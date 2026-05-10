from dataclasses import dataclass


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
