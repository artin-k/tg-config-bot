from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import OrderStatus, PaymentStatus
from app.repositories.orders import OrdersRepository
from app.repositories.payments import PaymentsRepository
from app.repositories.plans import PlansRepository
from app.repositories.users import UsersRepository
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.username_validator import validate_username
from app.services.vpn_panel import VPNPanelService
from app.utils.money import format_toman
from bot import texts
from bot.keyboards.admin import payment_review_keyboard
from bot.keyboards.buy import (
    BUY_BACK_TO_MENU,
    BUY_BACK_TO_PLANS,
    ConfirmPlanCallback,
    PaymentCallback,
    PlanCallback,
    payment_keyboard,
    plans_keyboard,
    pre_invoice_keyboard,
)
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states.buy import BuyStates

router = Router(name="buy")


@router.message(F.text == texts.BTN_BUY)
async def show_plans(message: Message, session: AsyncSession) -> None:
    plans = await PlansRepository(session).list_active()
    if not plans:
        await message.answer("در حال حاضر پلن فعالی برای خرید وجود ندارد.", reply_markup=main_menu_keyboard())
        return

    await message.answer(texts.BUY_PLANS_TEXT, reply_markup=plans_keyboard(plans))


@router.callback_query(F.data == BUY_BACK_TO_MENU)
async def buy_back_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == BUY_BACK_TO_PLANS)
async def buy_back_to_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    plans = await PlansRepository(session).list_active()
    if callback.message:
        await callback.message.edit_text(texts.BUY_PLANS_TEXT, reply_markup=plans_keyboard(plans))


@router.callback_query(PlanCallback.filter())
async def show_pre_invoice(
    callback: CallbackQuery,
    callback_data: PlanCallback,
    session: AsyncSession,
) -> None:
    await callback.answer()
    plan = await PlansRepository(session).get(callback_data.plan_id)
    if plan is None or not plan.is_active:
        await _safe_edit_or_answer(callback, "این پلن در دسترس نیست.")
        return

    user = None
    if callback.from_user:
        user = await UsersRepository(session).get_by_telegram_id(callback.from_user.id)

    wallet_balance = user.wallet_balance if user else 0
    text = f"""🧾 پیش فاکتور شما:

🔐 نام کاربری: در مرحله بعد وارد می‌شود
⚡ نام سرویس: {escape(plan.title)}
📦 حجم: {plan.volume_gb} گیگ
🗓 مدت اعتبار: {plan.duration_days} روز
💵 قیمت: {format_toman(plan.price)} تومان
🏦 موجودی کیف پول شما: {format_toman(wallet_balance)} تومان

💰 سفارش شما آماده پرداخت است"""
    await _safe_edit_or_answer(callback, text, reply_markup=pre_invoice_keyboard(plan.id))


@router.callback_query(ConfirmPlanCallback.filter())
async def ask_username(
    callback: CallbackQuery,
    callback_data: ConfirmPlanCallback,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await callback.answer()
    plan = await PlansRepository(session).get(callback_data.plan_id)
    if plan is None or not plan.is_active:
        await _safe_edit_or_answer(callback, "این پلن در دسترس نیست.")
        return

    await state.set_state(BuyStates.waiting_username)
    await state.update_data(plan_id=plan.id)
    if callback.message:
        await callback.message.answer(texts.USERNAME_PROMPT)


@router.message(BuyStates.waiting_username)
async def receive_username(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if message.from_user is None or message.text is None:
        return

    is_valid, normalized_or_reason = validate_username(message.text)
    if not is_valid:
        await message.answer(f"❌ {normalized_or_reason}\n\n{texts.USERNAME_PROMPT}")
        return

    data = await state.get_data()
    plan_id = data.get("plan_id")
    plan = await PlansRepository(session).get(int(plan_id)) if plan_id else None
    user = await UsersRepository(session).get_by_telegram_id(message.from_user.id)

    if plan is None or not plan.is_active or user is None:
        await state.clear()
        await message.answer("سفارش قابل ادامه نیست. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    order_service = OrderService(session, settings)
    order, payment = await order_service.create_order_with_payment(
        user=user,
        plan=plan,
        custom_username=normalized_or_reason,
    )

    await state.clear()
    await message.answer(
        f"""✅ تراکنش شما ایجاد شد

🛒 کد پیگیری: {order.tracking_code}
💵 مبلغ تراکنش به تومان: {format_toman(order.amount)}

💢 لطفاً به این نکات قبل از پرداخت توجه کنید 👇

🔹 تراکنش تا یک ربع اعتبار دارد و پس از آن در صورت پرداخت تایید نخواهد شد.
❌ پس از پرداخت، تایید تراکنش ممکن است 15 دقیقه تا 1 ساعت زمان ببرد.
✅ در صورت مشکل می‌توانید با پشتیبانی در ارتباط باشید.""",
        reply_markup=payment_keyboard(order.id),
    )


@router.callback_query(PaymentCallback.filter())
async def show_payment_info(
    callback: CallbackQuery,
    callback_data: PaymentCallback,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await callback.answer()
    order = await OrdersRepository(session).get_with_details(callback_data.order_id)
    if order is None or callback.from_user is None or order.user.telegram_id != callback.from_user.id:
        await _safe_edit_or_answer(callback, "این سفارش پیدا نشد.")
        return

    order_service = OrderService(session, settings)
    if await order_service.expire_order_if_unpaid(order):
        await _safe_edit_or_answer(callback, texts.EXPIRED_ORDER_TEXT)
        return

    if order.status not in (OrderStatus.PENDING_PAYMENT.value,):
        await _safe_edit_or_answer(callback, "این سفارش قبلاً پردازش شده است.")
        return

    payment = order.payment
    if payment is None:
        await _safe_edit_or_answer(callback, "پرداخت این سفارش پیدا نشد.")
        return

    await state.set_state(BuyStates.waiting_receipt)
    await state.update_data(order_id=order.id, payment_id=payment.id)
    if callback.message:
        await callback.message.answer(
            f"""💳 پرداخت دستی

مبلغ قابل پرداخت:
{format_toman(order.amount)} تومان

شماره کارت:
{escape(settings.payment_card_number) or "ثبت نشده"}

به نام:
{escape(settings.payment_card_holder) or "ثبت نشده"}

بعد از پرداخت، تصویر رسید را همینجا ارسال کنید."""
        )


@router.message(BuyStates.waiting_receipt, F.photo)
async def receive_receipt_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    payment_id = data.get("payment_id")
    order = await OrdersRepository(session).get_with_details(int(order_id)) if order_id else None
    payment = await PaymentsRepository(session).get(int(payment_id)) if payment_id else None

    if order is None or payment is None:
        await state.clear()
        await message.answer("پرداخت پیدا نشد. لطفاً دوباره سفارش ثبت کنید.", reply_markup=main_menu_keyboard())
        return

    order_service = OrderService(session, settings)
    if await order_service.expire_order_if_unpaid(order):
        await state.clear()
        await message.answer(texts.EXPIRED_ORDER_TEXT, reply_markup=main_menu_keyboard())
        return

    receipt_file_id = message.photo[-1].file_id
    await PaymentService(session, VPNPanelService()).attach_receipt(payment, receipt_file_id)
    await state.clear()

    await message.answer("✅ رسید شما دریافت شد و در انتظار تایید ادمین است.")
    await _notify_admins_about_payment(message, settings, payment.id, receipt_file_id, order)


@router.message(BuyStates.waiting_receipt)
async def receive_non_photo_receipt(message: Message) -> None:
    await message.answer("لطفاً تصویر رسید پرداخت را ارسال کنید.")


async def _notify_admins_about_payment(
    message: Message,
    settings: Settings,
    payment_id: int,
    receipt_file_id: str,
    order,
) -> None:
    username = f"@{order.user.telegram_username}" if order.user.telegram_username else "بدون یوزرنیم تلگرام"
    caption = f"""🧾 پرداخت جدید در انتظار تایید

👤 کاربر: {escape(order.user.first_name or "-")} / {escape(username)}
🛒 کد پیگیری: {order.tracking_code}
💵 مبلغ: {format_toman(order.amount)} تومان
⚡ پلن: {escape(order.plan.title)}
🔐 نام کاربری سرویس: {escape(order.custom_username or "-")}"""
    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=receipt_file_id,
                caption=caption,
                reply_markup=payment_review_keyboard(payment_id),
            )
        except Exception:
            await message.bot.send_message(
                chat_id=admin_id,
                text=caption,
                reply_markup=payment_review_keyboard(payment_id),
            )


async def _safe_edit_or_answer(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup)
