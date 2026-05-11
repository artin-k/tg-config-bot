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


def admin_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 مدیریت تعرفه‌ها", callback_data=AdminActionCallback(action="plans"))
    builder.button(text="💳 پرداخت‌های در انتظار تایید", callback_data=AdminActionCallback(action="payments"))
    builder.button(text="🧾 سفارش‌ها", callback_data=AdminActionCallback(action="orders"))
    builder.button(text="👥 کاربران", callback_data=AdminActionCallback(action="users"))
    builder.button(text="🛍 سرویس‌ها", callback_data=AdminActionCallback(action="services"))
    builder.button(text="📢 پیام همگانی", callback_data=AdminActionCallback(action="broadcast"))
    builder.button(text="⚙️ تنظیمات", callback_data=AdminActionCallback(action="settings"))
    builder.button(text="↩️ بازگشت به ربات", callback_data=AdminActionCallback(action="back"))
    builder.adjust(1)
    return builder.as_markup()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return admin_main_keyboard()


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
    builder.button(text="➕ افزودن تعرفه", callback_data=AdminActionCallback(action="add_plan"))
    for plan in plans:
        status = "🟢" if plan.is_active else "🔴"
        builder.button(
            text=f"{status} {plan.title}",
            callback_data=AdminPlanCallback(action="detail", plan_id=plan.id),
        )
    builder.button(text="↩️ بازگشت", callback_data=AdminActionCallback(action="panel"))
    builder.adjust(1)
    return builder.as_markup()


def plan_detail_keyboard(plan: Plan) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ ویرایش عنوان", callback_data=AdminPlanCallback(action="edit_title", plan_id=plan.id))
    builder.button(text="📝 ویرایش توضیحات", callback_data=AdminPlanCallback(action="edit_desc", plan_id=plan.id))
    builder.button(text="🗓 ویرایش مدت", callback_data=AdminPlanCallback(action="edit_duration", plan_id=plan.id))
    builder.button(text="📦 ویرایش حجم", callback_data=AdminPlanCallback(action="edit_volume", plan_id=plan.id))
    builder.button(text="💵 ویرایش قیمت", callback_data=AdminPlanCallback(action="edit_price", plan_id=plan.id))
    builder.button(text="🔢 ویرایش ترتیب نمایش", callback_data=AdminPlanCallback(action="edit_sort", plan_id=plan.id))
    toggle_text = "🔴 غیرفعال کردن" if plan.is_active else "🟢 فعال کردن"
    builder.button(text=toggle_text, callback_data=AdminPlanCallback(action="toggle", plan_id=plan.id))
    builder.button(text="🗑 حذف تعرفه", callback_data=AdminPlanCallback(action="delete", plan_id=plan.id))
    builder.button(text="↩️ بازگشت", callback_data=AdminActionCallback(action="plans"))
    builder.adjust(1)
    return builder.as_markup()


def add_plan_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ذخیره تعرفه", callback_data=AdminActionCallback(action="save_add_plan"))
    builder.button(text="❌ لغو", callback_data=AdminActionCallback(action="cancel_add_plan"))
    builder.adjust(2)
    return builder.as_markup()
