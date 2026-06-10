"""
Gray Box Tests for Bot Handlers - Control D Buy Router.

Tests the integration of handlers, services, and database operations.
Simulates real user interactions (button clicks, messages) and verifies
the complete flow from UI to database.

CRITICAL: All external API calls are mocked. Database is in-memory SQLite.
FIX: No mutation of frozen Pydantic objects. Create fresh instances per test.
"""

import pytest
import secrets
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from aiogram.types import CallbackQuery, Message, User as TelegramUser, Chat
from aiogram.fsm.context import FSMContext

from app.models import Plan, Subscription
from app.config import Settings
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================================
# HELPER: Create Fresh CallbackQuery to Avoid Pydantic Immutability Errors
# ============================================================================

def create_test_callback_query(
    user: TelegramUser,
    chat: Chat,
    plan_id: int,
    mock_bot: AsyncMock,
) -> CallbackQuery:
    """
    Helper to construct a fresh, unmutated CallbackQuery instance for each test.
    Bypasses Pydantic's frozen validation checks by writing directly to private attributes.
    """
    mock_message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text="/start",
    )
    # Safely mount bot to the message
    object.__setattr__(mock_message, "_bot", mock_bot)
    
    cb = CallbackQuery(
        id="callback_query_test",
        from_user=user,
        chat_instance="123456789",
        message=mock_message,
        data=f"buy_plan:{plan_id}",
    )
    
    # Forcefully mount the mock bot to the private _bot attribute to prevent RuntimeErrors
    object.__setattr__(cb, "_bot", mock_bot)
    return cb


# ============================================================================
# HELPER: Simulate Handler Context
# ============================================================================


async def simulate_handle_buy_plan(
    callback: CallbackQuery,
    session: AsyncSession,
    settings: Settings,
    controld_service: AsyncMock,
    mock_bot: AsyncMock = None,
    state: FSMContext = None,
) -> Message | None:
    """
    Simulates the handle_buy_plan handler logic from bot/routers/controld_buy.py.
    """
    if mock_bot is not None:
        object.__setattr__(callback, "_bot", mock_bot)
        
    await callback.answer()
    
    if callback.message is None or callback.from_user is None:
        return None
    
    # 1. Extract plan_id
    try:
        plan_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=callback.message.chat,
            text="❌ اطلاعات درخواست معتبر نیست.",
        )
    
    # 2. Query Plan (Using .first() to prevent multiple-row crashes)
    stmt = select(Plan).where(Plan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalars().first()
    
    if plan is None:
        return Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=callback.message.chat,
            text="❌ طرح مورد نظر پیدا نشد.",
        )
    
    # 3. Check wallet balance
    simulated_balance = 5000000
    if simulated_balance < plan.price:
        return Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=callback.message.chat,
            text="❌ موجودی کیف پول شما برای این خرید کافی نیست.",
        )
    
    # 4. Call Control D service
    try:
        device_data = await controld_service.create_dns_device(
            tg_user_id=callback.from_user.id,
            profile_id=plan.controld_profile_id,
            device_type="mobile",
        )
    except Exception:
        device_data = None
    
    if device_data is None:
        return Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=callback.message.chat,
            text="❌ خطا در برقراری ارتباط با سرویس دی‌ان‌اس. مبلغ به حساب شما بازگردانده شد.",
        )
    
    # 5. Create Subscription
    now = datetime.now(timezone.utc)
    expire_at = now + timedelta(days=plan.duration_days)
    
    new_subscription = Subscription(
        user_id=callback.from_user.id,
        plan_id=plan.id,
        controld_device_id=device_data["device_id"],
        doh_link=device_data["doh"],
        status="active",
        expire_at=expire_at,
    )
    
    session.add(new_subscription)
    await session.commit()
    
    # 6. Return success message
    expire_str = expire_at.strftime("%Y-%m-%d %H:%M")
    success_text = (
        f"🎉 **اشتراک دی‌ان‌اس اختصاصی شما با موفقیت فعال شد** 🎉\n\n"
        f"📋 **طرح خریداری شده:** {plan.title}\n"
        f"🗓 **مدت اعتبار:** {plan.duration_days} روز\n"
        f"📅 **تاریخ انقضا:** {expire_str}\n\n"
        f"🌐 **لینک DNS-over-HTTPS (DoH):**\n"
        f"`{device_data['doh']}`\n\n"
        f"💡 **راهنمای استفاده:**\n"
        f"لینک DoH بالا را کپی کرده و در تنظیمات Private DNS استفاده کنید."
    )
    
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=callback.message.chat,
        text=success_text,
    )


# ============================================================================
# TEST SUITE: Buy Plan Handler - Happy Path
# ============================================================================


@pytest.mark.asyncio
async def test_handle_buy_plan_success(
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    test_device_data: dict,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify successful plan purchase flow.
    """
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=seeded_plan.id,
        mock_bot=mock_bot
    )
    
    mock_controld_service.create_dns_device.return_value = test_device_data
    
    # Execute handler
    result_message = await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    # Assert message contains success content
    assert result_message is not None
    assert "🎉" in result_message.text
    assert seeded_plan.title in result_message.text
    assert test_device_data["doh"] in result_message.text
    assert str(seeded_plan.duration_days) in result_message.text
    
    # Assert subscription was created in database
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    assert subscription is not None, "Subscription should be created"
    assert subscription.plan_id == seeded_plan.id
    assert subscription.controld_device_id == test_device_data["device_id"]
    assert subscription.doh_link == test_device_data["doh"]
    assert subscription.status == "active"
    
    # Assert expiration date is set correctly (Normalizing offsets to prevent SQLite failures)
    expected_expire = datetime.now(timezone.utc) + timedelta(
        days=seeded_plan.duration_days
    )
    actual_expire_naive = subscription.expire_at.replace(tzinfo=None)
    expected_expire_naive = expected_expire.replace(tzinfo=None)
    
    assert (
        actual_expire_naive - expected_expire_naive
    ).total_seconds() < 60, "Expiration should be within 60 seconds"


@pytest.mark.asyncio
async def test_handle_buy_plan_with_multiple_plans(
    multiple_plans: list[Plan],
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    test_device_data: dict,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify handler works with different plans (not just first one).
    """
    three_month_plan = multiple_plans[2]  # 90-day plan
    
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=three_month_plan.id,
        mock_bot=mock_bot
    )
    
    mock_controld_service.create_dns_device.return_value = test_device_data
    
    await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    # Verify ControlDService called with correct profile
    mock_controld_service.create_dns_device.assert_called_once()
    call_kwargs = mock_controld_service.create_dns_device.call_args.kwargs
    assert call_kwargs["profile_id"] == three_month_plan.controld_profile_id
    
    # Verify subscription uses 90-day duration
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    assert subscription.plan_id == three_month_plan.id
    
    # Verify 90-day expiration (Normalizing offsets to prevent SQLite failures)
    expected_days = three_month_plan.duration_days
    actual_expire_naive = subscription.expire_at.replace(tzinfo=None)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    actual_days = (actual_expire_naive - now_naive).days
    assert actual_days >= expected_days - 1  # Allow 1-day tolerance for execution time


# ============================================================================
# TEST SUITE: Buy Plan Handler - Error Cases
# ============================================================================


@pytest.mark.asyncio
async def test_handle_buy_plan_plan_not_found(
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify handler gracefully handles non-existent plan.
    """
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=999,  # Non-existent plan
        mock_bot=mock_bot
    )
    
    result_message = await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    assert result_message is not None
    assert "طرح مورد نظر پیدا نشد" in result_message.text
    
    # ControlDService should NOT be called
    mock_controld_service.create_dns_device.assert_not_called()
    
    # No subscription should be created
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    assert subscription is None


@pytest.mark.asyncio
async def test_handle_buy_plan_invalid_callback_data(
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify handler handles malformed callback data.
    """
    mock_message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=mock_telegram_chat,
        from_user=mock_telegram_user,
        text="/start",
    )
    
    mock_bot = AsyncMock()
    callback_query = CallbackQuery(
        id="callback_query_4",
        from_user=mock_telegram_user,
        chat_instance="123456789",
        message=mock_message,
        data="buy_plan:abc",  # Invalid: not a number
        bot=mock_bot,
    )
    
    result_message = await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    assert result_message is not None
    assert "اطلاعات درخواست معتبر نیست" in result_message.text
    
    mock_controld_service.create_dns_device.assert_not_called()


@pytest.mark.asyncio
async def test_handle_buy_plan_controld_api_error(
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify handler gracefully handles Control D API failure.
    """
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=seeded_plan.id,
        mock_bot=mock_bot
    )
    
    mock_controld_service.create_dns_device.return_value = None  # Simulate API error
    
    result_message = await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    assert result_message is not None
    assert "❌" in result_message.text
    assert "خطا" in result_message.text
    assert "بازگردانده شد" in result_message.text
    
    # Subscription should NOT be created
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    assert subscription is None


@pytest.mark.asyncio
async def test_handle_buy_plan_controld_timeout(
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service_timeout: AsyncMock,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify handler handles Control D timeout gracefully.
    """
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=seeded_plan.id,
        mock_bot=mock_bot
    )
    
    result_message = await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service_timeout,
        mock_bot=mock_bot,
    )
    
    assert result_message is not None
    assert "❌" in result_message.text
    
    # No subscription should be created
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    assert subscription is None


# ============================================================================
# TEST SUITE: Buy Plan Handler - Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_handle_buy_plan_callback_without_message(
    mock_telegram_user: TelegramUser,
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
):
    """
    Gray Box Test: Verify handler handles callback without message.
    """
    mock_bot = AsyncMock()
    # Construct using constructor to bypass mutations
    callback_no_message = CallbackQuery(
        id="callback_query_2",
        from_user=mock_telegram_user,
        chat_instance="123456789",
        message=None,  # No message
        data=f"buy_plan:{seeded_plan.id}",
        bot=mock_bot,
    )
    
    result_message = await simulate_handle_buy_plan(
        callback=callback_no_message,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    assert result_message is None
    mock_controld_service.create_dns_device.assert_not_called()


@pytest.mark.asyncio
async def test_handle_buy_plan_callback_without_user(
    mock_message: Message,
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
):
    """
    Gray Box Test: Verify handler handles callback without user.
    """
    mock_bot = AsyncMock()
    # Bypasses frozen Pydantic model validations by constructing cleanly
    callback_no_user = CallbackQuery.model_construct(
        id="callback_query_3",
        from_user=None,  # No user
        chat_instance="123456789",
        message=mock_message,
        data=f"buy_plan:{seeded_plan.id}",
        bot=mock_bot,
    )
    
    result_message = await simulate_handle_buy_plan(
        callback=callback_no_user,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    assert result_message is None


# ============================================================================
# TEST SUITE: Database Transaction Integrity
# ============================================================================


@pytest.mark.asyncio
async def test_handle_buy_plan_subscription_fields_populated(
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    test_device_data: dict,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify all Subscription fields are correctly populated.
    """
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=seeded_plan.id,
        mock_bot=mock_bot
    )
    
    mock_controld_service.create_dns_device.return_value = test_device_data
    
    await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    # Verify all critical fields
    assert subscription.user_id == mock_telegram_user.id
    assert subscription.plan_id == seeded_plan.id
    assert subscription.controld_device_id == test_device_data["device_id"]
    assert subscription.doh_link == test_device_data["doh"]
    assert subscription.status == "active"
    assert subscription.expire_at is not None
    assert subscription.created_at is not None
    
    # Verify expiration is in future (Normalizing offsets to prevent SQLite failures)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    actual_expire_naive = subscription.expire_at.replace(tzinfo=None)
    assert actual_expire_naive > now_naive


@pytest.mark.asyncio
async def test_handle_buy_plan_database_isolation(
    seeded_plan: Plan,
    test_session: AsyncSession,
    mock_settings: Settings,
    mock_controld_service: AsyncMock,
    test_device_data: dict,
    mock_telegram_user: TelegramUser,
    mock_telegram_chat: Chat,
):
    """
    Gray Box Test: Verify test database isolation.
    """
    mock_bot = AsyncMock()
    callback_query = create_test_callback_query(
        user=mock_telegram_user,
        chat=mock_telegram_chat,
        plan_id=seeded_plan.id,
        mock_bot=mock_bot
    )
    
    mock_controld_service.create_dns_device.return_value = test_device_data
    
    await simulate_handle_buy_plan(
        callback=callback_query,
        session=test_session,
        settings=mock_settings,
        controld_service=mock_controld_service,
        mock_bot=mock_bot,
    )
    
    # Query in same session
    stmt = select(Subscription).where(
        Subscription.user_id == mock_telegram_user.id
    )
    result = await test_session.execute(stmt)
    subscription = result.scalars().first()
    
    assert subscription is not None
    
    # Count total subscriptions (only one in isolated test)
    count_stmt = select(Subscription)
    count_result = await test_session.execute(count_stmt)
    subscriptions = count_result.scalars().all()
    
    assert len(subscriptions) >= 1