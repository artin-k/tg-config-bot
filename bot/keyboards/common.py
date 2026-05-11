from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts

BACK_TO_MAIN_CALLBACK = "common:back_to_main"
CANCEL_CALLBACK = "common:cancel"
CONFIRM_CALLBACK = "common:confirm"


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return back_inline_keyboard()


def back_inline_keyboard(callback_data: str = BACK_TO_MAIN_CALLBACK, text: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text or texts.BTN_BACK, callback_data=callback_data)
    return builder.as_markup()


def confirm_cancel_keyboard(confirm_data: str = CONFIRM_CALLBACK, cancel_data: str = CANCEL_CALLBACK) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تایید", callback_data=confirm_data)
    builder.button(text="❌ لغو", callback_data=cancel_data)
    builder.adjust(2)
    return builder.as_markup()
