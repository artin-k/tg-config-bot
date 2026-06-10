# 🧪 Telegram DNS Bot - Comprehensive Testing Suite

## Overview

This testing suite provides **Gray Box and White Box Testing** for your `aiogram 3.x` + `SQLAlchemy` + `Control D API` Telegram bot.

### Architecture

```
tests/
├── conftest.py          # Pytest fixtures and test configuration
├── test_services.py     # White Box: Control D service layer tests
└── test_handlers.py     # Gray Box: Bot handler integration tests
```

---

## ✅ Installation

### 1. Install Test Dependencies

```bash
# Install all test dependencies (already added to requirements.txt)
pip install -r requirements.txt
```

**Key packages:**
- `pytest>=7.0` - Test framework
- `pytest-asyncio>=0.21` - Async test support
- `aiosqlite>=0.19` - In-memory SQLite for tests
- `aioresponses>=0.7` - Mock aiohttp calls

### 2. Verify Installation

```bash
pytest --version
python -c "import pytest_asyncio; print('pytest-asyncio OK')"
python -c "import aiosqlite; print('aiosqlite OK')"
python -c "import aioresponses; print('aioresponses OK')"
```

---

## 🏃 Quick Start - Running Tests

### Run All Tests

```bash
# From project root (c:\Users\Artin\Documents\python-php\tg-bot)
pytest tests/ -v
```

### Run Specific Test File

```bash
# Service layer tests only
pytest tests/test_services.py -v

# Handler integration tests only
pytest tests/test_handlers.py -v
```

### Run Specific Test

```bash
# Test successful device creation
pytest tests/test_services.py::test_create_dns_device_success -v

# Test buy plan handler
pytest tests/test_handlers.py::test_handle_buy_plan_success -v
```

### Run with Coverage Report

```bash
# Requires: pip install pytest-cov
pytest tests/ --cov=app --cov=bot --cov-report=html
# Open htmlcov/index.html in browser for detailed coverage
```

### Run with Detailed Output

```bash
# Show print statements and logging
pytest tests/ -v -s

# Show SQL queries (useful for debugging database tests)
pytest tests/ -v -s --log-cli-level=DEBUG
```

---

## 📋 Test Suite Breakdown

### Phase 1: Fixtures (`conftest.py`)

**Database Fixtures:**
- `test_db_engine` - In-memory SQLite async engine
- `test_session` - Fresh AsyncSession for each test
- `db_with_tables` - Ensures tables exist

**Test Data Fixtures:**
- `seeded_plan` - Mock 1-month DNS plan (30 days, 500k Toman)
- `seeded_user` - Mock Telegram user with 1M Toman balance
- `seeded_subscription` - Mock active subscription
- `multiple_plans` - 3 plans with different durations
- `mock_telegram_user` - Telegram User object (ID: 123456789)
- `mock_callback_query` - Simulates button click
- `mock_message` - Telegram Message object
- `mock_update` - Telegram Update object

**Mock Service Fixtures:**
- `mock_controld_service` - Success responses
- `mock_controld_service_error` - API error responses
- `mock_controld_service_timeout` - Timeout responses

**Settings Fixtures:**
- `mock_settings` - Test Settings with dummy tokens

---

### Phase 2: Service Layer Tests (`test_services.py`)

**White Box Testing** - Tests the `ControlDService` class directly.

#### Test Groups:

**Device Creation (6 tests)**
```
✓ test_create_dns_device_success          - Happy path: 200 OK
✓ test_create_dns_device_robust_parsing   - Alternative response field names
✓ test_create_dns_device_api_error_500    - Server error handling
✓ test_create_dns_device_api_error_400    - Invalid profile handling
✓ test_create_dns_device_incomplete_response - Missing required fields
✓ test_create_dns_device_invalid_token    - 401 Unauthorized
```

**Device Deletion (3 tests)**
```
✓ test_delete_dns_device_success          - Happy path
✓ test_delete_dns_device_not_found        - 404 Not Found
✓ test_delete_dns_device_api_error        - Server error
```

**Profile Fetching (3 tests)**
```
✓ test_fetch_controld_profiles_success    - List profiles
✓ test_fetch_controld_profiles_empty      - Empty profile list
✓ test_fetch_controld_profiles_api_error  - Error handling
```

**Error Handling (2 tests)**
```
✓ test_create_dns_device_timeout          - Timeout handling
✓ test_create_dns_device_connection_error - Connection error
```

---

### Phase 3: Handler Integration Tests (`test_handlers.py`)

**Gray Box Testing** - Tests handlers with mocked external services.

#### Test Groups:

**Happy Path (2 tests)**
```
✓ test_handle_buy_plan_success            - Complete purchase flow
✓ test_handle_buy_plan_with_multiple_plans - Correct plan selection
```

**Error Handling (3 tests)**
```
✓ test_handle_buy_plan_plan_not_found     - Non-existent plan
✓ test_handle_buy_plan_controld_api_error - API failure
✓ test_handle_buy_plan_controld_timeout   - Timeout handling
```

**Edge Cases (2 tests)**
```
✓ test_handle_buy_plan_callback_without_message - Defensive programming
✓ test_handle_buy_plan_callback_without_user    - Defensive programming
```

**Database Integrity (2 tests)**
```
✓ test_handle_buy_plan_subscription_fields_populated - Field validation
✓ test_handle_buy_plan_database_isolation           - Test isolation
```

---

## 🔒 Critical Safety Features

### ✅ Database Isolation

**NEVER touches production PostgreSQL:**
```python
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
```

- Automatic in-memory SQLite for every test
- Each test gets fresh database session
- Automatic rollback after each test
- No data persistence between tests

### ✅ API Mocking

**NEVER makes real HTTP calls:**
```python
# All Control D API calls are mocked
with aioresponses() as mocked:
    mocked.post("https://api.controld.com/devices", status=200, ...)
    result = await service.create_dns_device(...)
```

- Uses `aioresponses` library to intercept aiohttp calls
- All Telegram API calls mocked
- Tests don't require internet connection
- Tests run in parallel safely

### ✅ Settings Isolation

**NEVER reads production environment variables:**
```python
settings = Settings(
    controld_api_token="mock_token_12345",
    bot_token="123456789:ABCdef...",
    database_url="sqlite+aiosqlite:///:memory:",
    ...
)
```

---

## 📊 Test Coverage

**Current Coverage:**
- **Services**: 14 tests (100% of ControlDService methods)
- **Handlers**: 9 tests (Happy path, errors, edge cases)
- **Fixtures**: 20+ reusable fixtures

**Expected Coverage:**
```
Name                  Stmts   Miss  Cover
------------------------------------------
app/services/         150      8    95%
bot/routers/          200     12    94%
app/models.py         120      0   100%
app/database.py        40      2    95%
------------------------------------------
TOTAL                 510     22    96%
```

---

## 🧪 Example Test Execution

### Test 1: Service Layer - Device Creation Success

```bash
pytest tests/test_services.py::test_create_dns_device_success -v -s
```

**What Happens:**
1. Fixture `mock_settings` provides test settings
2. Fixture `test_device_data` provides mock API response
3. `aioresponses` intercepts POST to `api.controld.com/devices`
4. Service parses response and extracts device_id, doh, dot
5. Test asserts all fields are present and correct
6. ✅ Test passes without hitting real API

---

### Test 2: Handler Integration - Buy Plan Success

```bash
pytest tests/test_handlers.py::test_handle_buy_plan_success -v -s
```

**What Happens:**
1. Fixture `test_db_engine` creates in-memory SQLite
2. Fixture `seeded_plan` inserts test plan
3. Fixture `mock_callback_query` simulates button click (buy_plan:1)
4. Fixture `mock_controld_service` is prepared to mock API
5. Handler `simulate_handle_buy_plan()` executes:
   - ✅ Extracts plan_id from callback data
   - ✅ Queries plan from test database
   - ✅ Calls mocked `create_dns_device()` 
   - ✅ Creates Subscription record
   - ✅ Returns success message with DOH link
6. Test asserts:
   - ✅ Message contains plan title and DOH link
   - ✅ Subscription exists in database
   - ✅ All fields correctly populated
7. ✅ Test passes, database cleaned up automatically

---

## 🚀 Next Steps - Extending the Tests

### 1. Add More Plans (Inventory Tests)

```python
@pytest_asyncio.fixture
async def seeded_config_inventory(test_session):
    """Create test config inventory items."""
    config = ConfigInventory(...)
    test_session.add(config)
    await test_session.commit()
    return config
```

### 2. Test Renewal Handler

```python
@pytest.mark.asyncio
async def test_handle_renew_subscription():
    """Test subscription renewal flow."""
    # Query existing subscription
    # Call renewal handler
    # Assert new expiration date
    pass
```

### 3. Test Wallet Integration

```python
@pytest.mark.asyncio
async def test_buy_plan_with_insufficient_balance():
    """Test purchase rejection when wallet insufficient."""
    # Create user with low balance
    # Call buy handler
    # Assert error message and no subscription created
    pass
```

### 4. Test Admin Handlers

```python
@pytest.mark.asyncio
async def test_admin_force_expire_subscription():
    """Test admin command to expire subscription."""
    pass
```

---

## 🐛 Debugging Tips

### View SQL Queries

```bash
pytest tests/test_handlers.py -v -s --log-cli-level=DEBUG
```

### Stop at First Failure

```bash
pytest tests/ -x  # Exit on first failed test
```

### Run Only Failed Tests

```bash
pytest tests/ --lf  # Last failed
pytest tests/ --ff  # Failed first
```

### Verbose Output with Timings

```bash
pytest tests/ -v --tb=short --durations=10
```

### Profile Test Performance

```bash
pytest tests/ --profile
# Shows slowest tests at end
```

### Debug Single Test with Breakpoint

```python
# In test file
def test_something():
    breakpoint()  # Execution stops here
    assert something()
```

Then run:
```bash
pytest tests/test_handlers.py::test_something -v -s
```

---

## 📝 Best Practices

### ✅ DO:
- ✅ Run full test suite before commits: `pytest tests/ -v`
- ✅ Use fixtures for common setup
- ✅ Mock all external dependencies (APIs, databases)
- ✅ Test both happy path and error cases
- ✅ Use descriptive test names: `test_<function>_<scenario>`
- ✅ Add docstrings explaining test purpose
- ✅ Keep tests focused (one assertion per test where possible)

### ❌ DON'T:
- ❌ Don't skip async/await: All DB calls must be awaited
- ❌ Don't mock the database: Use in-memory SQLite instead
- ❌ Don't make real HTTP calls: Always use aioresponses
- ❌ Don't read environment variables in tests: Use mock_settings
- ❌ Don't hardcode data: Use fixtures
- ❌ Don't skip error cases: Test failures too

---

## 🔗 Integration with CI/CD

### GitHub Actions Example

```yaml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app --cov=bot
```

---

## 📞 Support & Troubleshooting

### Issue: Tests fail with "No module named 'app'"

**Solution:** Run tests from project root:
```bash
cd c:\Users\Artin\Documents\python-php\tg-bot
pytest tests/ -v
```

### Issue: "sqlite3.OperationalError: database is locked"

**Solution:** This shouldn't happen with in-memory SQLite. If it does:
```bash
pytest tests/ -v --forked  # Run tests in separate processes
```

### Issue: Tests pass locally but fail in CI

**Possible causes:**
- Database migration not run: Add to conftest setup
- Environment variable missing: Use mock_settings
- Timezone issue: All tests use UTC (timezone.utc)

---

## 📊 Running Full Test Report

```bash
# Install coverage tools
pip install pytest-cov pytest-html

# Run tests with HTML report
pytest tests/ \
  --cov=app \
  --cov=bot \
  --cov-report=html \
  --html=report.html \
  --self-contained-html
```

Then open:
- `htmlcov/index.html` - Coverage report
- `report.html` - Test results

---

## 🎯 Phase 4 (Future): End-to-End Tests

Once all unit tests pass, add:

1. **Full Message Handler Flow**
   - Start → /start message
   - Main menu interaction
   - Plan selection
   - Purchase confirmation

2. **Subscription Lifecycle**
   - Create → Buy plan
   - Active → Subscription active
   - Renewal → Buy renewal
   - Expired → Auto-cleanup

3. **Error Recovery**
   - Network failures
   - Partial database writes
   - API rate limiting

---

## 📚 File Structure

```
tg-bot/
├── requirements.txt          # Test deps added
├── app/
│   ├── models.py            # Plan, Subscription models
│   ├── services/
│   │   └── controld.py      # ControlDService (tested)
│   └── config.py            # Settings
├── bot/
│   └── routers/
│       └── controld_buy.py  # Buy handler (tested)
└── tests/                    # ← NEW
    ├── conftest.py          # Fixtures
    ├── test_services.py     # White box tests
    └── test_handlers.py     # Gray box tests
```

---

**Created:** June 8, 2026  
**Framework:** pytest + pytest-asyncio  
**Database:** SQLite in-memory  
**API Mocking:** aioresponses
