from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription


class SubscriptionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, user_id: int, plan_id: int, controld_device_id: str, doh_link: str, expire_at: datetime, status: str = "active") -> Subscription:
        sub = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            controld_device_id=controld_device_id,
            doh_link=doh_link,
            expire_at=expire_at,
            status=status,
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def get_active_for_user(self, user_id: int) -> list[Subscription]:
        result = await self.session.scalars(
            "SELECT * FROM subscriptions WHERE user_id = :uid AND status = 'active'",
            params={"uid": user_id},
        )
        return list(result.all())
