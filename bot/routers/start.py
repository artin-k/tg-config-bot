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
    await users.create_or_update_from_telegram(
        telegram_id=message.from_user.id,
        telegram_username=message.from_user.username,
        first_name=message.from_user.first_name,
        is_admin=message.from_user.id in settings.admin_ids,
    )
    await session.commit()

    await message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.message(F.text == texts.BTN_BACK)
async def back_to_main(message: Message) -> None:
    await message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == BACK_TO_MAIN_CALLBACK)
async def back_to_main_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
