from html import escape
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.services import ServicesRepository
from app.repositories.users import UsersRepository
from bot import texts

router = Router(name="services")


@router.message(F.text == texts.BTN_MY_SERVICES)
async def my_services(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    user = await UsersRepository(session).get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("ابتدا /start را ارسال کنید.")
        return

    services = await ServicesRepository(session).list_active_by_user(user.id)
    if not services:
        await message.answer("شما هنوز سرویس فعالی ندارید.")
        return

    tehran = ZoneInfo("Asia/Tehran")
    lines = ["🛍 سرویس‌های فعال شما:"]
    for index, service in enumerate(services, start=1):
        expire_at = service.expire_at.astimezone(tehran).strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"""
{index}. {escape(service.username)}
⚡ پلن: {escape(service.plan.title)}
📦 حجم: {service.volume_gb} گیگ
🗓 تاریخ انقضا: {expire_at}
🔗 لینک اشتراک:
{escape(service.subscription_link or "-")}"""
        )

    await message.answer("\n".join(lines))
