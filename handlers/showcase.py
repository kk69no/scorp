"""
Venue info: about, prices, games, hookah menu, food, location.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from keyboards import showcase_kb, main_menu_kb
from config import (
    VENUE_NAME, VENUE_ADDRESS, VENUE_PHONE, VENUE_INSTAGRAM,
    VENUE_DESCRIPTION, PRICE_PER_HOUR, PRICE_PER_HOUR_WEEKDAY_DISCOUNT,
    WORK_HOURS_START, WORK_HOURS_END,
    EXTRAS_HOOKAH, EXTRAS_DRINKS, EXTRAS_FOOD,
    PS5_GAMES, MAX_CAPACITY,
)

router = Router()


@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
    text = (
        f"🏠 {VENUE_NAME}\n"
        f"{'─' * 28}\n\n"
        f"{VENUE_DESCRIPTION}\n\n"
        f"📍 {VENUE_ADDRESS}\n"
        f"📱 {VENUE_PHONE}\n"
        f"📸 Instagram: {VENUE_INSTAGRAM}\n\n"
        f"🕐 Режим работы:\n"
        f"  Ежедневно {WORK_HOURS_START}:00 — {WORK_HOURS_END:02d}:00\n\n"
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
        f"  • Стандарт: {PRICE_PER_HOUR}₽/час\n"
        f"  • Пн–Чт до 17:00: {PRICE_PER_HOUR_WEEKDAY_DISCOUNT}₽/час\n\n"
        f"🔥 Кальян:\n"
    )
    for name, price in EXTRAS_HOOKAH.items():
        text += f"  • {name}: {price}₽\n"

    text += f"\n🥤 Напитки:\n"
    for name, price in EXTRAS_DRINKS.items():
        text += f"  • {name}: {price}₽\n"

    text += f"\n🍕 Еда:\n"
    for name, price in EXTRAS_FOOD.items():
        text += f"  • {name}: {price}₽\n"

    text += (
        f"\n💡 Скидки:\n"
        f"  • Каждый 5-й визит — час бесплатно\n"
        f"  • День рождения — скидка 20%\n"
        f"  • Приведи друга — +200 бонусов\n"
    )

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── PS5 Games ───────────────────────────────────────────

@router.callback_query(F.data == "show:games")
async def show_games(callback: CallbackQuery):
    text = f"🎮 Игры на PS5\n{'─' * 28}\n\n"
    for i, game in enumerate(PS5_GAMES, 1):
        text += f"  {i}. {game}\n"
    text += "\n💡 Список обновляется — спрашивай о новинках!"

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Hookah menu ─────────────────────────────────────────

@router.callback_query(F.data == "show:hookah")
async def show_hookah(callback: CallbackQuery):
    text = f"🔥 Меню кальянов\n{'─' * 28}\n\n"
    for name, price in EXTRAS_HOOKAH.items():
        text += f"  🔥 {name} — {price}₽\n"
    text += "\n💡 Кальян можно заказать заранее при бронировании!"

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Food & drinks ───────────────────────────────────────

@router.callback_query(F.data == "show:food")
async def show_food(callback: CallbackQuery):
    text = f"🍕 Еда и напитки\n{'─' * 28}\n\n"

    text += "🥤 Напитки:\n"
    for name, price in EXTRAS_DRINKS.items():
        text += f"  • {name} — {price}₽\n"

    text += "\n🍕 Еда:\n"
    for name, price in EXTRAS_FOOD.items():
        text += f"  • {name} — {price}₽\n"

    text += "\n💡 Заказывай заранее — к твоему приходу всё будет готово!"

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    await callback.answer()


# ─── Location ────────────────────────────────────────────

@router.callback_query(F.data == "show:location")
async def show_location(callback: CallbackQuery):
    text = (
        f"📍 Как добраться\n"
        f"{'─' * 28}\n\n"
        f"🏠 {VENUE_ADDRESS}\n\n"
        f"Мы находимся в центре Нальчика.\n"
        f"Ориентир: ул. Чернышевского / ул. Толстого.\n\n"
        f"🅿️ Парковка есть\n"
        f"📱 {VENUE_PHONE}\n"
        f"📸 {VENUE_INSTAGRAM}"
    )

    await callback.message.edit_text(text, reply_markup=showcase_kb())
    # Send location pin
    try:
        await callback.message.answer_location(
            latitude=43.49556,
            longitude=43.598987,
        )
    except Exception:
        pass
    await callback.answer()
