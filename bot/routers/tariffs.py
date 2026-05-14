from html import escape

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.config_inventory import ConfigInventoryRepository
from app.repositories.plans import PlansRepository
from app.utils.money import format_toman
from bot import texts

router = Router(name="tariffs")


@router.message(F.text == texts.BTN_TARIFFS)
async def tariffs(message: Message, session: AsyncSession) -> None:
    plans = await PlansRepository(session).list_active()
    if not plans:
        await message.answer("در حال حاضر تعرفه فعالی ثبت نشده است.")
        return

    counts = await ConfigInventoryRepository(session).available_counts_for_plans([plan.id for plan in plans])

    lines = ["💰 تعرفه اشتراک‌ها"]
    for index, plan in enumerate(plans, start=1):
        available_count = counts.get(plan.id, 0)
        stock_status = "✅ وضعیت: موجود" if available_count > 0 else "❌ وضعیت: ناموجود"
        lines.append(
            f"""
{index}. {escape(plan.title)}
📦 حجم: {plan.volume_gb} گیگ
🗓 مدت اعتبار: {plan.duration_days} روز
💵 قیمت: {format_toman(plan.price)} تومان
{stock_status}"""
        )
        if plan.description:
            lines.append(f"📝 توضیحات: {escape(plan.description)}")

    lines.append("\nبرای خرید، از گزینه «🔐 خرید اشتراک» استفاده کنید.")
    await message.answer("\n".join(lines))
