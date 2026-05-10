from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts

BACK_TO_MAIN_CALLBACK = "common:back_to_main"


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_BACK, callback_data=BACK_TO_MAIN_CALLBACK)
    return builder.as_markup()
