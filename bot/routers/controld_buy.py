# Open bot/routers/controld_buy.py
import secrets
from datetime import datetime, timezone, timedelta
from html import escape  # Safe escape utility
import structlog
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Plan, VPNService
from app.repositories.plans import PlansRepository
from app.repositories.users import UsersRepository
from app.services.controld import create_dns_device, ControlDService  # Client integrations
from bot import texts

logger = structlog.get_logger(__name__)
router = Router(name="controld_buy")


# ============================================================================
# TASK 1: MAIN PLANS MENU (With Custom Formatting)
# ============================================================================

@router.message(F.text == texts.BTN_BUY)
@router.callback_query(F.data == "menu:buy", StateFilter("*"))
async def show_dns_plans_menu(
    event: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    user_id = event.from_user.id if event.from_user else 0
    user = await UsersRepository(session).get_by_telegram_id(user_id) if user_id else None
    
    # Enforce Phone Verification
    if user is None or not user.is_phone_verified:
        from bot.keyboards.verification import phone_verification_keyboard
        from bot.states.wallet import VerificationStates
        await state.set_state(VerificationStates.waiting_contact)
        await state.update_data(next_section="buy")
        
        prompt_text = "⚠️ برای خرید اشتراک DNS، ابتدا باید شماره موبایل خود را تایید کنید.\n\nلطفاً دکمه زیر را بزنید تا شماره تماس شما ارسال شود 👇"
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.answer(prompt_text, reply_markup=phone_verification_keyboard())
        else:
            await event.answer(prompt_text, reply_markup=phone_verification_keyboard())
        return

    if isinstance(event, CallbackQuery):
        await event.answer()

    # Query plans
    plans = await PlansRepository(session).list_active()
    if not plans:
        msg = "در حال حاضر پلن فعالی برای خرید وجود ندارد."
        if isinstance(event, CallbackQuery):
            await event.message.answer(msg)
        else:
            await event.answer(msg)
        return

    # Build builder matching UI design specifications
    builder = InlineKeyboardBuilder()
    for plan in plans:
        # Format the price with commas
        formatted_price = f"{plan.price:,}"
        
        # --- FIXED: Only show Plan Title and Formatted Price ---
        builder.button(
            text=f"🔹 {plan.title} - {formatted_price} تومان 🔹",
            callback_data=f"buy_plan:{plan.id}"
        )
        # --------------------------------------------------------
        
    builder.button(text="🎁 دریافت اکانت تست (۲ ساعته) 🆓", callback_data="get_test_account")
    builder.button(text=texts.BTN_BACK, callback_data="menu:main")
    builder.adjust(1)
    
    main_text = (
        "لطفا یکی از پلن‌های زیر را انتخاب کنید:\n\n"
        "در صورتی که قبلا یک پلن فعال داشته باشید و پلن جدید خریداری کنید ، "
        "مدت زمان پلن جدید به پلن قبلی شما اضافه خواهد شد\n\n"
        "در صورت تمدید پلن، بخاطر انتخاب مجدد شما 10 درصد تخفیف بصورت دائمی "
        "بصورت اتوماتیک برای شما در نظر گرفته می‌شود!"
    )
    
    if isinstance(event, CallbackQuery):
        await event.message.answer(main_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await event.answer(main_text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ============================================================================
# TASK 2: BUY PLAN WITH TIME ACCUMULATION & AUTO-DISCOUNTS
# ============================================================================

# Open bot/routers/controld_buy.py

@router.callback_query(F.data.startswith("buy_plan:"), StateFilter("*"))
async def handle_buy_plan(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    await callback.answer()
    
    if callback.message is None or callback.from_user is None:
        return

    try:
        plan_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.answer("❌ اطلاعات درخواست معتبر نیست.")
        return

    # Query Plan (strictly using .first() over .one_or_none())
    stmt = select(Plan).where(Plan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalars().first()

    if plan is None:
        await callback.message.answer("❌ طرح مورد نظر پیدا نشد.")
        return

    # Check if the user already has an active DNS subscription to apply renewals / discounts
    active_stmt = select(VPNService).where(
        VPNService.user_id == callback.from_user.id,
        VPNService.status == "active"
    )
    active_result = await session.execute(active_stmt)
    current_sub = active_result.scalars().first()

    # Calculate price applying the automatic 10% discount for renewals
    final_price = plan.price
    discount_text = ""
    if current_sub is not None:
        discount_amount = int(plan.price * 0.1)
        final_price = plan.price - discount_amount
        discount_text = f" (تخفیف ۱۰٪ تمدید: {discount_amount:,} تومان)"

    # Simulated wallet balance check (Mock Step)
    simulated_balance = 5000000
    if simulated_balance < final_price:
        await callback.message.answer(f"❌ موجودی کیف پول شما کافی نیست. قیمت طرح: {final_price:,} تومان")
        return

    await callback.message.answer("⚙️ در حال پردازش تراکنش و فعال‌سازی اشتراک دی‌ان‌اس...")

    now = datetime.now(timezone.utc)

    if current_sub is None:
        # --- SCENARIO 1: NO ACTIVE SUB EXISTS - Create new device ---
        expire_at = now + timedelta(hours=plan.duration_hours)
        random_hex = secrets.token_hex(4)
        unique_device_name = f"tg_user_{callback.from_user.id}_{random_hex}"

        # Provision device via Control D
        device_data = await create_dns_device(
            tg_user_id=callback.from_user.id,
            profile_id=plan.controld_profile_id,
            duration_hours=plan.duration_hours,
            device_type="mobile",
            device_name=unique_device_name
        )

        if device_data is None:
            await callback.message.answer("❌ خطا در برقراری ارتباط با سرورهای دی‌ان‌اس.")
            return

        device_id = device_data["device_id"]
        doh_link = device_data["doh"]
        dot_link = device_data["dot"]
        
        # --- NEW: Extract Advanced Parameters ---
        resolver_id = device_data.get("resolver_id") or device_id
        stamp = device_data.get("stamp") or "ثبت نشده"
        # ----------------------------------------

        # Create Subscription record
        new_subscription = VPNService(
            user_id=callback.from_user.id,
            plan_id=plan.id,
            controld_device_id=device_id,
            config_link=doh_link,
            subscription_link=dot_link,
            username=unique_device_name,
            expire_at=expire_at,
            status="active"
        )
        session.add(new_subscription)
        
    else:
        # --- SCENARIO 2: ACTIVE SUB EXISTS - Accumulate time and update existing device ---
        current_expire = current_sub.expire_at
        if current_expire.tzinfo is None:
            current_expire = current_expire.replace(timezone.utc)

        # Append duration hours to the current subscription's expiry [1]
        expire_at = current_expire + timedelta(hours=plan.duration_hours)
        current_sub.expire_at = expire_at
        current_sub.plan_id = plan.id  # Update plan mapping

        # Call ControlD API to update existing device's disable_ttl [1]
        new_disable_ttl = int(expire_at.timestamp())
        controld_service = ControlDService(settings)
        
        success = await controld_service.update_device(
            device_id=current_sub.controld_device_id,
            disable_ttl=new_disable_ttl
        )

        if not success:
            await callback.message.answer("❌ خطا در تمدید اشتراک در سرورهای Control D.")
            return

        # Reuse existing links for success display
        device_id = current_sub.controld_device_id
        doh_link = current_sub.config_link
        dot_link = current_sub.subscription_link

    await session.commit()
    await state.clear()

    # Format Expiration Timestamp using Jalali/Shamsi safely
    try:
        import jdatetime
        from zoneinfo import ZoneInfo
        tehran_tz = ZoneInfo("Asia/Tehran")
        tehran_expire = expire_at.astimezone(tehran_tz)
        shamsi_expire = jdatetime.datetime.fromgregorian(datetime=tehran_expire)
        expire_str = shamsi_expire.strftime("%Y/%m/%d - %H:%M")
    except ImportError:
        from zoneinfo import ZoneInfo
        tehran_tz = ZoneInfo("Asia/Tehran")
        expire_str = expire_at.astimezone(tehran_tz).strftime("%Y-%m-%d %H:%M")

    # Format Success Messages
    if current_sub is not None:
        success_text = (
            f"🎉 **اشتراک دی‌ان‌اس شما با موفقیت تمدید شد** 🎉\n\n"
            f"📋 **طرح تمدید شده:** {escape(plan.title)}{discount_text}\n"
            f"⏳ **مدت زمان افزوده شده:** {plan.duration_hours} ساعت\n"
            f"📅 **تاریخ انقضای جدید:** {expire_str} (تهران)\n\n"
            f"🌐 **لینک DNS-over-HTTPS (DoH) شما (بدون تغییر):**\n"
            f"<code>{doh_link}</code>\n\n"
            f"🔒 **آدرس DNS-over-TLS (DoT):**\n"
            f"<code>{dot_link}</code>\n\n"
            f"💡 زمان جدید به اشتراک قبلی شما افزوده شد."
        )
    else:
        # --- FIXED: Use the redesigned Advanced Endpoints HTML template ---
        success_text = f"""✅ <b>اشتراک شما با موفقیت ساخته شد!</b>

👤 <b>نام سرویس:</b> <code>{escape(unique_device_name)}</code>
🗓 <b>اعتبار:</b> {plan.duration_hours} ساعت
📅 <b>تاریخ انقضا:</b> {expire_str} (تهران)

🔐 <b>SECURE DNS (Encrypted)</b>

🆔 <b>Resolver ID:</b>
<code>{resolver_id}</code>

🌐 <b>DNS-over-HTTPS/3:</b>
<code>{doh_link}</code>

🔒 <b>DNS-over-TLS/DoQ:</b>
<code>{dot_link}</code>

🖥 <b>Bootstrap IPs:</b>
<code>76.76.2.22</code> | <code>2606:1a40::22</code>

🔗 <b>DNS Stamp:</b>
<code>{stamp}</code>

⚠️ <i>جهت استفاده در برنامه‌هایی مانند v2rayNG، NekoBox یا Hiddify از DNS Stamp یا لینک‌های فوق استفاده کنید.</i>"""
    
    await callback.message.answer(success_text, parse_mode="HTML")


# ============================================================================
# TASK 3: THE TEST ACCOUNT (FREE TRIAL) FLOW (With Dynamic List Builder)
# ============================================================================

@router.callback_query(F.data == "get_test_account", StateFilter("*"))  # <-- Forcefully catches the click regardless of active FSM states [1]
async def handle_get_test_account(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """
    Handles the one-time 2-hour free trial request.
    Enforces anti-abuse database guards and deploys a time-limited device to Control D [1].
    """
    if callback.message is None or callback.from_user is None:
        return

    # 1. Fetch user safely from database
    user = await UsersRepository(session).get_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.message.answer("ابتدا /start را ارسال کنید.")
        await callback.answer()
        return

    # 2. Strict Anti-Abuse DB Check (Preferring .first() over .one_or_none() as per rules) [1]
    stmt = select(VPNService).where(
        VPNService.user_id == user.id,
        VPNService.is_test_account == True
    )
    result = await session.execute(stmt)
    existing_test = result.scalars().first()

    if existing_test is not None:
        # Alert the user and halt execution [1]
        await callback.answer("❌ شما قبلا از اکانت تست استفاده کرده‌اید.", show_alert=True)
        return

    # Stop the inline button loading spinner [1]
    await callback.answer()

    # 3. Retrieve default trial profile ID from settings
    profile_id = settings.controld_profile_id
    if not profile_id:
        await callback.message.answer("❌ تنظیمات اکانت تست از طرف مدیریت کامل نیست.")
        return

    await callback.message.answer("⚙️ در حال ساخت دی‌ان‌اس تست ۲ ساعته شما...")

    # Generate unique device identifier to prevent Control D name collisions [1]
    random_hex = secrets.token_hex(4)
    unique_device_name = f"tg_test_{user.telegram_id}_{random_hex}"

    # 4. Call Control D API with a 2-hour duration parameter (enforcing TTL) [1]
    controld_service = ControlDService(settings)
    device_data = await controld_service.create_dns_device(
        tg_user_id=user.telegram_id,
        profile_id=profile_id,
        duration_hours=2,  # Enforces 2 Hours TTL on Control D server
        device_name=unique_device_name
    )

    if device_data is None:
        await callback.message.answer("❌ خطا در برقراری ارتباط با سرورهای Control D. لطفاً مجدداً تلاش کنید.")
        return

    now = datetime.now(timezone.utc)
    expire_at = now + timedelta(hours=2)

    # 5. Save the test Subscription to PostgreSQL [1]
    new_test_sub = VPNService(
        user_id=user.id,
        plan_id=None,  # No plan linked for free trial
        controld_device_id=device_data["device_id"],
        config_link=device_data["doh"],
        subscription_link=device_data["dot"],
        username=unique_device_name,
        expire_at=expire_at,
        status="active",
        is_test_account=True  # Mark true to prevent any duplication abuse [1]
    )
    session.add(new_test_sub)
    await session.commit()
    await state.clear()

    # Fallbacks for Legacy IPs (Parsed successfully from Task 1) [1]
    ipv4_address = device_data.get("ipv4")
    ipv6_address = device_data.get("ipv6")

    # --- FIXED: Use dynamic list builder for test success card ---
    msg_lines = [
        "✅ <b>اکانت تست ۲ ساعته شما فعال شد!</b>\n",
        f"👤 <b>نام سرویس:</b> <code>{escape(unique_device_name)}</code>",
        "🗓 <b>اعتبار:</b> ۲ ساعت\n",
        "🌐 <b>لینک‌های اتصال هوشمند:</b>",
        f"<b>DoH:</b> <code>{device_data['doh']}</code>",
        f"<b>DoT:</b> <code>{device_data['dot']}</code>"
    ]

    # Build the legacy section dynamically
    legacy_lines = []
    if ipv4_address and ipv4_address != "ثبت نشده":
        legacy_lines.append(f"<b>IPv4:</b> <code>{ipv4_address}</code>")
    if ipv6_address and ipv6_address != "ثبت نشده":
        legacy_lines.append(f"<b>IPv6:</b> <code>{ipv6_address}</code>")

    # Only add the legacy header if we actually have at least one IP
    if legacy_lines:
        msg_lines.append("\n🖥 <b>تنظیمات کلاسیک:</b>")
        msg_lines.extend(legacy_lines)
        
        if ipv4_address:
            msg_lines.append(
                "\n⚠️ <i>توجه: برای استفاده از IPv4، آی‌پی شبکه شما باید در سیستم ثبت شده باشد. "
                "لینک‌های DoH/DoT نیازی به ثبت آی‌پی دارند.</i>"
            )

    # Add the final warning
    msg_lines.append("\n⚠️ <i>این اکانت به صورت خودکار پس از ۲ ساعت غیرفعال خواهد شد.</i>")

    # Join it all together safely
    final_message = "\n".join(msg_lines)
    
    await callback.message.answer(final_message, parse_mode="HTML")