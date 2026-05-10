from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.tracking import generate_referral_code


class UsersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def create_or_update_from_telegram(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
        first_name: str | None,
        is_admin: bool,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                first_name=first_name,
                referral_code=generate_referral_code(telegram_id),
                is_admin=is_admin,
            )
            self.session.add(user)
        else:
            user.telegram_username = telegram_username
            user.first_name = first_name
            user.is_admin = bool(user.is_admin or is_admin)

        await self.session.flush()
        return user
