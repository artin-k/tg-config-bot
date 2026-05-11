from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.users import UsersRepository
from app.utils.money import format_toman
from bot import texts
from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.wallet import WalletCallback, wallet_keyboard

router = Router(name="wallet")


@router.message(F.text == texts.BTN_WALLET)
async def wallet(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    user = await UsersRepository(session).get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("ابتدا /start را ارسال کنید.", reply_markup=main_menu_keyboard())
        return

    await message.answer(
        f"""🏦 کیف پول شما

💵 موجودی فعلی: {format_toman(user.wallet_balance)} تومان

در نسخه فعلی، شارژ کیف پول از طریق پشتیبانی یا پاداش زیرمجموعه‌گیری انجام می‌شود.""",
        reply_markup=wallet_keyboard(),
    )


@router.callback_query(WalletCallback.filter())
async def wallet_callback(callback: CallbackQuery, callback_data: WalletCallback) -> None:
    await callback.answer()
    if callback.message is None:
        return
    if callback_data.action == "back":
        await callback.message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
        return
    await callback.message.answer("تاریخچه تراکنش‌ها در نسخه بعدی فعال می‌شود.")
