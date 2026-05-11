from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import OrderKind
from app.repositories.payments import PaymentsRepository
from app.repositories.plans import PlansRepository
from app.repositories.users import UsersRepository
from app.services.order_status import order_kind_label
from app.services.payment_service import (
    ApprovedPaymentResult,
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
    add_plan_confirm_keyboard,
    admin_main_keyboard,
    pending_payments_keyboard,
    plan_detail_keyboard,
    plans_management_keyboard,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states.admin import AdminAddPlanStates, AdminEditPlanStates

router = Router(name="admin")

EDIT_FIELD_MAP = {
    "edit_title": ("title", "عنوان جدید تعرفه را ارسال کنید:", "title"),
    "edit_desc": ("description", "توضیحات جدید را ارسال کنید. برای خالی کردن، - بفرستید:", "description"),
    "edit_duration": ("duration_days", "مدت جدید را به روز ارسال کنید:", "positive_int"),
    "edit_volume": ("volume_gb", "حجم جدید را به گیگ ارسال کنید:", "positive_int"),
    "edit_price": ("price", "قیمت جدید را به تومان ارسال کنید:", "positive_int"),
    "edit_sort": ("sort_order", "ترتیب نمایش جدید را ارسال کنید. مقدار 0 مجاز است:", "int"),
}


@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession, settings: Settings) -> None:
    if not await _is_admin(message.from_user.id if message.from_user else None, session, settings):
        await message.answer("شما دسترسی مدیریت ندارید.")
        return
    await message.answer(texts.ADMIN_PANEL_TEXT, reply_markup=admin_main_keyboard())


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
            await callback.message.edit_text(texts.ADMIN_PANEL_TEXT, reply_markup=admin_main_keyboard())
        return

    if action == "payments":
        await state.clear()
        await _show_pending_payments(callback, session)
        return

    if action == "plans":
        await state.clear()
        await _show_plans(callback, session)
        return

    if action == "add_plan":
        await state.clear()
        await state.set_state(AdminAddPlanStates.title)
        if callback.message:
            await callback.message.answer("عنوان تعرفه را ارسال کنید.")
        return

    if action == "save_add_plan":
        await _save_add_plan(callback, state, session)
        return

    if action == "cancel_add_plan":
        await state.clear()
        if callback.message:
            await callback.message.answer("افزودن تعرفه لغو شد.", reply_markup=admin_main_keyboard())
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

    payment_service = PaymentService(session, VPNPanelService(), settings)
    try:
        if callback_data.action == "approve":
            result = await payment_service.approve_payment(callback_data.payment_id)
            await callback.bot.send_message(
                chat_id=result.user_telegram_id,
                text=_approved_message(result),
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
        await callback.answer("پرداخت پیدا نشد یا قابل تایید نیست.", show_alert=True)


@router.callback_query(AdminPlanCallback.filter())
async def admin_plan_action(
    callback: CallbackQuery,
    callback_data: AdminPlanCallback,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if not await _is_admin(callback.from_user.id if callback.from_user else None, session, settings):
        await callback.answer("دسترسی ندارید.", show_alert=True)
        return

    await callback.answer()
    plans_repo = PlansRepository(session)
    plan = await plans_repo.get(callback_data.plan_id)
    if plan is None:
        await _safe_edit_or_answer(callback, "تعرفه پیدا نشد.")
        return

    action = callback_data.action
    if action == "detail":
        await _show_plan_detail(callback, plan)
        return

    if action in EDIT_FIELD_MAP:
        field, prompt, validator = EDIT_FIELD_MAP[action]
        await state.set_state(AdminEditPlanStates.value)
        await state.update_data(plan_id=plan.id, field=field, validator=validator)
        if callback.message:
            await callback.message.answer(prompt)
        return

    if action == "toggle":
        await plans_repo.set_active(plan.id, not plan.is_active)
        await session.commit()
        refreshed = await plans_repo.get(plan.id)
        await _show_plan_detail(callback, refreshed)
        return

    if action == "delete":
        if await plans_repo.has_usage(plan.id):
            await plans_repo.set_active(plan.id, False)
            await session.commit()
            refreshed = await plans_repo.get(plan.id)
            detail = _format_plan_detail(refreshed) if refreshed is not None else ""
            await _safe_edit_or_answer(
                callback,
                f"این تعرفه سفارش یا سرویس ثبت‌شده دارد؛ حذف نشد و به‌جای آن غیرفعال شد.\n\n{detail}",
                reply_markup=plan_detail_keyboard(refreshed) if refreshed is not None else None,
            )
            return
        await plans_repo.delete(plan.id)
        await session.commit()
        await _show_plans(callback, session, prefix="✅ تعرفه حذف شد.\n\n")
        return

    await _safe_edit_or_answer(callback, "عملیات نامعتبر است.")


@router.message(AdminAddPlanStates.title)
async def add_plan_title(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("عنوان نمی‌تواند خالی باشد. دوباره ارسال کنید.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminAddPlanStates.description)
    await message.answer("توضیحات تعرفه را ارسال کنید. برای توضیحات خالی، - بفرستید.")


@router.message(AdminAddPlanStates.description)
async def add_plan_description(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    description = (message.text or "").strip()
    await state.update_data(description=None if description == "-" else description)
    await state.set_state(AdminAddPlanStates.duration_days)
    await message.answer("مدت اعتبار تعرفه را به روز ارسال کنید. مثال: 30")


@router.message(AdminAddPlanStates.duration_days)
async def add_plan_duration(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
        return
    await state.update_data(duration_days=value)
    await state.set_state(AdminAddPlanStates.volume_gb)
    await message.answer("حجم تعرفه را به گیگ ارسال کنید. مثال: 10")


@router.message(AdminAddPlanStates.volume_gb)
async def add_plan_volume(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
        return
    await state.update_data(volume_gb=value)
    await state.set_state(AdminAddPlanStates.price)
    await message.answer("قیمت تعرفه را به تومان ارسال کنید. مثال: 2100000")


@router.message(AdminAddPlanStates.price)
async def add_plan_price(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    value = _parse_positive_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
        return
    await state.update_data(price=value)
    await state.set_state(AdminAddPlanStates.sort_order)
    await message.answer("ترتیب نمایش را ارسال کنید. مقدار 0 هم مجاز است.")


@router.message(AdminAddPlanStates.sort_order)
async def add_plan_sort_order(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    value = _parse_int(message.text)
    if value is None:
        await message.answer("لطفاً یک عدد صحیح ارسال کنید.")
        return
    await state.update_data(sort_order=value)
    await state.set_state(AdminAddPlanStates.confirm)
    data = await state.get_data()
    await message.answer(_format_plan_data_summary(data), reply_markup=add_plan_confirm_keyboard())


@router.message(AdminEditPlanStates.value)
async def edit_plan_value(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    if not await _guard_admin_message(message, state, session, settings):
        return
    data = await state.get_data()
    plan_id = data.get("plan_id")
    field = data.get("field")
    validator = data.get("validator")
    if not plan_id or not field:
        await state.clear()
        await message.answer("ویرایش قابل ادامه نیست. دوباره تلاش کنید.", reply_markup=admin_main_keyboard())
        return

    parsed = _validate_edit_value(message.text, validator)
    if parsed is _INVALID:
        await message.answer(_validation_error(validator))
        return

    plan = await PlansRepository(session).update_fields(int(plan_id), **{field: parsed})
    await session.commit()
    await state.clear()
    if plan is None:
        await message.answer("تعرفه پیدا نشد.", reply_markup=admin_main_keyboard())
        return
    await message.answer("✅ تعرفه به‌روزرسانی شد.")
    await message.answer(_format_plan_detail(plan), reply_markup=plan_detail_keyboard(plan))


async def _save_add_plan(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    required = {"title", "duration_days", "volume_gb", "price", "sort_order"}
    if not required.issubset(data):
        await state.clear()
        await _safe_edit_or_answer(callback, "اطلاعات تعرفه کامل نیست. دوباره تلاش کنید.")
        return

    plan = await PlansRepository(session).create(
        title=str(data["title"]),
        description=data.get("description"),
        duration_days=int(data["duration_days"]),
        volume_gb=int(data["volume_gb"]),
        price=int(data["price"]),
        sort_order=int(data["sort_order"]),
        is_active=True,
    )
    await session.commit()
    await state.clear()
    if callback.message:
        await callback.message.answer(
            f"✅ تعرفه جدید ذخیره شد.\n\n{_format_plan_detail(plan)}",
            reply_markup=plan_detail_keyboard(plan),
        )


async def _show_pending_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    payments = await PaymentsRepository(session).list_pending_review()
    if not payments:
        text = "پرداختی در انتظار تایید نیست."
    else:
        lines = ["💳 پرداخت‌های در انتظار تایید:"]
        for payment in payments:
            order = payment.order
            user_name = payment.user.first_name or "-"
            telegram_username = f"@{payment.user.telegram_username}" if payment.user.telegram_username else "-"
            service_username = order.custom_username if order else "-"
            receipt_status = "رسید دریافت شده" if payment.receipt_file_id else "بدون رسید"
            lines.append(
                f"""
🛒 کد پیگیری: {order.tracking_code if order else "-"}
⚡ نوع سفارش: {order_kind_label(order.order_kind if order else None)}
👤 کاربر: {escape(user_name)} / {escape(telegram_username)}
⚡ پلن: {escape(order.plan.title if order and order.plan else "-")}
🔐 سرویس/نام کاربری: {escape(service_username or "-")}
💵 مبلغ: {format_toman(payment.amount)} تومان
📎 وضعیت رسید: {receipt_status}"""
            )
        text = "\n".join(lines)

    await _safe_edit_or_answer(callback, text, reply_markup=pending_payments_keyboard(payments))


async def _show_plans(callback: CallbackQuery, session: AsyncSession, prefix: str = "") -> None:
    plans = await PlansRepository(session).list_all()
    if not plans:
        text = f"{prefix}هنوز تعرفه‌ای ثبت نشده است."
    else:
        lines = [f"{prefix}📦 مدیریت تعرفه‌ها:"]
        for plan in plans:
            status = "فعال" if plan.is_active else "غیرفعال"
            lines.append(
                f"""
{escape(plan.title)}
وضعیت: {status}
حجم: {plan.volume_gb} گیگ | مدت: {plan.duration_days} روز | قیمت: {format_toman(plan.price)} تومان
ترتیب نمایش: {plan.sort_order}"""
            )
        text = "\n".join(lines)

    await _safe_edit_or_answer(callback, text, reply_markup=plans_management_keyboard(plans))


async def _show_plan_detail(callback: CallbackQuery, plan) -> None:
    if plan is None:
        await _safe_edit_or_answer(callback, "تعرفه پیدا نشد.")
        return
    await _safe_edit_or_answer(callback, _format_plan_detail(plan), reply_markup=plan_detail_keyboard(plan))


async def _is_admin(telegram_id: int | None, session: AsyncSession, settings: Settings) -> bool:
    if telegram_id is None:
        return False
    if telegram_id in settings.admin_ids:
        return True
    user = await UsersRepository(session).get_by_telegram_id(telegram_id)
    return bool(user and user.is_admin)


async def _guard_admin_message(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> bool:
    if not await _is_admin(message.from_user.id if message.from_user else None, session, settings):
        await state.clear()
        await message.answer("دسترسی ندارید.")
        return False
    if (message.text or "").strip() in {texts.BTN_BACK, texts.BTN_MAIN_MENU}:
        await state.clear()
        await message.answer(texts.ADMIN_PANEL_TEXT, reply_markup=admin_main_keyboard())
        return False
    return True


def _format_plan_detail(plan) -> str:
    status = "فعال" if plan.is_active else "غیرفعال"
    description = plan.description or "-"
    return f"""📦 جزئیات تعرفه

⚡ عنوان: {escape(plan.title)}
📝 توضیحات: {escape(description)}
📦 حجم: {plan.volume_gb} گیگ
🗓 مدت: {plan.duration_days} روز
💵 قیمت: {format_toman(plan.price)} تومان
🔢 ترتیب نمایش: {plan.sort_order}
📌 وضعیت: {status}"""


def _format_plan_data_summary(data: dict) -> str:
    description = data.get("description") or "-"
    return f"""🧾 خلاصه تعرفه جدید

⚡ عنوان: {escape(str(data["title"]))}
📝 توضیحات: {escape(str(description))}
📦 حجم: {data["volume_gb"]} گیگ
🗓 مدت: {data["duration_days"]} روز
💵 قیمت: {format_toman(int(data["price"]))} تومان
🔢 ترتیب نمایش: {data["sort_order"]}

آیا ذخیره شود؟"""


def _approved_message(result: ApprovedPaymentResult) -> str:
    if result.order_kind == OrderKind.RENEWAL.value:
        expire_at = _format_datetime(result.new_expire_at)
        return f"""✅ تمدید سرویس شما با موفقیت انجام شد

👤 نام کاربری: {escape(result.service_username)}
⚡ پلن تمدید: {escape(result.plan_title)}
📦 حجم افزوده: {result.volume_gb} گیگ
🗓 اعتبار افزوده: {result.duration_days} روز
📅 تاریخ انقضای جدید: {expire_at}"""

    return f"""✅ پرداخت شما تایید شد

✅ سرویس شما با موفقیت ساخته شد

👤 نام کاربری: {escape(result.service_username)}
⚡ پلن: {escape(result.plan_title)}
📦 حجم: {result.volume_gb} گیگ
🗓 اعتبار: {result.duration_days} روز

🔗 کانفیگ شما:
{escape(result.config_link or "-")}

🔗 لینک اشتراک:
{escape(result.subscription_link or "-")}"""


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone(ZoneInfo("Asia/Tehran")).strftime("%Y-%m-%d %H:%M")


def _parse_positive_int(value: str | None) -> int | None:
    parsed = _parse_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip().replace(",", "")
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


_INVALID = object()


def _validate_edit_value(value: str | None, validator: str):
    text = (value or "").strip()
    if validator == "title":
        return text if text else _INVALID
    if validator == "description":
        return None if text == "-" else text
    if validator == "positive_int":
        return _parse_positive_int(text) or _INVALID
    if validator == "int":
        parsed = _parse_int(text)
        return parsed if parsed is not None else _INVALID
    return _INVALID


def _validation_error(validator: str) -> str:
    if validator == "title":
        return "عنوان نمی‌تواند خالی باشد."
    if validator == "positive_int":
        return "لطفاً یک عدد صحیح مثبت ارسال کنید."
    if validator == "int":
        return "لطفاً یک عدد صحیح ارسال کنید."
    return "مقدار وارد شده معتبر نیست."


async def _safe_edit_or_answer(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup)


async def _remove_admin_buttons(callback: CallbackQuery) -> None:
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
