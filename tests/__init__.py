"""
Comprehensive test suite for Telegram DNS Bot (aiogram 3.x + SQLAlchemy + Control D API).

This package provides Gray Box and White Box testing across:
- Service layer (Control D API integration)
- Handler layer (Telegram bot callbacks)
- Database operations (SQLAlchemy ORM)

All tests use:
- In-memory SQLite (sqlite+aiosqlite:///:memory:) for database isolation
- aioresponses for mocking aiohttp calls (Control D API)
- pytest + pytest-asyncio for async test execution

Database: NEVER touches production PostgreSQL
API Calls: NEVER makes real HTTP requests to Control D or Telegram
Settings: NEVER reads production environment variables

Run tests:
    pytest tests/ -v              # All tests
    pytest tests/test_services.py # Service layer only
    pytest tests/test_handlers.py # Handlers only
"""
