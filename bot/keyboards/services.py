from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import VPNService


class ServiceActionCallback(CallbackData, prefix="svc"):
    action: str
    service_id: int


def services_actions_keyboard(services: list[VPNService]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in services:
        builder.button(
            text=f"🔗 لینک اشتراک {service.username}",
            callback_data=ServiceActionCallback(action="link", service_id=service.id),
        )
        builder.button(
            text=f"📊 وضعیت {service.username}",
            callback_data=ServiceActionCallback(action="status", service_id=service.id),
        )
        builder.button(
            text=f"♻️ تمدید {service.username}",
            callback_data=ServiceActionCallback(action="renew", service_id=service.id),
        )
    builder.adjust(1)
    return builder.as_markup()
