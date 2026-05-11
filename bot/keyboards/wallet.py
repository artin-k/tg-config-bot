from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class WalletCallback(CallbackData, prefix="wallet"):
    action: str


def wallet_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 تاریخچه تراکنش‌ها", callback_data=WalletCallback(action="history"))
    builder.button(text="↩️ بازگشت", callback_data=WalletCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()
