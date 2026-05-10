import logging

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.config import Settings
from app.database import async_session_maker
from bot.middlewares.db import DbSessionMiddleware
from bot.routers import admin, buy, common, errors, services, start, support, tariffs


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    storage = (
        RedisStorage.from_url(settings.redis_url)
        if settings.fsm_storage == "redis" and settings.redis_url
        else MemoryStorage()
    )
    dp = Dispatcher(storage=storage, settings=settings)
    db_middleware = DbSessionMiddleware(async_session_maker)
    dp.update.middleware(db_middleware)

    dp.include_router(errors.router)
    dp.include_router(start.router)
    dp.include_router(buy.router)
    dp.include_router(services.router)
    dp.include_router(tariffs.router)
    dp.include_router(support.router)
    dp.include_router(admin.router)
    dp.include_router(common.router)
    return dp
