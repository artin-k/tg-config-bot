from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot import texts


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [texts.BTN_BUY, texts.BTN_RENEW],
        [texts.BTN_MY_SERVICES, texts.BTN_TARIFFS],
        [texts.BTN_TRACK_ORDER, texts.BTN_REFERRAL],
        [texts.BTN_TUTORIALS, texts.BTN_SUPPORT],
        [texts.BTN_WALLET, texts.BTN_TEST_ACCOUNT],
        [texts.BTN_LUCKY_WHEEL],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=item) for item in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder="یکی از گزینه‌ها را انتخاب کنید",
    )
