# Open tests/conftest.py
import pytest
import pytest_asyncio
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from aiogram.types import Update, CallbackQuery, Message, User as TelegramUser, Chat
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from app.models import Base, Plan, Subscription, User
from app.config import Settings


# ============================================================================
# ENVIRONMENTAL ISOLATION FIXTURES (CRITICAL)
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def mock_env_vars():
    """
    Forcefully mocks sensitive environment variables before any tests run.
    This prevents Pydantic from reading live token strings from .env or OS environment.
    """
    mock_env = {
        "BOT_TOKEN": "mock_bot_token_12345",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "CONTROLD_API_TOKEN": "mock_controld_token_12345",
        "CONTROLD_PROFILE_ID": "mock_profile_12345",
        "REDIS_URL": "",
        "FSM_STORAGE": "memory",
        "ADMIN_IDS": "123456789",
    }
    with patch.dict(os.environ, mock_env, clear=False):
        yield


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def test_db_engine():
    """
    Create an in-memory SQLite async engine for testing.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_db_engine):
    """
    Provide a fresh AsyncSession for each test.
    """
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def db_with_tables(test_db_engine):
    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return test_db_engine


# ============================================================================
# SETTINGS FIXTURES (Removed Pydantic annotations from return signature)
# ============================================================================

@pytest.fixture
def mock_settings():
    """
    Provide mock Settings with safe defaults for testing.
    """
    settings = Settings()
    
    # Forcefully overwrite properties to ensure 100% test isolation
    settings.bot_token = "mock_bot_token_12345"
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.controld_api_token = "mock_controld_token_12345"
    settings.controld_profile_id = "mock_profile_12345"
    settings.redis_url = None
    settings.fsm_storage = "memory"
    settings.admin_ids_raw = ""
    settings.root_admin_telegram_id = None
    settings.owner_commission_percent = 10.0
    settings.referral_commission_percent = 0.0
    settings.commission_base = "final_amount"
    settings.affiliate_default_to_root = True
    settings.dice_win_discount_percent = 10
    settings.dice_cooldown_hours = 24
    settings.dice_discount_expire_hours = 72
    settings.allow_placeholder_configs = False
    settings.config_low_stock_threshold = 3
    settings.wallet_min_withdraw_amount = 100000
    settings.wallet_max_withdraw_amount = 0
    
    return settings


# ============================================================================
# TELEGRAM OBJECT FIXTURES
# ============================================================================

@pytest.fixture
def mock_telegram_user():
    return TelegramUser(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="fa",
    )


@pytest.fixture
def mock_telegram_chat():
    return Chat(
        id=123456789,
        type="private",
        first_name="Test",
        last_name="User",
        username="testuser",
    )


@pytest.fixture
def mock_message(mock_telegram_user, mock_telegram_chat):
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=mock_telegram_chat,
        from_user=mock_telegram_user,
        text="/start",
    )


@pytest.fixture
def mock_callback_query(mock_telegram_user, mock_message):
    cb = CallbackQuery(
        id="callback_query_1",
        from_user=mock_telegram_user,
        chat_instance="123456789",
        message=mock_message,
        data="buy_plan:1",
    )
    cb.bot = AsyncMock()  # Mount default mock bot to avoid RuntimeErrors
    return cb


@pytest.fixture
def mock_update(mock_callback_query):
    return Update(
        update_id=1,
        callback_query=mock_callback_query,
    )


@pytest.fixture
def mock_fsm_context():
    storage = MemoryStorage()
    return FSMContext(storage=storage, key=("123456789", 123456789))


# ============================================================================
# DATABASE SEEDING FIXTURES (FIXED: Uses .flush() instead of .commit())
# ============================================================================

@pytest_asyncio.fixture
async def seeded_plan(test_session):
    plan = Plan(
        title="پلن یک ماهه",
        description="اشتراک DNS اختصاصی برای 1 ماه",
        duration_days=30,
        volume_gb=1000,
        price=500000,
        is_active=True,
        sort_order=1,
        controld_profile_id="mock_profile_12345",
    )
    test_session.add(plan)
    await test_session.flush()  # Flushes the SQL to SQLite without closing transaction
    await test_session.refresh(plan)
    return plan


@pytest_asyncio.fixture
async def seeded_user(test_session, mock_telegram_user):
    user = User(
        telegram_id=mock_telegram_user.id,
        telegram_username=mock_telegram_user.username,
        first_name=mock_telegram_user.first_name,
        phone_number="+989123456789",
        is_phone_verified=True,
        verified_at=datetime.now(timezone.utc),
        wallet_balance=1000000,
        referral_code="test_referral_123",
        referral_depth=0,
        is_admin=False,
        is_root_admin=False,
        affiliate_enabled=True,
        affiliate_balance=0,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seeded_subscription(
    test_session, seeded_user, seeded_plan
):
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=seeded_user.telegram_id,
        plan_id=seeded_plan.id,
        controld_device_id="device_pk_mock_12345",
        doh_link="https://dns.example.com/dns-query",
        status="active",
        expire_at=now + timedelta(days=30),
    )
    test_session.add(subscription)
    await test_session.flush()
    await test_session.refresh(subscription)
    return subscription


@pytest_asyncio.fixture
async def multiple_plans(test_session):
    plans = [
        Plan(
            title="پلن هفتگی",
            description="اشتراک DNS اختصاصی برای 1 هفته",
            duration_days=7,
            volume_gb=500,
            price=250000,
            is_active=True,
            sort_order=1,
            controld_profile_id="mock_profile_weekly",
        ),
        Plan(
            title="پلن ماهانه",
            description="اشتراک DNS اختصاصی برای 1 ماه",
            duration_days=30,
            volume_gb=1000,
            price=500000,
            is_active=True,
            sort_order=2,
            controld_profile_id="mock_profile_monthly",
        ),
        Plan(
            title="پلن سه ماهه",
            description="اشتراک DNS اختصاصی برای 3 ماه",
            duration_days=90,
            volume_gb=3000,
            price=1200000,
            is_active=True,
            sort_order=3,
            controld_profile_id="mock_profile_quarterly",
        ),
    ]
    test_session.add_all(plans)
    await test_session.flush()
    for plan in plans:
        await test_session.refresh(plan)
    return plans


# ============================================================================
# CONTROL D SERVICE MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_controld_service():
    service = AsyncMock()
    service.create_dns_device = AsyncMock(
        return_value={
            "device_id": "device_pk_mock_12345",
            "doh": "https://dns.controld.com/dns-query?token=abc123",
            "dot": "dns.controld.com",
        }
    )
    service.delete_dns_device = AsyncMock(return_value=True)
    service.fetch_controld_profiles = AsyncMock(
        return_value=[
            {
                "id": "mock_profile_12345",
                "name": "Default Profile",
                "description": "Test profile",
            }
        ]
    )
    service.create_device = AsyncMock(
        return_value={
            "device_id": "device_pk_mock_12345",
            "doh": "https://dns.controld.com/dns-query?token=abc123",
        }
    )
    service.delete_device = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_controld_service_error():
    service = AsyncMock()
    service.create_dns_device = AsyncMock(return_value=None)
    service.delete_dns_device = AsyncMock(return_value=False)
    service.fetch_controld_profiles = AsyncMock(return_value=None)
    service.create_device = AsyncMock(return_value=None)
    service.delete_device = AsyncMock(return_value=False)
    return service


@pytest.fixture
def mock_controld_service_timeout():
    service = AsyncMock()
    service.create_dns_device = AsyncMock(
        side_effect=TimeoutError("Control D request timed out")
    )
    service.create_device = AsyncMock(
        side_effect=TimeoutError("Control D request timed out")
    )
    return service


@pytest.fixture
def patch_controld_service(mock_controld_service):
    with patch(
        "app.services.controld.ControlDService",
        return_value=mock_controld_service,
    ):
        yield mock_controld_service


@pytest.fixture
def patch_settings(mock_settings):
    with patch(
        "app.config.get_settings",
        return_value=mock_settings,
    ):
        yield mock_settings


# ============================================================================
# HELPER FIXTURES
# ============================================================================

@pytest.fixture
def test_device_data() -> dict:
    return {
        "device_id": "device_pk_abc123def456",
        "doh": "https://dns.controld.com/dns-query?token=xyz789",
        "dot": "dns-over-tls.controld.com",
    }


@pytest.fixture
def test_controld_error_response() -> dict:
    return {
        "error": "Invalid profile_id",
        "status": 400,
        "message": "The specified profile does not exist",
    }


@pytest.fixture
def test_controld_timeout_response() -> dict:
    return {
        "error": "Request timeout",
        "status": 504,
        "message": "Gateway timeout - Control D service unavailable",
    }


@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.get_event_loop_policy()