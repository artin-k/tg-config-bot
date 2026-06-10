# Open bot/routers/tariffs.py
from html import escape

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.plans import PlansRepository
from app.utils.money import format_toman
from bot import texts

router = Router(name="tariffs")


@router.message(F.text == texts.BTN_TARIFFS)
async def tariffs(message: Message, session: AsyncSession) -> None:
    # 1. Fetch active DNS plans
    plans = await PlansRepository(session).list_active()
    if not plans:
        await message.answer("در حال حاضر تعرفه فعالی ثبت نشده است.")
        return

    lines = ["💰 تعرفه اشتراک‌های DNS"]
    for index, plan in enumerate(plans, start=1):
        # 2. Rebranded to support dynamic, unlimited DNS provisioning (Always Available)
        stock_status = "✅ وضعیت: فعال و آماده تحویل"
        lines.append(
            f"""
{index}. {escape(plan.title)}
🗓 مدت اعتبار: {plan.duration_days} روز
💵 قیمت: {format_toman(plan.price)} تومان
{stock_status}"""
        )
        if plan.description:
            lines.append(f"📝 توضیحات: {escape(plan.description)}")

    lines.append("\nبرای خرید، از گزینه «🔐 خرید اشتراک DNS» استفاده کنید.")
    await message.answer("\n".join(lines))