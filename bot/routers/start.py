from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.repositories.users import UsersRepository
from bot import texts
from bot.keyboards.common import BACK_TO_MAIN_CALLBACK
from bot.keyboards.main_menu import main_menu_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return

    users = UsersRepository(session)
    existing_user = await users.get_by_telegram_id(message.from_user.id)
    user = await users.create_or_update_from_telegram(
        telegram_id=message.from_user.id,
        telegram_username=message.from_user.username,
        first_name=message.from_user.first_name,
        is_admin=message.from_user.id in settings.admin_ids,
    )
    referral_code = _extract_referral_code(message.text)
    if existing_user is None and referral_code:
        referrer = await users.get_by_referral_code(referral_code)
        if referrer is not None and referrer.telegram_id != message.from_user.id:
            user.referred_by_id = referrer.id
    await session.commit()

    await message.answer(texts.welcome_text(message.from_user.first_name), reply_markup=main_menu_keyboard())


@router.message(F.text == texts.BTN_BACK)
async def back_to_main(message: Message) -> None:
    await message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == BACK_TO_MAIN_CALLBACK)
async def back_to_main_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


def _extract_referral_code(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    code = parts[1].strip()
    return code or None
