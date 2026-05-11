from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.repositories.users import UsersRepository
from app.utils.money import format_toman
from bot import texts
from bot.keyboards.main_menu import main_menu_keyboard

router = Router(name="referral")


@router.message(F.text == texts.BTN_REFERRAL)
async def referral(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return

    users = UsersRepository(session)
    user = await users.get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("ابتدا /start را ارسال کنید.", reply_markup=main_menu_keyboard())
        return

    bot_info = await message.bot.get_me()
    count = await users.count_referrals(user.id)
    reward = settings.referral_reward_amount
    reward_line = (
        f"💰 پاداش هر دعوت موفق: {format_toman(reward)} تومان"
        if reward > 0
        else "در حال حاضر پاداش مالی توسط مدیریت تنظیم نشده است."
    )

    await message.answer(
        f"""👥 زیرمجموعه‌گیری

با دعوت دوستان خود می‌توانید اعتبار هدیه دریافت کنید.

🔗 لینک دعوت اختصاصی شما:
https://t.me/{bot_info.username}?start={user.referral_code}

👤 تعداد زیرمجموعه‌های شما: {count}
{reward_line}

بعد از خرید موفق زیرمجموعه، پاداش به کیف پول شما اضافه می‌شود.""",
        reply_markup=main_menu_keyboard(),
    )
