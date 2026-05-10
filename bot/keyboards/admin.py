from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Payment, Plan


class AdminActionCallback(CallbackData, prefix="adm"):
    action: str


class AdminPaymentCallback(CallbackData, prefix="adm_pay"):
    action: str
    payment_id: int


class AdminPlanCallback(CallbackData, prefix="adm_plan"):
    action: str
    plan_id: int


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 مدیریت پلن‌ها", callback_data=AdminActionCallback(action="plans"))
    builder.button(text="🧾 سفارش‌های جدید", callback_data=AdminActionCallback(action="orders"))
    builder.button(text="💳 پرداخت‌های در انتظار تایید", callback_data=AdminActionCallback(action="payments"))
    builder.button(text="👥 کاربران", callback_data=AdminActionCallback(action="users"))
    builder.button(text="🛍 سرویس‌ها", callback_data=AdminActionCallback(action="services"))
    builder.button(text="📢 پیام همگانی", callback_data=AdminActionCallback(action="broadcast"))
    builder.button(text="↩️ بازگشت", callback_data=AdminActionCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def pending_payments_keyboard(payments: list[Payment]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for payment in payments:
        tracking_code = payment.order.tracking_code if payment.order else str(payment.id)
        builder.button(
            text=f"✅ تایید {tracking_code}",
            callback_data=AdminPaymentCallback(action="approve", payment_id=payment.id),
        )
        builder.button(
            text=f"❌ رد {tracking_code}",
            callback_data=AdminPaymentCallback(action="reject", payment_id=payment.id),
        )
    builder.button(text="↩️ بازگشت", callback_data=AdminActionCallback(action="panel"))
    builder.adjust(*([2] * len(payments)), 1)
    return builder.as_markup()


def payment_review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ تایید پرداخت",
        callback_data=AdminPaymentCallback(action="approve", payment_id=payment_id),
    )
    builder.button(
        text="❌ رد پرداخت",
        callback_data=AdminPaymentCallback(action="reject", payment_id=payment_id),
    )
    builder.adjust(2)
    return builder.as_markup()


def plans_management_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ افزودن پلن", callback_data=AdminActionCallback(action="add_plan"))
    for plan in plans:
        action_text = "غیرفعال کردن" if plan.is_active else "فعال کردن"
        status = "✅" if plan.is_active else "⛔"
        builder.button(
            text=f"{status} {action_text}: {plan.title}",
            callback_data=AdminPlanCallback(action="toggle", plan_id=plan.id),
        )
    builder.button(text="↩️ بازگشت", callback_data=AdminActionCallback(action="panel"))
    builder.adjust(1)
    return builder.as_markup()
