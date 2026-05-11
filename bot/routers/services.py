from html import escape
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VPNServiceStatus
from app.repositories.services import ServicesRepository
from app.repositories.users import UsersRepository
from bot import texts
from bot.keyboards.main_menu import main_menu_keyboard
from bot.keyboards.services import ServiceActionCallback, services_actions_keyboard

router = Router(name="services")


@router.message(F.text == texts.BTN_MY_SERVICES)
async def my_services(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    user = await UsersRepository(session).get_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer("ابتدا /start را ارسال کنید.", reply_markup=main_menu_keyboard())
        return

    services = await ServicesRepository(session).list_active_by_user(user.id)
    if not services:
        await message.answer("شما هنوز سرویس فعالی ندارید.", reply_markup=main_menu_keyboard())
        return

    lines = ["🛍 سرویس‌های فعال شما"]
    for index, service in enumerate(services, start=1):
        lines.append(_service_summary(service, index))

    await message.answer("\n".join(lines), reply_markup=services_actions_keyboard(services))


@router.callback_query(ServiceActionCallback.filter(F.action.in_({"link", "status"})))
async def service_action(
    callback: CallbackQuery,
    callback_data: ServiceActionCallback,
    session: AsyncSession,
) -> None:
    await callback.answer()
    if callback.from_user is None:
        return

    user = await UsersRepository(session).get_by_telegram_id(callback.from_user.id)
    if user is None:
        await _safe_answer(callback, "ابتدا /start را ارسال کنید.")
        return

    service = await ServicesRepository(session).get_user_service(callback_data.service_id, user.id)
    if service is None:
        await _safe_answer(callback, "این سرویس پیدا نشد یا متعلق به حساب شما نیست.")
        return

    if callback_data.action == "link":
        await _safe_answer(
            callback,
            f"""🔗 لینک‌های سرویس {escape(service.username)}

لینک اشتراک:
{escape(service.subscription_link or "ثبت نشده")}

لینک کانفیگ:
{escape(service.config_link or "ثبت نشده")}""",
        )
        return

    await _safe_answer(callback, _service_summary(service))


def _service_summary(service, index: int | None = None) -> str:
    tehran = ZoneInfo("Asia/Tehran")
    expire_at = service.expire_at.astimezone(tehran).strftime("%Y-%m-%d %H:%M")
    status = "فعال" if service.status == VPNServiceStatus.ACTIVE.value else service.status
    prefix = f"\n{index}. " if index is not None else ""
    return f"""{prefix}{escape(service.username)}
⚡ پلن: {escape(service.plan.title if service.plan else "-")}
📦 حجم: {service.volume_gb} گیگ
🗓 تاریخ انقضا: {expire_at}
📌 وضعیت: {status}
🔗 لینک اشتراک: {escape(service.subscription_link or "-")}
🔗 لینک کانفیگ: {escape(service.config_link or "-")}"""


async def _safe_answer(callback: CallbackQuery, text: str) -> None:
    if callback.message:
        try:
            await callback.message.edit_text(text)
        except Exception:
            await callback.message.answer(text)
