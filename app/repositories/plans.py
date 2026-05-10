from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Plan


class PlansRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, plan_id: int) -> Plan | None:
        return await self.session.get(Plan, plan_id)

    async def list_active(self) -> list[Plan]:
        result = await self.session.scalars(
            select(Plan)
            .where(Plan.is_active.is_(True))
            .order_by(Plan.sort_order.asc(), Plan.price.asc(), Plan.id.asc())
        )
        return list(result.all())

    async def list_all(self) -> list[Plan]:
        result = await self.session.scalars(select(Plan).order_by(Plan.sort_order.asc(), Plan.id.asc()))
        return list(result.all())

    async def create(
        self,
        *,
        title: str,
        duration_days: int,
        volume_gb: int,
        price: int,
        description: str | None = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> Plan:
        plan = Plan(
            title=title,
            duration_days=duration_days,
            volume_gb=volume_gb,
            price=price,
            description=description,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def set_active(self, plan_id: int, is_active: bool) -> Plan | None:
        plan = await self.get(plan_id)
        if plan is None:
            return None
        plan.is_active = is_active
        await self.session.flush()
        return plan
