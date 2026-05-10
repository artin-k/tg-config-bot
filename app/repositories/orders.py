from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Order


class OrdersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, order_id: int) -> Order | None:
        return await self.session.get(Order, order_id)

    async def get_with_details(self, order_id: int) -> Order | None:
        return await self.session.scalar(
            select(Order)
            .options(
                joinedload(Order.user),
                joinedload(Order.plan),
                joinedload(Order.payment),
            )
            .where(Order.id == order_id)
        )

    async def get_by_tracking_code(self, tracking_code: str) -> Order | None:
        return await self.session.scalar(select(Order).where(Order.tracking_code == tracking_code))

    async def create(
        self,
        *,
        user_id: int,
        plan_id: int,
        custom_username: str,
        tracking_code: str,
        amount: int,
        status: str,
        expires_at,
    ) -> Order:
        order = Order(
            user_id=user_id,
            plan_id=plan_id,
            custom_username=custom_username,
            tracking_code=tracking_code,
            amount=amount,
            status=status,
            expires_at=expires_at,
        )
        self.session.add(order)
        await self.session.flush()
        return order
