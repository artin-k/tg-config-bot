from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.tutorials import TutorialCallback, tutorials_keyboard

router = Router(name="tutorials")


TUTORIAL_TEXTS = {
    "android": """📱 آموزش اتصال در اندروید

1. ابتدا برنامه V2RayNG را نصب کنید.
2. لینک کانفیگ یا اشتراک را کپی کنید.
3. وارد برنامه شوید و گزینه + را بزنید.
4. گزینه Import from clipboard را انتخاب کنید.
5. کانفیگ را فعال کرده و متصل شوید.""",
    "iphone": """🍎 آموزش اتصال در آیفون

1. یکی از برنامه‌های Streisand، FoXray یا Shadowrocket را نصب کنید.
2. لینک اشتراک یا کانفیگ را کپی کنید.
3. داخل برنامه گزینه Import یا Add را انتخاب کنید.
4. کانفیگ را از Clipboard اضافه کنید.
5. در صورت نیاز به راهنمایی بیشتر، به پشتیبانی پیام دهید.""",
    "windows": """💻 آموزش اتصال در ویندوز

1. برنامه v2rayN را نصب و اجرا کنید.
2. لینک اشتراک یا کانفیگ را کپی کنید.
3. از منوی Servers گزینه Import from clipboard را بزنید.
4. یک سرور را انتخاب کنید و System Proxy را فعال کنید.
5. اتصال را تست کنید.""",
    "mac": """🖥 آموزش اتصال در مک

1. یکی از برنامه‌های V2Box، Streisand یا Clash Verge را نصب کنید.
2. لینک اشتراک یا کانفیگ را کپی کنید.
3. داخل برنامه گزینه Import from clipboard یا Add subscription را انتخاب کنید.
4. کانفیگ را فعال کنید و متصل شوید.""",
    "links": """🔗 لینک برنامه‌ها

لینک‌های دانلود توسط مدیریت تنظیم خواهد شد.

تا آن زمان، اگر برای نصب برنامه نیاز به راهنمایی دارید با پشتیبانی در ارتباط باشید.""",
}


@router.message(F.text == texts.BTN_TUTORIALS)
async def tutorials(message: Message) -> None:
    await message.answer(
        """📚 بخش آموزش

لطفاً سیستم‌عامل یا برنامه مورد نظر خود را انتخاب کنید:""",
        reply_markup=tutorials_keyboard(),
    )


@router.callback_query(TutorialCallback.filter())
async def tutorial_callback(callback: CallbackQuery, callback_data: TutorialCallback) -> None:
    await callback.answer()
    if callback.message is None:
        return

    if callback_data.topic == "back":
        await callback.message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
        return

    text = TUTORIAL_TEXTS.get(callback_data.topic, texts.COMING_SOON_TEXT)
    try:
        await callback.message.edit_text(text, reply_markup=tutorials_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=tutorials_keyboard())
