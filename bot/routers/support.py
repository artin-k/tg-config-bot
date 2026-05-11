from html import escape

from aiogram import F, Router
from aiogram.types import Message

from app.config import Settings
from bot import texts

router = Router(name="support")


@router.message(F.text == texts.BTN_SUPPORT)
async def support(message: Message, settings: Settings) -> None:
    await message.answer(
        f"""☎️ پشتیبانی

برای ارتباط با پشتیبانی به آیدی زیر پیام دهید:
@{escape(settings.support_username)}"""
    )
