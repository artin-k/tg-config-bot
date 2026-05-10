from aiogram import F, Router
from aiogram.types import Message

from bot import texts

router = Router(name="common")


COMING_SOON_BUTTONS = {
    texts.BTN_RENEW,
    texts.BTN_TEST_ACCOUNT,
    texts.BTN_LUCKY_WHEEL,
    texts.BTN_WALLET,
    texts.BTN_REFERRAL,
    texts.BTN_TUTORIALS,
}


@router.message(F.text.in_(COMING_SOON_BUTTONS))
async def coming_soon(message: Message) -> None:
    await message.answer(texts.COMING_SOON_TEXT)
