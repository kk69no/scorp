"""
Venue info: about, prices, games, hookah menu, food, location.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from keyboards import showcase_kb, main_menu_kb
from config import (
    VENUE_NAME, VENUE_ADDRESS, VENUE_PHONE, VENUE_INSTAGRAM,
    VENUE_DESCRIPTION, PRICE_PER_HOUR, PRICE_FULL_DAY,
    WORK_HOURS_START, WORK_HOURS_END, MIN_BOOKING_HOURS,
    EXTRAS_HOOKAH,
    PS5_GAMES, MAX_CAPACITY, CONSOLES, DELIVERY_NOTE,
    VENUE_LATITUDE, VENUE_LONGITUDE,
)

router = Router()


@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
    consoles_text = ", ".join(CONSOLES)
    text = (
        f"🏠 {VENUE_NAME}\n"
        f"{'─' * 28}\n\n"
        f"{VENUE_DESCRIPTION}\n\n"
        f"📍 {VENUE_ADDRESS}\n"
        f"📱 {VENUE_PHONE}\n"
        f"📸 Instagram: {VENUE_INSTAGRAM}\n\n"
        f"🕐 Режим работы:\n"
        f"  Ежедневно {WORK_HOURS_START}:00 — {WORK_HOURS_END:02d}:00\n\n"
        f"🎮 Консоли: {consoles_text}\n"
        f"👥 Вместимость: до {MAX_CAPACITY} человек\n\n"
        f"Выбери раздел для подробностей 👇"
    )
    await message.answer(text, reply_markup=showcase_kb())


# ─── Price list ──────────────────────────────────────────

@router.callback_query(F.data == "show:price")
async def show_price(callback: CallbackQuery):
    text = (
        f"💰 Прайс-лист {VENUE_NAME}\n"
        f"{'─' * 28}\n\n"
        f"🏠 Аренда комнаты:\n"
        f"  • {PRICE_PER_HOUR:,}₽ / час\n"
        f"  • 🌟 Сутки — {PRICE_FULL_DAY:,}₽\n"
        f"  • Минимум: {MIN_BOOKING_HOURS} часа\n\n"
    )

    if EXTRAS_HOOKAH:
        text += "🔥 Кальян:\n"
        for name, price in EXTRAS_HOOKAH.items():
            text += f"  • {name}: {price}₽\n"
        text += "\n"

    text += (
        f"🍕 Еда и напитки:\n"
        f"  {DELIVERY_NOTE}\n\n"
        f"💡 Скидки:\n"
        f"  • Каждый 5-й визит — час бесплатно\n"
        f"  • День рождения — скидка 20%\n"
        f"  • Приведи друга — +200 бонусов\n"
    )

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Games & Consoles ────────────────────────────────────

@router.callback_query(F.data == "show:games")
async def show_games(callback: CallbackQuery):
    consoles_text = ", ".join(CONSOLES)
    text = f"🎮 Консоли и игры\n{'─' * 28}\n\n"
    text += f"🕹 Консоли: {consoles_text}\n\n"
    text += "📀 Доступные игры:\n"
    for i, game in enumerate(PS5_GAMES, 1):
        if game.startswith("и другие"):
            text += f"\n  🔥 {game}\n"
        else:
            text += f"  {i}. {game}\n"
    text += "\n💡 Почти все популярные игры в наличии!"

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Hookah menu ─────────────────────────────────────────

@router.callback_query(F.data == "show:hookah")
async def show_hookah(callback: CallbackQuery):
    text = f"🔥 Кальян\n{'─' * 28}\n\n"
    for name, price in EXTRAS_HOOKAH.items():
        text += f"  🔥 {name} — {price}₽\n"
    text += "\n💡 Кальян можно заказать заранее при бронировании!"

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Food & drinks ───────────────────────────────────────

@router.callback_query(F.data == "show:food")
async def show_food(callback: CallbackQuery):
    text = (
        f"🍕 Еда и напитки\n"
        f"{'─' * 28}\n\n"
        f"📦 {DELIVERY_NOTE}\n\n"
        f"Вы можете заказать любую еду и напитки из сервисов\n"
        f"доставки прямо к нам в комнату.\n\n"
        f"Администратор поможет с заказом! 🤝"
    )

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Location ────────────────────────────────────────────

@router.callback_query(F.data == "show:location")
async def show_location(callback: CallbackQuery):
    text = (
        f"📍 Как добраться\n"
        f"{'─' * 28}\n\n"
        f"🏠 {VENUE_ADDRESS}\n\n"
        f"Мы находимся в центре Нальчика.\n\n"
        f"📱 {VENUE_PHONE}\n"
        f"📸 {VENUE_INSTAGRAM}"
    )

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    try:
        await callback.message.answer_location(
            latitude=VENUE_LATITUDE,
            longitude=VENUE_LONGITUDE,
        )
    except Exception:
        pass
    await callback.answer()
