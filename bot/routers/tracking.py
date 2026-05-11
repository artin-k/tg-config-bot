from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import OrderStatus
from app.repositories.orders import OrdersRepository
from app.repositories.users import UsersRepository
from app.services.order_service import OrderService
from app.services.order_status import order_kind_label, order_status_label
from app.utils.money import format_toman
from bot import texts
from bot.keyboards.main_menu import main_menu_keyboard
from bot.states.tracking import TrackingStates

router = Router(name="tracking")


@router.message(F.text == texts.BTN_TRACK_ORDER)
async def ask_tracking_code(message: Message, state: FSMContext) -> None:
    await state.set_state(TrackingStates.waiting_code)
    await message.answer("لطفاً کد پیگیری سفارش خود را ارسال کنید:")


@router.message(TrackingStates.waiting_code)
async def receive_tracking_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if message.from_user is None or not message.text:
        return
    if message.text in {texts.BTN_BACK, texts.BTN_MAIN_MENU}:
        await state.clear()
        await message.answer(texts.MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
        return

    user = await UsersRepository(session).get_by_telegram_id(message.from_user.id)
    if user is None:
        await state.clear()
        await message.answer("ابتدا /start را ارسال کنید.", reply_markup=main_menu_keyboard())
        return

    tracking_code = message.text.strip()
    order = await OrdersRepository(session).get_by_tracking_code_for_user(tracking_code, user.id)
    if order is None:
        await message.answer("❌ سفارشی با این کد پیگیری برای حساب شما پیدا نشد.")
        return

    if order.status == OrderStatus.PENDING_PAYMENT.value:
        await OrderService(session, settings).expire_order_if_unpaid(order)

    await state.clear()
    await message.answer(_format_order_tracking(order), reply_markup=main_menu_keyboard())


def _format_order_tracking(order) -> str:
    tehran = ZoneInfo("Asia/Tehran")
    created_at = order.created_at.astimezone(tehran).strftime("%Y-%m-%d %H:%M")
    expires_at = order.expires_at.astimezone(tehran).strftime("%Y-%m-%d %H:%M") if order.expires_at else "-"
    extra_message = _extra_message(order.status)

    return f"""📦 وضعیت سفارش شما

🛒 کد پیگیری: {order.tracking_code}
⚡ نوع سفارش: {order_kind_label(order.order_kind)}
📌 وضعیت: {order_status_label(order.status)}
💵 مبلغ: {format_toman(order.amount)} تومان
🗓 تاریخ ثبت: {created_at}
⏳ مهلت پرداخت: {expires_at if order.status == OrderStatus.PENDING_PAYMENT.value else "-"}

{extra_message}"""


def _extra_message(status: str) -> str:
    if status == OrderStatus.PENDING_PAYMENT.value:
        return "برای ادامه، پرداخت را انجام دهید و رسید را ارسال کنید."
    if status == OrderStatus.COMPLETED.value:
        return "سفارش شما با موفقیت تکمیل شده است."
    if status == OrderStatus.EXPIRED.value:
        return "مهلت پرداخت این سفارش به پایان رسیده است."
    if status == OrderStatus.FAILED.value:
        return "این سفارش ناموفق بوده است. برای بررسی بیشتر با پشتیبانی در ارتباط باشید."
    return ""
