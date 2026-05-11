from aiogram import F, Router
from aiogram.types import Message

from bot import texts

router = Router(name="common")


COMING_SOON_BUTTONS = {
    texts.BTN_TEST_ACCOUNT,
    texts.BTN_LUCKY_WHEEL,
}


@router.message(F.text.in_(COMING_SOON_BUTTONS))
async def coming_soon(message: Message) -> None:
    await message.answer(texts.COMING_SOON_TEXT)


@router.message(F.photo)
async def unexpected_photo(message: Message) -> None:
    await message.answer("رسید پرداخت فقط زمانی قابل ثبت است که از داخل سفارش گزینه پرداخت را انتخاب کرده باشید.")
