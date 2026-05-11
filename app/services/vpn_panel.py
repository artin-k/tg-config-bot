from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VPNProvisionResult:
    config_link: str
    subscription_link: str


class VPNPanelService:
    async def provision_user(
        self,
        *,
        username: str,
        volume_gb: int,
        duration_days: int,
    ) -> VPNProvisionResult:
        return VPNProvisionResult(
            config_link=f"vless://placeholder-{username}",
            subscription_link=f"https://example.com/sub/{username}",
        )

    async def extend_service(
        self,
        *,
        username: str,
        volume_gb: int,
        duration_days: int,
        expire_at: datetime,
    ) -> None:
        return None
