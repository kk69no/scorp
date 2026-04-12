"""
Help & FAQ.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import main_menu_kb
from config import (
    VENUE_NAME, VENUE_ADDRESS, VENUE_PHONE,
    PRICE_PER_HOUR, PRICE_FULL_DAY, MIN_BOOKING_HOURS,
    MAX_CAPACITY, WORK_HOURS_START, WORK_HOURS_END,
    VENUE_LATITUDE, VENUE_LONGITUDE,
)

router = Router()

FAQ_KB_DATA = [
    ("📅 Как забронировать?", "faq:booking"),
    ("💰 Цены и оплата", "faq:prices"),
    ("❌ Отмена и перенос", "faq:cancel"),
    ("🎁 Бонусная программа", "faq:loyalty"),
    ("🎫 Промокоды", "faq:promo"),
    ("🎮 Что есть в комнате?", "faq:room"),
    ("🍕 Еда и напитки", "faq:food"),
    ("📍 Как добраться?", "faq:location"),
]


def _faq_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d)] for t, d in FAQ_KB_DATA
    ])


def _back_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К списку", callback_data="faq:menu")]
    ])


@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def show_help(message: Message):
    await message.answer(
        f"❓ Помощь — {VENUE_NAME}\n{'─' * 28}\n\nВыбери вопрос:",
        reply_markup=_faq_kb(),
    )


@router.callback_query(F.data == "faq:menu")
async def faq_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        f"❓ Помощь — {VENUE_NAME}\n{'─' * 28}\n\nВыбери вопрос:",
        reply_markup=_faq_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:booking")
async def faq_booking(callback: CallbackQuery):
    await callback.message.edit_text(
        "📅 Как забронировать?\n\n"
        "1. Нажми «📅 Забронировать»\n"
        "2. Выбери дату в календаре\n"
        "3. Выбери время\n"
        "4. Укажи длительность (мин. 3 часа)\n"
        "5. Укажи кол-во гостей\n"
        "6. Добавь кальян или пропусти\n"
        "7. Введи промокод если есть\n"
        "8. Подтверди!\n\n"
        "💡 «🔄 Как в прошлый раз» — повторит прошлую бронь",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:prices")
async def faq_prices(callback: CallbackQuery):
    await callback.message.edit_text(
        f"💰 Цены\n\n"
        f"🏠 Комната:\n"
        f"  • {PRICE_PER_HOUR:,}₽ / час\n"
        f"  • 🌟 Сутки — {PRICE_FULL_DAY:,}₽\n"
        f"  • Минимум: {MIN_BOOKING_HOURS} часа\n\n"
        f"💳 Оплата на месте: наличные / карта.\n"
        f"Предоплата не требуется.",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:cancel")
async def faq_cancel(callback: CallbackQuery):
    await callback.message.edit_text(
        "❌ Отмена и перенос\n\n"
        "📋 Мои брони → выбери бронь:\n"
        "  • «❌ Отменить» — без штрафов\n"
        "  • «📅 Перенести» — на другую дату\n\n"
        "⚠️ 3 неявки без отмены = блокировка.",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:loyalty")
async def faq_loyalty(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎁 Бонусная программа\n\n"
        "📈 Уровни:\n"
        "  🥉 Бронза — 0+ визитов\n"
        "  🥈 Серебро — 5+ визитов\n"
        "  🥇 Золото — 10+ визитов\n"
        "  💎 Платина — 20+ визитов\n\n"
        "Бонусы:\n"
        "  • +100 баллов за визит\n"
        "  • +200 за друга\n"
        "  • Каждый 5-й визит — час бесплатно\n"
        "  • 20% скидка на ДР (±3 дня)\n\n"
        "Баллы → скидки в «👤 Профиль»",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:promo")
async def faq_promo(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎫 Промокоды\n\n"
        "Введи код при подтверждении брони — "
        "скидка применится автоматически.\n\n"
        "Где взять:\n"
        "  • В рассылках бота\n"
        "  • В Instagram\n"
        "  • У друзей",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:room")
async def faq_room(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🎮 В комнате\n\n"
        f"🕹 PS3 + PS5 Pro\n"
        f"📀 Все популярные игры\n"
        f"👥 До {MAX_CAPACITY} человек\n"
        f"🔥 Кальян\n"
        f"🍕 Доставка еды\n\n"
        f"⏰ {WORK_HOURS_START}:00 — {WORK_HOURS_END:02d}:00",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:food")
async def faq_food(callback: CallbackQuery):
    await callback.message.edit_text(
        "🍕 Еда и напитки\n\n"
        "Заказывай доставку от партнёров прямо в комнату!\n"
        "Администратор поможет на месте.",
        reply_markup=_back_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq:location")
async def faq_location(callback: CallbackQuery):
    await callback.message.edit_text(
        f"📍 Как добраться\n\n"
        f"🏠 {VENUE_ADDRESS}\n"
        f"📱 {VENUE_PHONE}\n\n"
        f"Центр Нальчика.",
        reply_markup=_back_kb(),
    )
    try:
        await callback.message.answer_location(latitude=VENUE_LATITUDE, longitude=VENUE_LONGITUDE)
    except Exception:
        pass
    await callback.answer()
