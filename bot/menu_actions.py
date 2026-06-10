from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Order, OrderKind, OrderStatus, User, VPNService
from app.repositories.dice_rolls import DiceRollsRepository
from app.repositories.orders import OrdersRepository
from app.repositories.plans import PlansRepository
from app.repositories.services import ServicesRepository
from app.repositories.test_accounts import TestAccountsRepository
from app.repositories.users import UsersRepository
from app.services.order_service import OrderService
from app.services.affiliate_service import AffiliateService
from app.services.settings_service import AppSettingsService
from app.utils.admin_access import is_user_admin
from app.utils.codes import generate_discount_code
from app.utils.formatting import (
    format_datetime,
    format_money,
    format_order_status_fa,
    format_order_type_fa,
    format_remaining_time,
    format_service_status_fa,
)
from bot import texts
from bot.keyboards.buy import plans_keyboard
from bot.keyboards.main_menu import account_dashboard_keyboard, buy_renew_menu_keyboard, features_menu_keyboard, main_menu_keyboard
from bot.keyboards.renewal import renewal_services_keyboard
from bot.keyboards.services import services_actions_keyboard
from bot.keyboards.tracking import orders_tracking_keyboard
from bot.keyboards.tutorials import tutorials_keyboard
from bot.keyboards.verification import phone_verification_keyboard
from bot.keyboards.wallet import wallet_keyboard
from bot.states.wallet import VerificationStates


async def show_main_menu(
    message: Message,
    session: AsyncSession | None = None,
    settings: Settings | None = None,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user) if session is not None else None
    await message.answer(
        texts.MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(is_admin=bool(settings and is_user_admin(user, settings))),
    )


async def show_buy_renew_menu(message: Message) -> None:
    await message.answer(
        "🛒 خرید اشتراک DNS\n\nبرای خرید اشتراک جدید، گزینه خرید را انتخاب کنید.\n\nتوجه: در این نسخه تمدید مستقیم اشتراک با اضافه کردن زمان انجام می‌شود.",
        reply_markup=buy_renew_menu_keyboard(),
    )


async def show_features_menu(message: Message) -> None:
    await message.answer(
        "🧭 منوی امکانات\n\nامکانات تکمیلی ربات از این بخش در دسترس است:",
        reply_markup=features_menu_keyboard(),
    )


# Open bot/menu_actions.py
# Find and update your show_account_dashboard function:

async def show_account_dashboard(
    message: Message,
    session: AsyncSession,
    settings: Settings | None = None,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user)
    if user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    direct_referrals = await UsersRepository(session).count_referrals(user.id)
    active_services_count = len(await ServicesRepository(session).list_active_by_user(user.id))
    recent_orders_count = await OrdersRepository(session).count_by_user(user.id)

    # --- FIXED: Use the database verification status instead of hardcoded 'True' ---
    await message.answer(
        f"""👤 حساب کاربری شما

🆔 آیدی عددی: {user.telegram_id}
🏦 موجودی کیف پول: {format_money(user.wallet_balance)} تومان
👥 دعوت مستقیم: {direct_referrals}
🛍 دستگاه‌های فعال (DNS): {active_services_count}
📦 سفارش‌های اخیر: {recent_orders_count}""",
        reply_markup=account_dashboard_keyboard(phone_verified=user.is_phone_verified),
    )


# In bot/menu_actions.py

async def show_buy_plans(message: Message, session: AsyncSession) -> None:
    # 1. Fetch active DNS plans
    plans = await PlansRepository(session).list_active()
    if not plans:
        await message.answer("در حال حاضر پلن فعالی برای خرید وجود ندارد.", reply_markup=main_menu_keyboard())
        return

    # 2. Bypass inventory checks since DNS has unlimited stock
    counts = {plan.id: 9999 for plan in plans}
    text = texts.BUY_PLANS_TEXT
    
    await message.answer(text, reply_markup=plans_keyboard(plans, counts))


async def show_renewal_services(message: Message, session: AsyncSession) -> None:
    await show_renewal_disabled(message, session)


async def show_renewal_disabled(message: Message, session: AsyncSession | None = None) -> None:
    await message.answer(
        "♻️ تمدید مستقیم اشتراک در حال حاضر فعال نیست.\n\nبرای ادامه استفاده، لطفاً از بخش «خرید اشتراک» یک سرویس جدید تهیه کنید.",
        reply_markup=buy_renew_menu_keyboard(),
    )

async def show_my_services(
    message: Message,
    session: AsyncSession,
    settings: Settings | None = None,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user)
    if user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    services = await ServicesRepository(session).list_by_user(user.id)
    if not services:
        await message.answer("شما هنوز سرویس فعالی ندارید.", reply_markup=main_menu_keyboard())
        return

    lines = ["🛍 اشتراک‌های DNS فعال شما"]
    for index, service in enumerate(services, start=1):
        lines.append(format_service_summary(service, index))

    await message.answer("\n".join(lines), reply_markup=services_actions_keyboard(services))


async def show_tariffs(message: Message, session: AsyncSession) -> None:
    plans = await PlansRepository(session).list_active()
    if not plans:
        await message.answer("در حال حاضر تعرفه فعالی ثبت نشده است.", reply_markup=main_menu_keyboard())
        return

    lines = ["💰 تعرفه اشتراک‌های DNS"]
    for index, plan in enumerate(plans, start=1):
        lines.append(
            f"""
{index}. {escape(plan.title)}
🗓 مدت اعتبار: {plan.duration_days} روز
💵 قیمت: {format_money(plan.price)} تومان"""
        )
        if plan.description:
            lines.append(f"📝 توضیحات: {escape(plan.description)}")

    lines.append("\nبرای خرید، از گزینه «🔐 خرید اشتراک» استفاده کنید.")
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())


async def show_order_tracking(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user)
    if user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    orders = await OrdersRepository(session).list_by_user(user.id)
    order_service = OrderService(session, settings)
    for order in orders:
        if order.status == OrderStatus.PENDING_PAYMENT.value:
            await order_service.expire_order_if_unpaid(order)

    if not orders:
        await message.answer(
            "شما هنوز سفارشی ثبت نکرده‌اید.",
            reply_markup=orders_tracking_keyboard([], include_search=True),
        )
        return

    lines = ["📦 سفارش‌های شما", "آخرین سفارش‌ها به ترتیب جدیدترین:"]
    for index, order in enumerate(orders, start=1):
        lines.append(format_order_summary(order, index))

    await message.answer("\n".join(lines), reply_markup=orders_tracking_keyboard(orders))


async def show_referral(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    telegram_user: TelegramUser | None = None,
) -> None:
    telegram_user = telegram_user or message.from_user
    if telegram_user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    user = await _get_or_create_user_from_telegram_user(telegram_user, session, settings)

    affiliate = AffiliateService(session, settings)
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or "bot"
    stats = await affiliate.referral_page_stats(user)

    direct_reward_line = (
        f"پاداش مستقیم کاربران: {settings.referral_commission_percent:g}٪ از خرید موفق"
        if settings.referral_commission_percent > 0
        else "در حال حاضر پاداش مستقیم کاربران فعال نیست، اما دعوت‌های شما در سیستم ثبت و قابل پیگیری است."
    )
    footer = (
        "برای گزارش کامل از /admin بخش مدیریت زیرمجموعه‌ها استفاده کنید."
        if user.is_root_admin
        else direct_reward_line
    )

    await message.answer(
        f"""👥 زیرمجموعه‌گیری و معرفین

با دعوت دوستان خود می‌توانید تخفیف و پاداش دریافت کنید.

🔗 لینک دعوت اختصاصی شما:
https://t.me/{bot_username}?start={user.referral_code}

👤 تعداد دعوت مستقیم: {stats["direct_count"]}
🛒 خریدهای موفق زیرمجموعه‌ها: {stats["successful_referral_orders"]}
💰 پاداش کل: {format_money(stats["total_commission"])} تومان
⏳ پاداش تسویه‌نشده: {format_money(stats["unpaid_commission"])} تومان

{footer}""",
        reply_markup=main_menu_keyboard(is_admin=is_user_admin(user, settings)),
    )


async def show_tutorials(message: Message) -> None:
    await message.answer(
        """📚 بخش آموزش

لطفاً سیستم‌عامل مورد نظر خود را برای اتصال به DNS انتخاب کنید:""",
        reply_markup=tutorials_keyboard(),
    )


async def show_support(message: Message, session: AsyncSession) -> None:
    support_username = await AppSettingsService(session).get_support_username()
    support_text = f"@{escape(support_username)}" if support_username else "ثبت نشده"
    await message.answer(
        f"""☎️ پشتیبانی

برای ارتباط با پشتیبانی به آیدی زیر پیام دهید:
{support_text}""",
        reply_markup=main_menu_keyboard(),
    )


async def show_wallet(
    message: Message,
    session: AsyncSession,
    state: FSMContext | None = None,
    settings: Settings | None = None,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user)
    if user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    await message.answer(
        f"""🏦 کیف پول شما

💵 موجودی فعلی: {format_money(user.wallet_balance)} تومان

لطفاً یکی از گزینه‌های زیر را انتخاب کنید:""",
        reply_markup=wallet_keyboard(),
    )


async def show_test_account(
    message: Message,
    session: AsyncSession,
    settings: Settings | None = None,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user)
    if user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    repo = TestAccountsRepository(session)
    existing_claim = await repo.get_user_claim(user.id)
    if existing_claim is not None:
        account = existing_claim.test_account
        await message.answer(
            f"""شما قبلاً دی‌ان‌اس تست دریافت کرده‌اید.

🔑 {escape(account.title)}

🌐 دی‌ان‌اس DoH:
{escape(account.config_link)}"""
            + (f"\n\n🔒 دی‌ان‌اس DoT:\n{escape(account.subscription_link)}" if account.subscription_link else ""),
            reply_markup=main_menu_keyboard(),
        )
        return

    account = await repo.get_available()
    if account is None:
        await message.answer("در حال حاضر دی‌ان‌اس تستی موجود نیست.", reply_markup=main_menu_keyboard())
        return

    await repo.create_claim(user_id=user.id, test_account=account)
    await session.commit()
    text = f"""🔑 دی‌ان‌اس تست شما آماده است

{escape(account.title)}

⏳ مدت تست: {account.duration_hours} ساعت

🌐 دی‌ان‌اس DoH (HTTPS):
{escape(account.config_link)}"""
    if account.subscription_link:
        text += f"\n\n🔒 دی‌ان‌اس DoT (TLS):\n{escape(account.subscription_link)}"
    await message.answer(text, reply_markup=main_menu_keyboard())


async def show_lucky_wheel(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    telegram_user: TelegramUser | None = None,
) -> None:
    user = await _get_current_or_create_user(message, session, settings, telegram_user)
    if user is None:
        await message.answer("امکان شناسایی حساب تلگرام شما وجود ندارد. لطفاً دوباره تلاش کنید.", reply_markup=main_menu_keyboard())
        return

    now = datetime.now(timezone.utc)
    repo = DiceRollsRepository(session)
    last_roll = await repo.get_last_by_user(user.id)
    if last_roll is not None:
        created_at = last_roll.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        next_roll_at = created_at + timedelta(hours=settings.dice_cooldown_hours)
        if now < next_roll_at:
            remaining = int((next_roll_at - now).total_seconds())
            await message.answer(
                f"""شما امروز شانس خود را امتحان کرده‌اید.

⏳ زمان باقی‌مانده تا تلاش بعدی: {format_remaining_time(remaining)}""",
                reply_markup=main_menu_keyboard(),
            )
            return

    await message.answer("🎲 تاس را می‌اندازیم...\nاگر عدد ۶ بیاورید، تخفیف هدیه می‌گیرید!")
    dice_message = await message.answer_dice(emoji="🎲")
    value = dice_message.dice.value if dice_message.dice else 1
    won = value == 6

    discount_code = None
    expires_at = None
    discount_percent = 0
    if won:
        discount_percent = settings.dice_win_discount_percent
        expires_at = now + timedelta(hours=settings.dice_discount_expire_hours)
        discount_code = await _generate_unique_discount_code(repo)

    await repo.create(
        user_id=user.id,
        dice_value=value,
        won=won,
        discount_percent=discount_percent,
        discount_code=discount_code,
        expires_at=expires_at,
    )
    await session.commit()

    if won and discount_code:
        await message.answer(
            f"""🎉 تبریک! عدد ۶ آوردید.

🎁 تخفیف شما: {discount_percent}٪
🎟 کد تخفیف: {discount_code}
⏳ اعتبار کد: {format_datetime(expires_at)}

در هنگام خرید می‌توانید از این کد استفاده کنید.""",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        f"""متأسفانه این بار برنده نشدید.
عدد شما: {value}

فردا دوباره شانس خود را امتحان کنید 🍀""",
        reply_markup=main_menu_keyboard(),
    )


async def show_coming_soon(message: Message) -> None:
    await message.answer(texts.COMING_SOON_TEXT, reply_markup=main_menu_keyboard())


def format_service_summary(service: VPNService, index: int | None = None) -> str:
    prefix = f"\n{index}. " if index is not None else ""
    return f"""{prefix}{escape(service.username)}
⚡ پلن: {escape(service.plan.title if service.plan else "-")}
🗓 تاریخ انقضا: {format_datetime(service.expire_at)}
📌 وضعیت: {format_service_status_fa(service.status)}
🌐 دی‌ان‌اس DoH: `{escape(service.config_link or "-")}`
🔒 دی‌ان‌اس DoT: `{escape(service.subscription_link or "-")}`"""


def format_order_summary(order: Order, index: int | None = None) -> str:
    prefix = f"\n{index}. " if index is not None else "\n"
    lines = [
        f"{prefix}کد پیگیری: {order.tracking_code}",
        f"⚡ نوع سفارش: {format_order_type_fa(order.order_kind)}",
        f"⚡ پلن: {escape(order.plan.title if order.plan else '-')}",
        f"💵 مبلغ: {format_money(order.amount)} تومان",
        f"📌 وضعیت: {format_order_status_fa(order.status)}",
        f"🗓 تاریخ ثبت: {format_datetime(order.created_at)}",
    ]
    if order.status == OrderStatus.PENDING_PAYMENT.value:
        lines.append(f"⏳ مهلت پرداخت: {format_datetime(order.expires_at)}")
    return "\n".join(lines)


def format_order_detail(order: Order) -> str:
    service_username = order.custom_username or "-"
    if order.order_kind == OrderKind.RENEWAL.value and order.renewal_service:
        service_username = order.renewal_service.username

    receipt_status = "دریافت شده" if order.payment and order.payment.receipt_file_id else "ارسال نشده"
    lines = [
        "📦 جزئیات سفارش",
        "",
        f"🛒 کد پیگیری: {order.tracking_code}",
        f"⚡ نوع سفارش: {format_order_type_fa(order.order_kind)}",
        f"⚡ پلن: {escape(order.plan.title if order.plan else '-')}",
        f"💵 مبلغ: {format_money(order.amount)} تومان",
        f"📌 وضعیت سفارش: {format_order_status_fa(order.status)}",
        f"📎 وضعیت رسید: {receipt_status}",
        f"🔐 نام دستگاه: {escape(service_username)}",
        f"🗓 تاریخ ثبت: {format_datetime(order.created_at)}",
    ]
    if order.status == OrderStatus.PENDING_PAYMENT.value:
        lines.append(f"⏳ مهلت پرداخت: {format_datetime(order.expires_at)}")
    if order.paid_at:
        lines.append(f"💳 تاریخ پرداخت: {format_datetime(order.paid_at)}")
    if order.completed_at:
        lines.append(f"✅ تاریخ تکمیل: {format_datetime(order.completed_at)}")
    return "\n".join(lines)


async def _get_current_user(message: Message, session: AsyncSession):
    if message.from_user is None:
        return None
    return await UsersRepository(session).get_by_telegram_id(message.from_user.id)


async def _get_current_or_create_user(
    message: Message,
    session: AsyncSession,
    settings: Settings | None = None,
    telegram_user: TelegramUser | None = None,
) -> User | None:
    actual_user = telegram_user or message.from_user
    if actual_user is None:
        return None
    repo = UsersRepository(session)
    user = await repo.get_by_telegram_id(actual_user.id)
    if user is not None:
        return user
    return await _get_or_create_user_from_telegram_user(actual_user, session, settings or get_settings())


async def get_or_create_user_from_message(message: Message, session: AsyncSession) -> User:
    if message.from_user is None:
        raise ValueError("message.from_user is required")
    return await _get_or_create_user_from_telegram_user(message.from_user, session, get_settings())


async def _get_or_create_user_from_telegram_user(
    telegram_user: TelegramUser,
    session: AsyncSession,
    settings: Settings,
) -> User:
    try:
        user = await UsersRepository(session).create_or_update_from_telegram(
            telegram_id=telegram_user.id,
            telegram_username=telegram_user.username,
            first_name=telegram_user.first_name,
            is_admin=telegram_user.id in settings.admin_ids,
            is_root_admin=settings.root_admin_telegram_id == telegram_user.id,
        )
        if settings.root_admin_telegram_id == telegram_user.id:
            user = await AffiliateService(session, settings).ensure_root_owner() or user
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return user


async def _generate_unique_discount_code(repo: DiceRollsRepository) -> str:
    for _ in range(10):
        code = generate_discount_code()
        if await repo.get_by_discount_code(code) is None:
            return code
    raise RuntimeError("Could not generate unique discount code")