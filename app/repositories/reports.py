from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderStatus, Subscription

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


@dataclass(frozen=True)
class SalesReportStats:
    today_sales: int
    week_sales: int
    total_sales: int
    completed_orders_count: int
    active_subscriptions_count: int
    expired_subscriptions_count: int


class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sales_report(self, now: datetime | None = None) -> SalesReportStats:
        now_utc = self._as_utc(now or datetime.now(timezone.utc))
        today_start_utc, week_start_utc = self._tehran_period_starts(now_utc)
        sale_timestamp = func.coalesce(Order.completed_at, Order.paid_at, Order.created_at)

        sales_row = (
            await self.session.execute(
                select(
                    func.coalesce(
                        func.sum(case((sale_timestamp >= today_start_utc, Order.amount), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((sale_timestamp >= week_start_utc, Order.amount), else_=0)),
                        0,
                    ),
                    func.coalesce(func.sum(Order.amount), 0),
                    func.count(Order.id),
                ).where(Order.status == OrderStatus.COMPLETED.value)
            )
        ).one()

        active_condition = Subscription.status == "active"
        active_not_expired = active_condition & (Subscription.expire_at >= now_utc)
        expired_condition = (Subscription.status != "active") | (Subscription.expire_at < now_utc)
        subscriptions_row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(case((active_not_expired, 1), else_=0)), 0),
                    func.coalesce(func.sum(case((expired_condition, 1), else_=0)), 0),
                )
            )
        ).one()

        return SalesReportStats(
            today_sales=int(sales_row[0] or 0),
            week_sales=int(sales_row[1] or 0),
            total_sales=int(sales_row[2] or 0),
            completed_orders_count=int(sales_row[3] or 0),
            active_subscriptions_count=int(subscriptions_row[0] or 0),
            expired_subscriptions_count=int(subscriptions_row[1] or 0),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _tehran_period_starts(now_utc: datetime) -> tuple[datetime, datetime]:
        now_tehran = now_utc.astimezone(TEHRAN_TZ)
        today_start_tehran = datetime.combine(now_tehran.date(), time.min, tzinfo=TEHRAN_TZ)
        days_since_saturday = (now_tehran.weekday() - 5) % 7
        week_start_tehran = today_start_tehran - timedelta(days=days_since_saturday)
        return (
            today_start_tehran.astimezone(timezone.utc),
            week_start_tehran.astimezone(timezone.utc),
        )
