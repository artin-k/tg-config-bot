from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Plan
from app.utils.money import format_toman
from bot import texts

BUY_BACK_TO_MENU = "buy:back_to_menu"
BUY_BACK_TO_PLANS = "buy:back_to_plans"


class PlanCallback(CallbackData, prefix="plan"):
    plan_id: int


class ConfirmPlanCallback(CallbackData, prefix="buy_confirm"):
    plan_id: int


class PaymentCallback(CallbackData, prefix="pay"):
    order_id: int


def plans_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    return plans_inline_keyboard(plans)


def plans_inline_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(
            text=f"{plan.title} | {plan.volume_gb} گیگ | {format_toman(plan.price)} تومان",
            callback_data=PlanCallback(plan_id=plan.id),
        )
    builder.button(text=texts.BTN_BACK, callback_data=BUY_BACK_TO_MENU)
    builder.adjust(1)
    return builder.as_markup()


def pre_invoice_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ادامه خرید", callback_data=ConfirmPlanCallback(plan_id=plan_id))
    builder.button(text=texts.BTN_BACK, callback_data=BUY_BACK_TO_PLANS)
    builder.adjust(1)
    return builder.as_markup()


def payment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تایید و پرداخت", callback_data=PaymentCallback(order_id=order_id))
    builder.adjust(1)
    return builder.as_markup()
