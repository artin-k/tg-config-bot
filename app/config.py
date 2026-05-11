from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_vpn_shop",
        alias="DATABASE_URL",
    )
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    fsm_storage: str = Field(default="memory", alias="FSM_STORAGE")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    support_username: str = Field(default="support", alias="SUPPORT_USERNAME")
    payment_card_number: str = Field(default="", alias="PAYMENT_CARD_NUMBER")
    payment_card_holder: str = Field(default="", alias="PAYMENT_CARD_HOLDER")
    payment_description: str = Field(
        default="پرداخت سفارش اشتراک VPN",
        alias="PAYMENT_DESCRIPTION",
    )
    order_expire_minutes: int = Field(default=15, alias="ORDER_EXPIRE_MINUTES")
    referral_reward_amount: int = Field(default=0, alias="REFERRAL_REWARD_AMOUNT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, dotenv_settings, env_settings, file_secret_settings

    @field_validator("support_username", mode="after")
    @classmethod
    def normalize_support_username(cls, value: str) -> str:
        return value.strip().removeprefix("@")

    @field_validator("redis_url", mode="after")
    @classmethod
    def normalize_redis_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()

    @field_validator("fsm_storage", mode="after")
    @classmethod
    def normalize_fsm_storage(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"memory", "redis"}:
            return "memory"
        return normalized

    @property
    def admin_ids(self) -> list[int]:
        if not self.admin_ids_raw.strip():
            return []
        return [int(item.strip()) for item in self.admin_ids_raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
