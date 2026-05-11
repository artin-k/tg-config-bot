from datetime import datetime, timedelta, timezone

from app.models import Plan, VPNService, VPNServiceStatus
from app.services.vpn_panel import VPNPanelService


class RenewalService:
    def __init__(self, vpn_panel: VPNPanelService) -> None:
        self.vpn_panel = vpn_panel

    async def extend_service(self, *, service: VPNService, plan: Plan, now: datetime) -> datetime:
        current_expire_at = service.expire_at
        if current_expire_at.tzinfo is None:
            current_expire_at = current_expire_at.replace(tzinfo=timezone.utc)

        base_expire_at = current_expire_at if current_expire_at > now else now
        new_expire_at = base_expire_at + timedelta(days=plan.duration_days)

        await self.vpn_panel.extend_service(
            username=service.username,
            volume_gb=plan.volume_gb,
            duration_days=plan.duration_days,
            expire_at=new_expire_at,
        )

        service.expire_at = new_expire_at
        service.volume_gb += plan.volume_gb
        service.duration_days += plan.duration_days
        service.status = VPNServiceStatus.ACTIVE.value
        return new_expire_at
