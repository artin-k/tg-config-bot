from __future__ import annotations

from app.config import Settings
from app.models import User


def is_user_admin(user: User | None, settings: Settings) -> bool:
    if user is None:
        return False
    return is_admin_identity(
        telegram_id=user.telegram_id,
        settings=settings,
        db_is_admin=user.is_admin,
        db_is_root_admin=user.is_root_admin,
    )


def is_admin_identity(
    *,
    telegram_id: int | None,
    settings: Settings,
    db_is_admin: bool = False,
    db_is_root_admin: bool = False,
) -> bool:
    if telegram_id is None:
        return False
    return bool(
        db_is_admin
        or db_is_root_admin
        or telegram_id in settings.admin_ids
        or (
            settings.root_admin_telegram_id is not None
            and telegram_id == settings.root_admin_telegram_id
        )
    )
