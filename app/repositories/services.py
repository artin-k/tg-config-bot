from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import VPNService, VPNServiceStatus


class ServicesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: int,
        order_id: int,
        plan_id: int,
        username: str,
        config_link: str,
        subscription_link: str,
        volume_gb: int,
        duration_days: int,
        expire_at,
        status: str = VPNServiceStatus.ACTIVE.value,
    ) -> VPNService:
        service = VPNService(
            user_id=user_id,
            order_id=order_id,
            plan_id=plan_id,
            username=username,
            config_link=config_link,
            subscription_link=subscription_link,
            volume_gb=volume_gb,
            duration_days=duration_days,
            expire_at=expire_at,
            status=status,
        )
        self.session.add(service)
        await self.session.flush()
        return service

    async def list_active_by_user(self, user_id: int) -> list[VPNService]:
        result = await self.session.scalars(
            select(VPNService)
            .options(joinedload(VPNService.plan))
            .where(
                VPNService.user_id == user_id,
                VPNService.status == VPNServiceStatus.ACTIVE.value,
            )
            .order_by(VPNService.expire_at.desc())
        )
        return list(result.unique().all())
