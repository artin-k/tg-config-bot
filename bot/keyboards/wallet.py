from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class WalletCallback(CallbackData, prefix="wallet"):
    action: str


class WalletTopupReviewCallback(CallbackData, prefix="wal_rev"):
    action: str
    transaction_id: int


def wallet_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ شارژ کیف پول", callback_data=WalletCallback(action="topup"))
    builder.button(text="💸 برداشت از کیف پول", callback_data=WalletCallback(action="withdraw"))
    builder.button(text="📜 تاریخچه تراکنش‌ها", callback_data=WalletCallback(action="history"))
    builder.button(text="📤 درخواست‌های برداشت من", callback_data=WalletCallback(action="withdrawals"))
    builder.button(text="↩️ بازگشت", callback_data=WalletCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def withdrawal_destination_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 کارت بانکی", callback_data=WalletCallback(action="dest_card"))
    builder.button(text="🏦 شماره شبا", callback_data=WalletCallback(action="dest_sheba"))
    builder.button(text="↩️ بازگشت", callback_data=WalletCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def withdrawal_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ثبت درخواست برداشت", callback_data=WalletCallback(action="withdraw_confirm"))
    builder.button(text="❌ لغو", callback_data=WalletCallback(action="withdraw_cancel"))
    builder.adjust(1)
    return builder.as_markup()


def wallet_topup_review_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ تایید شارژ کیف پول",
        callback_data=WalletTopupReviewCallback(action="approve", transaction_id=transaction_id),
    )
    builder.button(
        text="❌ رد شارژ کیف پول",
        callback_data=WalletTopupReviewCallback(action="reject", transaction_id=transaction_id),
    )
    builder.adjust(2)
    return builder.as_markup()
