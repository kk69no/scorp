"""
Loyalty program, referrals, birthday promos.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards import loyalty_kb, main_menu_kb
from config import (
    LOYALTY_VISIT_POINTS, LOYALTY_REFERRAL_POINTS,
    FREE_HOUR_EVERY_N_VISITS, BIRTHDAY_DISCOUNT_PERCENT,
    VENUE_NAME,
)

router = Router()

TIERS = [
    (0, "🥉 Бронза"),
    (5, "🥈 Серебро"),
    (10, "🥇 Золото"),
    (20, "💎 Платина"),
]


def _get_tier_info(visits: int) -> str:
    tier_name = TIERS[0][1]
    next_info = ""
    for i, (min_v, name) in enumerate(TIERS):
        if visits >= min_v:
            tier_name = name
        else:
            remaining = min_v - visits
            filled = min(int((visits - TIERS[i-1][0]) / (min_v - TIERS[i-1][0]) * 10), 10) if i > 0 else 0
            bar = "█" * filled + "░" * (10 - filled)
            next_info = f"[{bar}] До {name}: ещё {remaining}"
            break
    else:
        next_info = "🏆 Максимальный уровень!"
    return f"{tier_name}\n{next_info}"


@router.message(F.text == "🎁 Бонусы")
async def show_loyalty(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    visits = user["visits_count"]
    points = user["loyalty_points"]
    next_free = FREE_HOUR_EVERY_N_VISITS - (visits % FREE_HOUR_EVERY_N_VISITS)
    if next_free == FREE_HOUR_EVERY_N_VISITS:
        next_free_text = "🎁 Следующий визит — бесплатный час!"
    else:
        next_free_text = f"До бесплатного часа: ещё {next_free} визит(ов)"

    tier_info = _get_tier_info(visits)

    text = (
        f"🎁 Программа лояльности\n"
        f"{'─' * 28}\n\n"
        f"👤 {user['full_name']}\n"
        f"🎟 Реферальный код: {user['referral_code']}\n\n"
        f"{tier_info}\n\n"
        f"📊 Статистика:\n"
        f"  🏆 Визитов: {visits}\n"
        f"  💎 Баллов: {points}\n"
        f"  {next_free_text}\n\n"
        f"📌 Как заработать:\n"
        f"  • +{LOYALTY_VISIT_POINTS} баллов за каждый визит\n"
        f"  • +{LOYALTY_REFERRAL_POINTS} баллов за приглашённого друга\n"
        f"  • Каждый {FREE_HOUR_EVERY_N_VISITS}-й визит — 1 час бесплатно\n"
        f"  • Скидка {BIRTHDAY_DISCOUNT_PERCENT}% в день рождения (±3 дня)\n\n"
        f"📤 Пригласи друга — отправь свой код:"
    )

    await message.answer(text, reply_markup=loyalty_kb(user["referral_code"]))


@router.callback_query(F.data == "loyalty_history")
async def loyalty_history(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    bookings = await db.get_user_bookings(callback.from_user.id, active_only=False)
    completed = [b for b in bookings if b["status"] == "completed"]

    if not completed:
        await callback.answer("Пока нет завершённых визитов", show_alert=True)
        return

    text = "📊 История визитов:\n\n"
    total_spent = 0
    for b in completed[:10]:
        text += f"  📅 {b['booking_date']} | {b['duration_hours']}ч | {b['total_price']}₽\n"
        total_spent += b["total_price"]

    text += f"\n💰 Всего потрачено: {total_spent}₽"
    text += f"\n🏆 Визитов: {user['visits_count']}"

    await callback.message.edit_text(text)
    await callback.answer()
