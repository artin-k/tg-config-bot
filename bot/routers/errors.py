import traceback

import structlog
from aiogram import Router
from aiogram.types import ErrorEvent

router = Router(name="errors")
logger = structlog.get_logger(__name__)


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    logger.error(
        "unhandled_update_error",
        exception=repr(event.exception),
        traceback="".join(
            traceback.format_exception(
                type(event.exception),
                event.exception,
                event.exception.__traceback__,
            )
        ),
    )
    return True
