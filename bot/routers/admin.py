from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.repositories.payments import PaymentsRepository
from app.repositories.plans import PlansRepository
from app.repositories.users import UsersRepository
from app.services.payment_service import (
    PaymentAlreadyProcessedError,
    PaymentApprovalError,
    PaymentExpiredError,
    PaymentService,
)
from app.services.vpn_panel import VPNPanelService
from app.utils.money import format_toman
from bot import texts
from bot.keyboards.admin import (
    AdminActionCallback,
    AdminPaymentCallback,
    AdminPlanCallback,
    admin_panel_keyboard,
    pending_payments_keyboard,
    plans_management_keyboard,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states.admin import AdminAddPlanStates

router = Router(name="admin")


@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession, settings: Settings) -> None:
    if not await _is_admin(message.from_user.id if message.from_user else None, session, settings):
        await message.answer("شما دسترسی مدیریت ندارید.")
        return
    await message.answer(texts.ADMIN_PANEL_TEXT, reply_markup=admin_panel_keyboard())


@router.callback_query(AdminActionCallback.filter())
async def admin_action(
    callback: CallbackQuery,
    callback_data: AdminActionCallback,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if not await _is_admin(callback.from_user.id if callback.from_user else None, session, settings):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return

    action = callback_data.action
    await callback.answer()

    if action in {"panel", "back"}:
        await state.clear()
        if action == "back":
            if callback.message:
                await callback.message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
        elif callback.message:
            await callback.message.edit_text(texts.ADMIN_PANEL_TEXT, reply_markup=admin_panel_keyboard())
        return

    if action == "payments":
        await _show_pending_payments(callback, session)
        return

    if action == "plans":
        await _show_plans(callback, session)
        return

    if action == "add_plan":
        await state.set_state(AdminAddPlanStates.title)
        if callback.message:
            await callback.message.answer("عنوان پلن را ارسال کنید.")
        return

    if callback.message:
        await callback.message.answer(texts.COMING_SOON_TEXT)


@router.callback_query(AdminPaymentCallback.filter())
async def admin_payment_action(
    callback: CallbackQuery,
    callback_data: AdminPaymentCallback,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if not await _is_admin(callback.from_user.id if callback.from_user else None, session, settings):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return

    payment_service = PaymentService(session, VPNPanelService())
    try:
        if callback_data.action == "approve":
            result = await payment_service.approve_payment(callback_data.payment_id)
            await callback.bot.send_message(
                chat_id=result.user_telegram_id,
                text=f"""✅ پرداخت شما تایید شد

✅ سرویس شما با موفقیت ساخته شد

👤 نام کاربری: {escape(result.custom_username)}
⚡ پلن: {escape(result.plan_title)}
📦 حجم: {result.volume_gb} گیگ
🗓 اعتبار: {result.duration_days} روز

🔗 کانفیگ شما:
{escape(result.config_link)}

🔗 لینک اشتراک:
{escape(result.subscription_link)}""",
            )
            await callback.answer("پرداخت تایید شد.")
            await _remove_admin_buttons(callback)
        elif callback_data.action == "reject":
            result = await payment_service.reject_payment(callback_data.payment_id)
            await callback.bot.send_message(
                chat_id=result.user_telegram_id,
                text="""❌ پرداخت شما توسط مدیریت تایید نشد.
در صورت وجود مشکل با پشتیبانی در ارتباط باشید.""",
            )
            await callback.answer("پرداخت رد شد.")
            await _remove_admin_buttons(callback)
    except PaymentExpiredError:
        await callback.answer(texts.EXPIRED_ORDER_TEXT, show_alert=True)
    except PaymentAlreadyProcessedError:
        await callback.answer("این پرداخت قبلاً بررسی شده است.", show_alert=True)
    except PaymentApprovalError:
        await callback.answer("پرداخت پیدا نشد.", show_alert=True)


@router.callback_query(AdminPlanCallback.filter())
async def toggle_plan(
    callback: CallbackQuery,
    callback_data: AdminPlanCallback,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if not await _is_admin(callback.from_user.id if callback.from_user else None, session, settings):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return
    if callback_data.action != "toggle":
        await callback.answer("عملیات نامعتبر است.", show_alert=True)
        return

    plans_repo = PlansRepository(session)
    plan = await plans_repo.get(callback_data.plan_id)
    if plan is None:
        await callback.answer("پلن پیدا نشد.", show_alert=True)
        return
    await plans_repo.set_active(plan.id, not plan.is_active)
    await session.commit()
    await callback.answer("وضعیت پلن تغییر کرد.")
    await _show_plans(callback, session)


@router.message(AdminAddPlanStates.title)
async def add_plan_title(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _is_admin(message.from_user.id if message.from_user else None, session, settings):
        await state.clear()
        await message.answer("دسترسی ندارید.")
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("عنوان نمی‌تواند خالی باشد. دوباره ارسال کنید.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminAddPlanStates.duration_days)
    await message.answer("مدت اعتبار پلن را به روز ارسال کنید. مثال: 30")


@router.message(AdminAddPlanStates.duration_days)
async def add_plan_duration(message: Message, state: FSMContext) -> None:
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
        return
    await state.update_data(duration_days=value)
    await state.set_state(AdminAddPlanStates.volume_gb)
    await message.answer("حجم پلن را به گیگ ارسال کنید. مثال: 10")


@router.message(AdminAddPlanStates.volume_gb)
async def add_plan_volume(message: Message, state: FSMContext) -> None:
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
        return
    await state.update_data(volume_gb=value)
    await state.set_state(AdminAddPlanStates.price)
    await message.answer("قیمت پلن را به تومان ارسال کنید. مثال: 2100000")


@router.message(AdminAddPlanStates.price)
async def add_plan_price(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if not await _is_admin(message.from_user.id if message.from_user else None, session, settings):
        await state.clear()
        await message.answer("دسترسی ندارید.")
        return
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
        return

    data = await state.get_data()
    plan = await PlansRepository(session).create(
        title=data["title"],
        duration_days=int(data["duration_days"]),
        volume_gb=int(data["volume_gb"]),
        price=value,
        is_active=True,
    )
    await session.commit()
    await state.clear()
    await message.answer(
        f"""✅ پلن جدید ذخیره شد.

{escape(plan.title)}
📦 حجم: {plan.volume_gb} گیگ
🗓 مدت: {plan.duration_days} روز
💵 قیمت: {format_toman(plan.price)} تومان""",
        reply_markup=admin_panel_keyboard(),
    )


async def _show_pending_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    payments = await PaymentsRepository(session).list_pending_review()
    if not payments:
        text = "پرداختی در انتظار تایید نیست."
    else:
        lines = ["💳 پرداخت‌های در انتظار تایید:"]
        for payment in payments:
            lines.append(
                f"""
🛒 {payment.order.tracking_code}
👤 {escape(payment.user.first_name or "-")} / @{escape(payment.user.telegram_username or "-")}
⚡ {escape(payment.order.plan.title)}
💵 {format_toman(payment.amount)} تومان"""
            )
        text = "\n".join(lines)

    if callback.message:
        await callback.message.edit_text(text, reply_markup=pending_payments_keyboard(payments))


async def _show_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    plans = await PlansRepository(session).list_all()
    if not plans:
        text = "هنوز پلنی ثبت نشده است."
    else:
        lines = ["📦 مدیریت پلن‌ها:"]
        for plan in plans:
            status = "فعال" if plan.is_active else "غیرفعال"
            lines.append(
                f"""
{escape(plan.title)}
وضعیت: {status}
حجم: {plan.volume_gb} گیگ | مدت: {plan.duration_days} روز | قیمت: {format_toman(plan.price)} تومان"""
            )
        text = "\n".join(lines)

    if callback.message:
        await callback.message.edit_text(text, reply_markup=plans_management_keyboard(plans))


async def _is_admin(telegram_id: int | None, session: AsyncSession, settings: Settings) -> bool:
    if telegram_id is None:
        return False
    if telegram_id in settings.admin_ids:
        return True
    user = await UsersRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


def _parse_positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip().replace(",", "")
    if not normalized.isdigit():
        return None
    parsed = int(normalized)
    return parsed if parsed > 0 else None


async def _remove_admin_buttons(callback: CallbackQuery) -> None:
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
