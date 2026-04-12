"""
Admin panel — full-featured management for Scorpion Platinum.
"""

from datetime import date, timedelta, datetime
import io
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
from states import AdminStates
from keyboards import (
    admin_menu_kb, admin_bookings_list_kb, admin_confirm_kb, main_menu_kb,
    calendar_kb,
)
from config import ADMIN_IDS, WEEKDAYS_RU, LOYALTY_VISIT_POINTS, PRICE_PER_HOUR, MAX_CAPACITY

router = Router()


async def _check_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return await db.is_admin(user_id)


STATUS_TEXT = {
    "pending": "⏳ Ожидание",
    "confirmed": "✅ Подтверждена",
    "completed": "✅ Завершена",
    "cancelled": "❌ Отменена",
    "no_show": "🚷 Неявка",
}


# ═══════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()

    if not ADMIN_IDS:
        user = await db.get_user(message.from_user.id)
        if user:
            await db.set_admin(message.from_user.id)
            ADMIN_IDS.append(message.from_user.id)
            await message.answer(
                "🔑 Ты назначен администратором!\n\nАдмин-панель 👇",
                reply_markup=admin_menu_kb(),
            )
            return

    if not await _check_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    await message.answer("🔧 Админ-панель", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "adm:menu")
async def adm_menu(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("🔧 Админ-панель", reply_markup=admin_menu_kb())
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  BOOKINGS — TODAY
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:today")
async def adm_today(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    today_str = date.today().isoformat()
    bookings = await db.get_bookings_for_date(today_str)

    total_guests = sum(b["guests_count"] for b in bookings)
    total_revenue = sum(b["total_price"] for b in bookings)

    text = (
        f"📋 Брони на сегодня ({today_str})\n"
        f"{'─' * 28}\n"
        f"Всего: {len(bookings)} | 👥 {total_guests} чел. | 💵 {total_revenue:,}₽\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_bookings_list_kb(bookings, "view"),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  BOOKINGS — WEEK
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:week")
async def adm_week(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    today = date.today()
    text = f"📅 Брони на неделю\n{'─' * 28}\n\n"
    total_all = 0

    for i in range(7):
        d = today + timedelta(days=i)
        d_str = d.isoformat()
        wd = WEEKDAYS_RU[d.weekday()]
        bookings = await db.get_bookings_for_date(d_str)
        count = len(bookings)
        guests = sum(b["guests_count"] for b in bookings)
        revenue = sum(b["total_price"] for b in bookings)
        total_all += revenue

        marker = "📌 " if i == 0 else "  "
        if count:
            text += f"{marker}{d_str} ({wd}): {count} бр. | 👥 {guests} | 💵 {revenue:,}₽\n"
        else:
            text += f"{marker}{d_str} ({wd}): —\n"

    text += f"\n💰 Итого за неделю: {total_all:,}₽"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  OCCUPANCY — HOURLY LOAD
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:occupancy")
async def adm_occupancy(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    today_str = date.today().isoformat()
    occ = await db.get_hourly_occupancy(today_str)

    text = f"📊 Загрузка по часам — сегодня ({today_str})\n{'─' * 28}\n\n"
    for time_str, guests in occ.items():
        bar = "█" * guests + "░" * (MAX_CAPACITY - guests)
        pct = int(guests / MAX_CAPACITY * 100) if MAX_CAPACITY else 0
        text += f"  {time_str} [{bar}] {guests}/{MAX_CAPACITY} ({pct}%)\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  MANUAL BOOKING
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:manual_booking")
async def adm_manual_booking(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    await callback.message.edit_text(
        "📝 Ручная бронь\n\n"
        "Введи имя клиента или Telegram ID.\n"
        "Если клиента нет в базе — бронь создастся на тебя (админа)."
    )
    await state.set_state(AdminStates.manual_choosing_user)
    await callback.answer()


@router.message(AdminStates.manual_choosing_user)
async def adm_manual_user(message: Message, state: FSMContext):
    text = message.text.strip()

    # Try as telegram ID
    try:
        tg_id = int(text)
        user = await db.get_user(tg_id)
    except ValueError:
        # Search by name
        results = await db.search_users(text)
        if results:
            user = results[0]
        else:
            user = None

    if user:
        await state.update_data(manual_user_id=user["id"], manual_user_name=user["full_name"])
        await message.answer(
            f"👤 Клиент: {user['full_name']}\n\n📅 Выбери дату:",
            reply_markup=calendar_kb(0),
        )
    else:
        # Book under admin
        admin_user = await db.get_user(message.from_user.id)
        await state.update_data(
            manual_user_id=admin_user["id"],
            manual_user_name=f"[РУЧНАЯ] {text}",
            manual_note=f"Ручная бронь для: {text}",
        )
        await message.answer(
            f"👤 Клиент не найден — бронь на: {text}\n\n📅 Выбери дату:",
            reply_markup=calendar_kb(0),
        )

    await state.set_state(AdminStates.manual_choosing_date)


@router.callback_query(AdminStates.manual_choosing_date, F.data.startswith("date:"))
async def adm_manual_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[1]
    await state.update_data(manual_date=date_str)

    from handlers.booking import _get_work_hours
    all_slots = _get_work_hours()

    from keyboards import time_slots_kb
    await callback.message.edit_text(
        f"📅 Дата: {date_str}\n\n⏰ Выбери время:",
        reply_markup=time_slots_kb(all_slots),
    )
    await state.set_state(AdminStates.manual_choosing_time)
    await callback.answer()


@router.callback_query(AdminStates.manual_choosing_time, F.data.startswith("time:"))
async def adm_manual_time(callback: CallbackQuery, state: FSMContext):
    start_time = callback.data.split(":")[1] + ":00"
    await state.update_data(manual_time=start_time)

    await callback.message.edit_text(
        f"⏰ Время: {start_time}\n\n⏳ Длительность (часы)? Введи число:"
    )
    await state.set_state(AdminStates.manual_choosing_duration)
    await callback.answer()


@router.message(AdminStates.manual_choosing_duration)
async def adm_manual_duration(message: Message, state: FSMContext):
    try:
        dur = int(message.text.strip())
        if dur < 1 or dur > 24:
            raise ValueError
    except ValueError:
        await message.answer("Введи число от 1 до 24:")
        return

    await state.update_data(manual_duration=dur)
    await message.answer(f"⏳ {dur} ч.\n\n👥 Количество гостей? Введи число:")
    await state.set_state(AdminStates.manual_choosing_guests)


@router.message(AdminStates.manual_choosing_guests)
async def adm_manual_guests(message: Message, state: FSMContext):
    try:
        guests = int(message.text.strip())
        if guests < 1 or guests > MAX_CAPACITY:
            raise ValueError
    except ValueError:
        await message.answer(f"Введи число от 1 до {MAX_CAPACITY}:")
        return

    data = await state.get_data()
    dur = data["manual_duration"]
    start_h = int(data["manual_time"].split(":")[0])
    end_h = (start_h + dur) % 24
    end_time = f"{end_h:02d}:00"

    from config import PRICE_FULL_DAY
    if dur >= 17:
        price = PRICE_FULL_DAY
    else:
        price = PRICE_PER_HOUR * dur

    booking_id = await db.create_booking(
        user_id=data["manual_user_id"],
        booking_date=data["manual_date"],
        start_time=data["manual_time"],
        end_time=end_time,
        duration_hours=dur,
        guests_count=guests,
        base_price=price,
        extras_price=0,
        discount=0,
        total_price=price,
        admin_note=data.get("manual_note", "Ручная бронь"),
    )

    await state.clear()
    await message.answer(
        f"✅ Ручная бронь #{booking_id} создана!\n\n"
        f"👤 {data['manual_user_name']}\n"
        f"📅 {data['manual_date']} {data['manual_time']}–{end_time}\n"
        f"👥 {guests} чел. | 💵 {price:,}₽",
        reply_markup=admin_menu_kb(),
    )


# Calendar nav for manual booking
@router.callback_query(AdminStates.manual_choosing_date, F.data.startswith("cal_prev:"))
async def manual_cal_prev(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(max(0, offset - 1)))
    await callback.answer()

@router.callback_query(AdminStates.manual_choosing_date, F.data.startswith("cal_next:"))
async def manual_cal_next(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(min(offset + 1, 2)))
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  BLOCK / UNBLOCK DATES
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:dates")
async def adm_dates_menu(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    blocked = await db.get_all_blocked_dates()
    text = f"📅 Управление датами\n{'─' * 28}\n\n"

    if blocked:
        text += "🚫 Заблокированные даты:\n"
        for bd in blocked:
            reason = f" — {bd['reason']}" if bd.get("reason") else ""
            text += f"  • {bd['blocked_date']}{reason}\n"
    else:
        text += "Нет заблокированных дат ✅\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать дату", callback_data="adm:block_date")],
        [InlineKeyboardButton(text="🔓 Разблокировать дату", callback_data="adm:unblock_date")],
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm:block_date")
async def adm_block_date(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    await callback.message.edit_text(
        "🚫 Выбери дату для блокировки:",
        reply_markup=calendar_kb(0),
    )
    await state.set_state(AdminStates.blocking_date)
    await callback.answer()


@router.callback_query(AdminStates.blocking_date, F.data.startswith("date:"))
async def adm_block_date_selected(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[1]
    await state.update_data(block_date=date_str)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="block_no_reason")]
    ])
    await callback.message.edit_text(
        f"🚫 Блокировка даты: {date_str}\n\nУкажи причину (или пропусти):",
        reply_markup=kb,
    )
    await state.set_state(AdminStates.blocking_reason)
    await callback.answer()


@router.callback_query(AdminStates.blocking_reason, F.data == "block_no_reason")
async def adm_block_no_reason(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.block_date(data["block_date"], "")
    await state.clear()
    await callback.message.edit_text(
        f"✅ Дата {data['block_date']} заблокирована.",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


@router.message(AdminStates.blocking_reason)
async def adm_block_reason_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.block_date(data["block_date"], message.text)
    await state.clear()
    await message.answer(
        f"✅ Дата {data['block_date']} заблокирована.\nПричина: {message.text}",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "adm:unblock_date")
async def adm_unblock_date(callback: CallbackQuery, state: FSMContext):
    blocked = await db.get_all_blocked_dates()
    if not blocked:
        await callback.answer("Нет заблокированных дат", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for bd in blocked:
        reason = f" ({bd['reason']})" if bd.get("reason") else ""
        rows.append([InlineKeyboardButton(
            text=f"🔓 {bd['blocked_date']}{reason}",
            callback_data=f"adm_unblock:{bd['blocked_date']}"
        )])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:dates")])

    await callback.message.edit_text(
        "🔓 Выбери дату для разблокировки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_unblock:"))
async def adm_unblock_confirm(callback: CallbackQuery):
    date_str = callback.data.split(":", 1)[1]
    await db.unblock_date(date_str)
    await callback.answer(f"✅ {date_str} разблокирована", show_alert=True)
    await adm_dates_menu(callback)


# Calendar nav for block
@router.callback_query(AdminStates.blocking_date, F.data.startswith("cal_prev:"))
async def adm_cal_prev(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(max(0, offset - 1)))
    await callback.answer()

@router.callback_query(AdminStates.blocking_date, F.data.startswith("cal_next:"))
async def adm_cal_next(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(min(offset + 1, 2)))
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  STATISTICS — ENHANCED
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:stats")
async def adm_stats(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    stats = await db.get_stats()

    text = (
        f"📊 Статистика\n"
        f"{'─' * 28}\n\n"
        f"👥 Пользователей: {stats['total_users']} (новых за неделю: +{stats['new_users_week']})\n"
        f"🔄 Повторных клиентов: {stats['repeat_users']}\n"
        f"📋 Активных броней: {stats['active_bookings']}\n"
        f"✅ Завершённых: {stats['completed_bookings']}\n"
        f"📌 Сегодня: {stats['today_bookings']}\n"
        f"🚷 Неявок: {stats['noshows']}\n"
        f"❌ Отмен: {stats['cancellations']}\n\n"
        f"💰 Выручка:\n"
        f"  За всё время: {stats['total_revenue']:,}₽\n"
        f"  За 7 дней: {stats['week_revenue']:,}₽\n"
        f"  За 30 дней: {stats['month_revenue']:,}₽\n"
        f"  Средний чек: {stats['avg_check']:,}₽\n\n"
        f"📈 Средние показатели:\n"
        f"  Гостей/бронь: {stats['avg_guests']}\n"
        f"  Часов/бронь: {stats['avg_duration']}\n\n"
        f"⭐ Рейтинг: {stats['avg_rating']}/5 ({stats['reviews_count']} отзывов)\n\n"
    )

    if stats["popular_hours"]:
        text += "🕐 Популярные часы:\n"
        for h in stats["popular_hours"]:
            text += f"  {h['start_time']} — {h['c']} бр.\n"

    if stats["popular_days"]:
        text += "\n📅 Популярные дни:\n"
        for d in stats["popular_days"]:
            text += f"  {d['day_name']} — {d['c']} бр.\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Загрузка по часам", callback_data="adm:occupancy")],
        [InlineKeyboardButton(text="💰 Выручка по дням", callback_data="adm:revenue")],
        [InlineKeyboardButton(text="📊 Месячный отчёт", callback_data="adm:monthly")],
        [InlineKeyboardButton(text="🏆 Топ клиентов", callback_data="adm:top_customers")],
        [InlineKeyboardButton(text="⭐ Все отзывы", callback_data="adm:reviews")],
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  REVENUE BY DAY
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:revenue")
async def adm_revenue(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    days_data = await db.get_revenue_by_day(14)

    text = f"💰 Выручка по дням (14 дней)\n{'─' * 28}\n\n"
    total = 0
    if days_data:
        for d in days_data:
            total += d["revenue"]
            text += f"  {d['booking_date']}: {d['bookings']} бр. | 👥 {d['guests']} | 💵 {d['revenue']:,}₽\n"
        text += f"\n💰 Итого: {total:,}₽"
        text += f"\n📈 В среднем/день: {total // len(days_data):,}₽"
    else:
        text += "Нет данных за период"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К статистике", callback_data="adm:stats")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  REVIEWS
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:reviews")
async def adm_reviews(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    reviews = await db.get_all_reviews(20)
    avg, cnt = await db.get_average_rating()

    text = f"⭐ Отзывы ({cnt} всего, средний: {avg}/5)\n{'─' * 28}\n\n"

    if reviews:
        for r in reviews:
            stars = "⭐" * r["rating"]
            comment = f"\n  💬 {r['comment']}" if r.get("comment") else ""
            text += f"  {stars} — {r['full_name']} ({r['created_at'][:10]}){comment}\n\n"
    else:
        text += "Пока нет отзывов"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К статистике", callback_data="adm:stats")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:users")
async def adm_users_menu(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    users = await db.get_all_users_including_blocked()
    total = len(users)
    blocked = sum(1 for u in users if u["is_blacklisted"])

    text = (
        f"👥 Пользователи ({total} всего, {blocked} в ЧС)\n"
        f"{'─' * 28}\n\n"
        f"Последние зарегистрированные:\n"
    )

    for u in users[:10]:
        bl = " ⛔" if u["is_blacklisted"] else ""
        adm = " 🔑" if u["is_admin"] else ""
        text += f"  • {u['full_name']}{adm}{bl} — {u['visits_count']} визитов, {u['loyalty_points']} баллов\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск клиента", callback_data="adm:search_user")],
        [InlineKeyboardButton(text="⛔ Чёрный список", callback_data="adm:blacklist")],
        [InlineKeyboardButton(text="🔑 Управление админами", callback_data="adm:admins")],
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm:search_user")
async def adm_search_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 Введи имя, телефон или username для поиска:"
    )
    await state.set_state(AdminStates.search_user)
    await callback.answer()


@router.message(AdminStates.search_user)
async def adm_search_result(message: Message, state: FSMContext):
    query = message.text.strip()
    results = await db.search_users(query)
    await state.clear()

    if not results:
        await message.answer(
            f"Не найдено: «{query}»",
            reply_markup=admin_menu_kb(),
        )
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for u in results[:10]:
        rows.append([InlineKeyboardButton(
            text=f"👤 {u['full_name']} ({u['visits_count']} визитов)",
            callback_data=f"adm_user:{u['telegram_id']}"
        )])
    rows.append([InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")])

    await message.answer(
        f"🔍 Результаты для «{query}» ({len(results)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("adm_user:"))
async def adm_user_profile(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    user = await db.get_user(tg_id)
    if not user:
        await callback.answer("Не найден", show_alert=True)
        return

    bookings = await db.get_user_bookings_by_id(user["id"], limit=5)

    bl = "⛔ ЗАБЛОКИРОВАН" if user["is_blacklisted"] else "✅ Активен"
    adm = "🔑 Админ" if user["is_admin"] else ""
    username = f"@{user['username']}" if user.get("username") else "—"

    text = (
        f"👤 Профиль клиента\n{'─' * 28}\n\n"
        f"Имя: {user['full_name']}\n"
        f"Telegram: {username} (ID: {user['telegram_id']})\n"
        f"Телефон: {user.get('phone') or '—'}\n"
        f"ДР: {user.get('birthday') or '—'}\n"
        f"Статус: {bl} {adm}\n\n"
        f"📊 Статистика:\n"
        f"  🏆 Визитов: {user['visits_count']}\n"
        f"  💎 Баллов: {user['loyalty_points']}\n"
        f"  🚷 Неявок: {user['noshow_count']}\n"
        f"  📅 Регистрация: {user['created_at'][:10]}\n"
    )

    if bookings:
        text += f"\n📋 Последние брони:\n"
        for b in bookings:
            text += f"  #{b['id']} {b['booking_date']} {b['start_time']} — {STATUS_TEXT.get(b['status'], b['status'])}\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    # User notes
    notes = await db.get_user_notes(user["id"], limit=3)
    if notes:
        text += "\n📝 Заметки:\n"
        for n in notes:
            text += f"  {n['created_at'][:10]}: {n['note']}\n"

    buttons = [
        [InlineKeyboardButton(text="💎 Баллы", callback_data=f"adm_points:{tg_id}"),
         InlineKeyboardButton(text="📝 Заметка", callback_data=f"adm_note:{tg_id}")],
        [InlineKeyboardButton(text="💬 Написать", callback_data=f"adm_msg:{tg_id}")],
    ]
    if user["is_blacklisted"]:
        buttons.append([InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"adm_unban:{tg_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="⛔ Заблокировать", callback_data=f"adm_ban:{tg_id}")])

    if user["is_admin"]:
        buttons.append([InlineKeyboardButton(text="🔑 Снять админа", callback_data=f"adm_demote:{tg_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="🔑 Назначить админом", callback_data=f"adm_promote:{tg_id}")])

    buttons.append([InlineKeyboardButton(text="◀️ К пользователям", callback_data="adm:users")])

    await callback.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ─── Points adjustment ───

@router.callback_query(F.data.startswith("adm_points:"))
async def adm_adjust_points(callback: CallbackQuery, state: FSMContext):
    tg_id = int(callback.data.split(":")[1])
    user = await db.get_user(tg_id)
    await state.update_data(points_user_tg=tg_id)
    await callback.message.edit_text(
        f"💎 Баллы {user['full_name']}: {user['loyalty_points']}\n\n"
        "Введи новое количество баллов (число):"
    )
    await state.set_state(AdminStates.adjust_points)
    await callback.answer()


@router.message(AdminStates.adjust_points)
async def adm_set_points(message: Message, state: FSMContext):
    try:
        points = int(message.text.strip())
        if points < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи положительное число:")
        return

    data = await state.get_data()
    tg_id = data["points_user_tg"]
    await db.set_loyalty_points(tg_id, points)
    user = await db.get_user(tg_id)
    await state.clear()
    await message.answer(
        f"✅ Баллы {user['full_name']} обновлены: {points}",
        reply_markup=admin_menu_kb(),
    )


# ─── Message user ───

@router.callback_query(F.data.startswith("adm_msg:"))
async def adm_message_user(callback: CallbackQuery, state: FSMContext):
    tg_id = int(callback.data.split(":")[1])
    user = await db.get_user(tg_id)
    await state.update_data(msg_user_tg=tg_id, msg_user_name=user["full_name"])
    await callback.message.edit_text(
        f"💬 Сообщение для {user['full_name']}\n\nВведи текст:"
    )
    await state.set_state(AdminStates.message_user)
    await callback.answer()


@router.message(AdminStates.message_user)
async def adm_send_message(message: Message, state: FSMContext):
    data = await state.get_data()
    tg_id = data["msg_user_tg"]
    try:
        await message.bot.send_message(
            tg_id,
            f"💬 Сообщение от администрации Scorpion Platinum:\n\n{message.text}"
        )
        await message.answer(f"✅ Сообщение отправлено {data['msg_user_name']}", reply_markup=admin_menu_kb())
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}", reply_markup=admin_menu_kb())
    await state.clear()


# ─── Ban / Unban ───

@router.callback_query(F.data.startswith("adm_ban:"))
async def adm_ban(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    await db.blacklist_user(tg_id)
    await callback.answer("⛔ Заблокирован", show_alert=True)
    await adm_user_profile(callback.__class__(
        id=callback.id, chat_instance=callback.chat_instance,
        data=f"adm_user:{tg_id}", message=callback.message, from_user=callback.from_user
    ))


@router.callback_query(F.data.startswith("adm_unban:"))
async def adm_unban(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    await db.unblacklist_user(tg_id)
    await callback.answer("✅ Разблокирован", show_alert=True)
    # Refresh profile
    user = await db.get_user(tg_id)
    if user:
        callback.data = f"adm_user:{tg_id}"
        await adm_user_profile(callback)


# ─── Promote / Demote admin ───

@router.callback_query(F.data.startswith("adm_promote:"))
async def adm_promote(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    await db.set_admin(tg_id)
    await callback.answer("🔑 Назначен админом", show_alert=True)
    callback.data = f"adm_user:{tg_id}"
    await adm_user_profile(callback)


@router.callback_query(F.data.startswith("adm_demote:"))
async def adm_demote(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    await db.remove_admin(tg_id)
    if tg_id in ADMIN_IDS:
        ADMIN_IDS.remove(tg_id)
    await callback.answer("Админ снят", show_alert=True)
    callback.data = f"adm_user:{tg_id}"
    await adm_user_profile(callback)


# ═══════════════════════════════════════════════════════════
#  BLACKLIST
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:blacklist")
async def adm_blacklist(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    db_conn = await db.get_db()
    try:
        cur = await db_conn.execute("SELECT * FROM users WHERE is_blacklisted = 1")
        blacklisted = [dict(r) for r in await cur.fetchall()]
    finally:
        await db_conn.close()

    text = f"⛔ Чёрный список ({len(blacklisted)} чел.)\n{'─' * 28}\n\n"

    rows = []
    if blacklisted:
        for u in blacklisted:
            text += f"  • {u['full_name']} (неявок: {u['noshow_count']})\n"
            rows.append([InlineKeyboardButton(
                text=f"🔓 {u['full_name']}",
                callback_data=f"adm_unban:{u['telegram_id']}"
            )])
    else:
        text += "Пусто ✅"

    rows.append([InlineKeyboardButton(text="➕ Добавить в ЧС", callback_data="adm:add_blacklist")])
    rows.append([InlineKeyboardButton(text="◀️ К пользователям", callback_data="adm:users")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:add_blacklist")
async def adm_add_blacklist(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введи Telegram ID пользователя для блокировки:"
    )
    await state.set_state(AdminStates.adding_to_blacklist)
    await callback.answer()


@router.message(AdminStates.adding_to_blacklist)
async def adm_add_blacklist_id(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("Введи числовой Telegram ID:")
        return

    user = await db.get_user(tg_id)
    if not user:
        await message.answer("Пользователь не найден в базе.", reply_markup=admin_menu_kb())
        await state.clear()
        return

    await db.blacklist_user(tg_id)
    await state.clear()
    await message.answer(
        f"⛔ {user['full_name']} добавлен в чёрный список.",
        reply_markup=admin_menu_kb(),
    )


# ═══════════════════════════════════════════════════════════
#  ADMIN ROLES
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:admins")
async def adm_admins_list(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    admins = await db.get_admins()
    text = f"🔑 Администраторы ({len(admins)})\n{'─' * 28}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for a in admins:
        username = f"@{a['username']}" if a.get("username") else ""
        text += f"  • {a['full_name']} {username}\n"
        rows.append([InlineKeyboardButton(
            text=f"👤 {a['full_name']}",
            callback_data=f"adm_user:{a['telegram_id']}"
        )])

    rows.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm:add_admin")])
    rows.append([InlineKeyboardButton(text="◀️ К пользователям", callback_data="adm:users")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:add_admin")
async def adm_add_admin(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введи Telegram ID нового админа:")
    await state.set_state(AdminStates.adding_admin)
    await callback.answer()


@router.message(AdminStates.adding_admin)
async def adm_add_admin_id(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введи числовой Telegram ID:")
        return

    user = await db.get_user(tg_id)
    if not user:
        await message.answer("Пользователь не найден. Он должен сначала написать /start боту.",
                             reply_markup=admin_menu_kb())
        await state.clear()
        return

    await db.set_admin(tg_id)
    await state.clear()
    await message.answer(
        f"🔑 {user['full_name']} назначен админом.",
        reply_markup=admin_menu_kb(),
    )


# ═══════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:promo")
async def adm_promo(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    users = await db.get_all_users()
    await callback.message.edit_text(
        f"📢 Рассылка ({len(users)} получателей)\n\n"
        "Напиши текст сообщения:"
    )
    await state.set_state(AdminStates.sending_promo)
    await callback.answer()


@router.message(AdminStates.sending_promo)
async def adm_send_promo(message: Message, state: FSMContext):
    text = message.text
    if not text:
        await message.answer("Напиши текст для рассылки:")
        return

    users = await db.get_all_users()
    sent = 0
    failed = 0

    for user in users:
        try:
            await message.bot.send_message(
                user["telegram_id"],
                f"📢 {text}\n\n— Scorpion Platinum",
            )
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}",
        reply_markup=admin_menu_kb(),
    )


# ═══════════════════════════════════════════════════════════
#  COMPLETE / NO-SHOW
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:complete")
async def adm_complete(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    today_str = date.today().isoformat()
    bookings = await db.get_bookings_for_date(today_str)
    confirmed = [b for b in bookings if b["status"] == "confirmed"]

    if not confirmed:
        await callback.answer("Нет активных броней на сегодня", show_alert=True)
        return

    await callback.message.edit_text(
        "✅ Выбери бронь для завершения:",
        reply_markup=admin_bookings_list_kb(confirmed, "complete"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_complete:"))
async def adm_complete_select(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"Завершить бронь #{booking_id}?",
        reply_markup=admin_confirm_kb("complete", booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_confirm_complete:"))
async def adm_confirm_complete(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Бронь не найдена", show_alert=True)
        return

    await db.update_booking_status(booking_id, "completed")

    user = await db.get_user_by_id(booking["user_id"])
    if user:
        visits = await db.increment_visits(user["telegram_id"])
        await db.add_loyalty_points(user["telegram_id"], LOYALTY_VISIT_POINTS)

        try:
            msg = f"✅ Визит завершён! Спасибо за посещение Scorpion Platinum!\n\n"
            msg += f"🏆 Визит #{visits} | +{LOYALTY_VISIT_POINTS} баллов"

            from config import FREE_HOUR_EVERY_N_VISITS
            if visits % FREE_HOUR_EVERY_N_VISITS == 0:
                msg += f"\n\n🎁 Поздравляем! Следующий визит — 1 час БЕСПЛАТНО!"

            await callback.bot.send_message(user["telegram_id"], msg)
        except Exception:
            pass

    await callback.message.edit_text(
        f"✅ Бронь #{booking_id} завершена. Лояльность начислена.",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:noshow")
async def adm_noshow(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    today_str = date.today().isoformat()
    bookings = await db.get_bookings_for_date(today_str)
    confirmed = [b for b in bookings if b["status"] == "confirmed"]

    if not confirmed:
        await callback.answer("Нет активных броней на сегодня", show_alert=True)
        return

    await callback.message.edit_text(
        "🚷 Выбери бронь — отметить неявку:",
        reply_markup=admin_bookings_list_kb(confirmed, "noshow"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_noshow:"))
async def adm_noshow_select(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"🚷 Отметить неявку для брони #{booking_id}?",
        reply_markup=admin_confirm_kb("noshow", booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_confirm_noshow:"))
async def adm_confirm_noshow(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Бронь не найдена", show_alert=True)
        return

    await db.update_booking_status(booking_id, "no_show")
    blacklisted = await db.increment_noshow(booking["user_id"])

    user = await db.get_user_by_id(booking["user_id"])
    status_msg = f"🚷 Бронь #{booking_id} — неявка."
    if blacklisted and user:
        status_msg += f"\n⛔ {user['full_name']} добавлен в чёрный список (превышен лимит неявок)."

    await callback.message.edit_text(status_msg, reply_markup=admin_menu_kb())
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  EXPORT CSV
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:export")
async def adm_export(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    csv_data = await db.export_bookings_csv(90)
    file = BufferedInputFile(
        csv_data.encode("utf-8-sig"),
        filename=f"scorpion_bookings_{date.today().isoformat()}.csv",
    )
    await callback.message.answer_document(file, caption="📊 Экспорт бронирований за 90 дней")
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  VIEW BOOKING FROM ADMIN
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_view:"))
async def adm_view_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Не найдена", show_alert=True)
        return

    user = await db.get_user_by_id(booking["user_id"])
    user_name = user["full_name"] if user else "?"
    user_phone = user.get("phone", "нет") if user else "нет"
    user_tg = f"@{user['username']}" if user and user.get("username") else str(user["telegram_id"]) if user else "?"

    text = (
        f"📋 Бронь #{booking['id']}\n"
        f"{'─' * 28}\n"
        f"👤 {user_name} | 📱 {user_phone} | TG: {user_tg}\n"
        f"📅 {booking['booking_date']}\n"
        f"⏰ {booking['start_time']} — {booking['end_time']} ({booking['duration_hours']}ч)\n"
        f"👥 {booking['guests_count']} чел.\n"
        f"💵 {booking['total_price']:,}₽\n"
        f"📌 {STATUS_TEXT.get(booking['status'], booking['status'])}\n"
    )

    if booking.get("admin_note"):
        text += f"📝 Заметка: {booking['admin_note']}\n"

    if booking.get("extras"):
        text += "\n🛒 Допы:\n"
        for ext in booking["extras"]:
            text += f"  • {ext['item_name']} — {ext['price']}₽\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    if booking["status"] in ("confirmed", "pending"):
        buttons.append([
            InlineKeyboardButton(text="✅ Завершить", callback_data=f"adm_complete:{booking_id}"),
            InlineKeyboardButton(text="🚷 Неявка", callback_data=f"adm_noshow:{booking_id}"),
        ])
        buttons.append([
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"adm_edit:{booking_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"adm_cancel:{booking_id}"),
        ])
    if user:
        buttons.append([
            InlineKeyboardButton(text=f"👤 Профиль {user_name}", callback_data=f"adm_user:{user['telegram_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:today")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cancel:"))
async def adm_cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    success = await db.cancel_booking(booking_id)
    if success:
        await callback.answer("❌ Бронь отменена", show_alert=True)
    else:
        await callback.answer("Не удалось отменить", show_alert=True)
    # Return to today
    await adm_today(callback)


# ═══════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:settings")
async def adm_settings(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    from config import (
        PRICE_PER_HOUR, PRICE_FULL_DAY, WORK_HOURS_START, WORK_HOURS_END,
        MAX_CAPACITY, MIN_BOOKING_HOURS, VENUE_ADDRESS, VENUE_PHONE,
    )

    text = (
        f"⚙️ Настройки\n{'─' * 28}\n\n"
        f"💰 Цена/час: {PRICE_PER_HOUR:,}₽\n"
        f"🌟 Сутки: {PRICE_FULL_DAY:,}₽\n"
        f"⏰ Часы работы: {WORK_HOURS_START}:00 — {WORK_HOURS_END:02d}:00\n"
        f"👥 Макс. гостей: {MAX_CAPACITY}\n"
        f"⏳ Мин. бронь: {MIN_BOOKING_HOURS} ч.\n"
        f"📍 Адрес: {VENUE_ADDRESS}\n"
        f"📱 Телефон: {VENUE_PHONE}\n\n"
        f"Нажми кнопку чтобы изменить настройку:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цена/час", callback_data="adm_set:price"),
         InlineKeyboardButton(text="🌟 Сутки", callback_data="adm_set:fullday")],
        [InlineKeyboardButton(text="⏰ Открытие", callback_data="adm_set:hours_start"),
         InlineKeyboardButton(text="⏰ Закрытие", callback_data="adm_set:hours_end")],
        [InlineKeyboardButton(text="👥 Макс. гостей", callback_data="adm_set:capacity")],
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  EDIT BOOKING
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_edit:"))
async def adm_edit_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Не найдена", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Дату", callback_data=f"adm_editf:date:{booking_id}"),
         InlineKeyboardButton(text="⏰ Время", callback_data=f"adm_editf:time:{booking_id}")],
        [InlineKeyboardButton(text="⏳ Длительность", callback_data=f"adm_editf:duration:{booking_id}"),
         InlineKeyboardButton(text="👥 Гостей", callback_data=f"adm_editf:guests:{booking_id}")],
        [InlineKeyboardButton(text="📝 Заметку", callback_data=f"adm_editf:note:{booking_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_view:{booking_id}")],
    ])

    await callback.message.edit_text(
        f"✏️ Редактирование брони #{booking_id}\n\n"
        f"📅 {booking['booking_date']} {booking['start_time']}–{booking['end_time']}\n"
        f"👥 {booking['guests_count']} чел. | {booking['duration_hours']}ч | {booking['total_price']:,}₽\n\n"
        "Что изменить?",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_editf:"))
async def adm_edit_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    field = parts[1]
    booking_id = int(parts[2])

    await state.update_data(edit_booking_id=booking_id, edit_field=field)

    prompts = {
        "date": "📅 Введи новую дату (YYYY-MM-DD):",
        "time": "⏰ Введи новое время начала (HH:MM):",
        "duration": "⏳ Введи новую длительность (часы):",
        "guests": f"👥 Введи кол-во гостей (1-{MAX_CAPACITY}):",
        "note": "📝 Введи заметку:",
    }

    await callback.message.edit_text(prompts.get(field, "Введи значение:"))
    await state.set_state(AdminStates.edit_new_value)
    await callback.answer()


@router.message(AdminStates.edit_new_value)
async def adm_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data["edit_booking_id"]
    field = data["edit_field"]
    value = message.text.strip()

    try:
        if field == "date":
            from datetime import datetime as dt
            dt.strptime(value, "%Y-%m-%d")
            await db.update_booking_fields(booking_id, booking_date=value)
        elif field == "time":
            h, m = value.split(":")
            int(h); int(m)
            booking = await db.get_booking(booking_id)
            end_h = int(h) + booking["duration_hours"]
            end_time = f"{end_h % 24:02d}:00"
            await db.update_booking_fields(booking_id, start_time=value, end_time=end_time)
        elif field == "duration":
            dur = int(value)
            booking = await db.get_booking(booking_id)
            start_h = int(booking["start_time"].split(":")[0])
            end_time = f"{(start_h + dur) % 24:02d}:00"
            new_price = PRICE_PER_HOUR * dur
            await db.update_booking_fields(
                booking_id, duration_hours=dur, end_time=end_time,
                base_price=new_price,
                total_price=new_price + booking["extras_price"] - booking["discount"],
            )
        elif field == "guests":
            guests = int(value)
            if guests < 1 or guests > MAX_CAPACITY:
                raise ValueError
            await db.update_booking_fields(booking_id, guests_count=guests)
        elif field == "note":
            await db.update_booking_fields(booking_id, admin_note=value)
        else:
            await message.answer("❌ Неизвестное поле", reply_markup=admin_menu_kb())
            await state.clear()
            return

        await db.add_admin_log(message.from_user.id, "edit_booking",
                               f"Бронь #{booking_id}: {field} = {value}")
        await state.clear()
        await message.answer(
            f"✅ Бронь #{booking_id}: {field} → {value}",
            reply_markup=admin_menu_kb(),
        )
    except (ValueError, TypeError):
        await message.answer("❌ Неверный формат. Попробуй снова:")


# ═══════════════════════════════════════════════════════════
#  PROMO CODES
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:promo_codes")
async def adm_promo_codes(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    codes = await db.get_all_promo_codes()

    text = f"🎫 Промокоды ({len(codes)})\n{'─' * 28}\n\n"

    if codes:
        for c in codes:
            status = "✅" if c["is_active"] else "❌"
            disc = f"-{c['discount_percent']}%" if c["discount_percent"] else f"-{c['discount_amount']}₽"
            uses = f"{c['used_count']}/{c['max_uses']}" if c["max_uses"] else f"{c['used_count']}/∞"
            valid = f" до {c['valid_to']}" if c.get("valid_to") else ""
            text += f"  {status} {c['code']} | {disc} | {uses}{valid}\n"
    else:
        text += "Нет промокодов"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for c in codes[:8]:
        rows.append([InlineKeyboardButton(
            text=f"🗑 {c['code']}",
            callback_data=f"adm_del_promo:{c['code']}"
        )])
    rows.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm:create_promo")])
    rows.append([InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "adm:create_promo")
async def adm_create_promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎫 Создание промокода\n\nВведи код (буквы/цифры, мин. 3 символа):"
    )
    await state.set_state(AdminStates.creating_promo_code)
    await callback.answer()


@router.message(AdminStates.creating_promo_code)
async def adm_promo_code_name(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if not code.isalnum() or len(code) < 3:
        await message.answer("Код должен быть от 3 символов (буквы/цифры):")
        return

    existing = await db.get_promo_code(code)
    if existing:
        await message.answer("Этот код уже существует. Введи другой:")
        return

    await state.update_data(promo_code=code)
    await message.answer(
        f"Код: {code}\n\nВведи скидку — процент (напр. 10%) или сумму (напр. 500):"
    )
    await state.set_state(AdminStates.promo_discount)


@router.message(AdminStates.promo_discount)
async def adm_promo_discount(message: Message, state: FSMContext):
    text = message.text.strip()
    discount_percent = 0
    discount_amount = 0

    if "%" in text:
        try:
            discount_percent = int(text.replace("%", "").strip())
            if discount_percent < 1 or discount_percent > 100:
                raise ValueError
        except ValueError:
            await message.answer("Введи процент 1-100 (напр. 15%):")
            return
    else:
        try:
            discount_amount = int(text.replace("₽", "").replace("р", "").strip())
            if discount_amount < 1:
                raise ValueError
        except ValueError:
            await message.answer("Введи сумму (напр. 500) или процент (напр. 10%):")
            return

    await state.update_data(promo_percent=discount_percent, promo_amount=discount_amount)
    await message.answer("Макс. использований (0 = безлимит):")
    await state.set_state(AdminStates.promo_max_uses)


@router.message(AdminStates.promo_max_uses)
async def adm_promo_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text.strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи число (0 = безлимит):")
        return

    data = await state.get_data()
    code = data["promo_code"]

    await db.create_promo_code(
        code=code,
        discount_percent=data["promo_percent"],
        discount_amount=data["promo_amount"],
        max_uses=max_uses,
        created_by=message.from_user.id,
    )
    await db.add_admin_log(message.from_user.id, "create_promo", f"Промокод {code}")
    await state.clear()

    disc = f"-{data['promo_percent']}%" if data["promo_percent"] else f"-{data['promo_amount']}₽"
    uses = f"макс. {max_uses}" if max_uses else "безлимит"
    await message.answer(
        f"✅ Промокод создан!\n\n🎫 {code}\n💰 {disc}\n🔢 {uses}",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data.startswith("adm_del_promo:"))
async def adm_delete_promo(callback: CallbackQuery):
    code = callback.data.split(":", 1)[1]
    await db.delete_promo_code(code)
    await db.add_admin_log(callback.from_user.id, "delete_promo", f"Удалён {code}")
    await callback.answer(f"🗑 {code} удалён", show_alert=True)
    await adm_promo_codes(callback)


# ═══════════════════════════════════════════════════════════
#  ADMIN LOGS
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:logs")
async def adm_logs(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    logs = await db.get_admin_logs(30)
    text = f"📜 Журнал действий\n{'─' * 28}\n\n"

    if logs:
        for log in logs:
            name = log.get("full_name") or str(log["admin_telegram_id"])
            time_str = log["created_at"][5:16]
            text += f"  {time_str} | {name}\n  → {log['action']}: {log.get('details', '')}\n\n"
    else:
        text += "Пока нет записей"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  CONSOLE MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:consoles")
async def adm_consoles(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    from config import CONSOLES
    await db.init_consoles(CONSOLES)
    consoles = await db.get_consoles()

    status_icons = {"active": "🟢", "maintenance": "🟡", "broken": "🔴"}
    text = f"🎮 Консоли\n{'─' * 28}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for c in consoles:
        icon = status_icons.get(c["status"], "⚪")
        note = f" — {c['note']}" if c.get("note") else ""
        text += f"  {icon} {c['name']}: {c['status']}{note}\n"
        rows.append([
            InlineKeyboardButton(text=f"🟢", callback_data=f"adm_con:active:{c['name']}"),
            InlineKeyboardButton(text=f"🟡", callback_data=f"adm_con:maintenance:{c['name']}"),
            InlineKeyboardButton(text=f"🔴", callback_data=f"adm_con:broken:{c['name']}"),
            InlineKeyboardButton(text=c["name"], callback_data="ignore"),
        ])

    rows.append([InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_con:"))
async def adm_console_status(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    new_status = parts[1]
    console_name = parts[2]

    if new_status == "broken":
        await state.update_data(console_name=console_name, console_status=new_status)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Без описания", callback_data="console_no_note")]
        ])
        await callback.message.edit_text(
            f"🔴 {console_name} → поломка\n\nОпиши проблему:",
            reply_markup=kb,
        )
        await state.set_state(AdminStates.console_note)
        await callback.answer()
        return

    await db.update_console_status(console_name, new_status)
    await db.add_admin_log(callback.from_user.id, "console", f"{console_name} → {new_status}")
    await callback.answer(f"✅ {console_name} → {new_status}", show_alert=True)
    await adm_consoles(callback)


@router.callback_query(F.data == "console_no_note")
async def adm_console_no_note(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.update_console_status(data["console_name"], data["console_status"])
    await db.add_admin_log(callback.from_user.id, "console", f"{data['console_name']} → broken")
    await state.clear()
    await callback.answer("🔴 Отмечено", show_alert=True)
    await adm_consoles(callback)


@router.message(AdminStates.console_note)
async def adm_console_note_save(message: Message, state: FSMContext):
    data = await state.get_data()
    note = message.text.strip()
    await db.update_console_status(data["console_name"], data["console_status"], note)
    await db.add_admin_log(message.from_user.id, "console",
                           f"{data['console_name']} → {data['console_status']}: {note}")
    await state.clear()
    await message.answer(
        f"🔴 {data['console_name']} — поломка.\n{'Проблема: ' + note if note else ''}",
        reply_markup=admin_menu_kb(),
    )


# ═══════════════════════════════════════════════════════════
#  USER NOTES
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_note:"))
async def adm_add_note(callback: CallbackQuery, state: FSMContext):
    tg_id = int(callback.data.split(":")[1])
    user = await db.get_user(tg_id)
    if not user:
        await callback.answer("Не найден", show_alert=True)
        return

    await state.update_data(note_user_id=user["id"], note_user_tg=tg_id, note_user_name=user["full_name"])
    await callback.message.edit_text(f"📝 Заметка о {user['full_name']}\n\nВведи текст:")
    await state.set_state(AdminStates.adding_user_note)
    await callback.answer()


@router.message(AdminStates.adding_user_note)
async def adm_save_note(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_user_note(data["note_user_id"], message.from_user.id, message.text)
    await db.add_admin_log(message.from_user.id, "user_note",
                           f"Заметка о {data['note_user_name']}")
    await state.clear()
    await message.answer(
        f"📝 Заметка о {data['note_user_name']} сохранена.",
        reply_markup=admin_menu_kb(),
    )


# ═══════════════════════════════════════════════════════════
#  TARGETED PROMO
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:targeted_promo")
async def adm_targeted_promo(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    vip = await db.get_vip_users(5)
    inactive = await db.get_inactive_users(30)
    bday = await db.get_users_with_birthday_soon(7)
    all_users = await db.get_all_users()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🌟 VIP (5+ визитов) — {len(vip)}", callback_data="adm_target:vip")],
        [InlineKeyboardButton(text=f"😴 Неактивные (30д) — {len(inactive)}", callback_data="adm_target:inactive")],
        [InlineKeyboardButton(text=f"🎂 Именинники (7д) — {len(bday)}", callback_data="adm_target:birthday")],
        [InlineKeyboardButton(text=f"📢 Все — {len(all_users)}", callback_data="adm_target:all")],
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])
    await callback.message.edit_text(
        f"🎯 Целевая рассылка\n{'─' * 28}\n\nВыбери сегмент:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_target:"))
async def adm_target_segment(callback: CallbackQuery, state: FSMContext):
    segment = callback.data.split(":")[1]
    await state.update_data(target_segment=segment)

    names = {"vip": "VIP", "inactive": "Неактивные", "birthday": "Именинники", "all": "Все"}
    await callback.message.edit_text(f"🎯 Сегмент: {names.get(segment)}\n\nВведи текст сообщения:")
    await state.set_state(AdminStates.targeted_promo_text)
    await callback.answer()


@router.message(AdminStates.targeted_promo_text)
async def adm_send_targeted(message: Message, state: FSMContext):
    data = await state.get_data()
    segment = data["target_segment"]
    text = message.text

    if segment == "vip":
        users = await db.get_vip_users(5)
    elif segment == "inactive":
        users = await db.get_inactive_users(30)
    elif segment == "birthday":
        users = await db.get_users_with_birthday_soon(7)
    else:
        users = await db.get_all_users()

    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(user["telegram_id"], f"📢 {text}\n\n— Scorpion Platinum")
            sent += 1
        except Exception:
            failed += 1

    await db.add_admin_log(message.from_user.id, "targeted_promo",
                           f"Сегмент: {segment}, отправлено: {sent}")
    await state.clear()
    await message.answer(
        f"✅ Целевая рассылка\n📤 Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=admin_menu_kb(),
    )


# ═══════════════════════════════════════════════════════════
#  SETTINGS EDITOR
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_set:"))
async def adm_edit_setting(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    setting = callback.data.split(":")[1]
    current = {
        "price": PRICE_PER_HOUR,
        "fullday": 12000,
        "hours_start": 10,
        "hours_end": 3,
        "capacity": MAX_CAPACITY,
    }
    names = {
        "price": "Цена за час (₽)",
        "fullday": "Цена за сутки (₽)",
        "hours_start": "Час открытия (0-23)",
        "hours_end": "Час закрытия (0-23)",
        "capacity": "Макс. гостей",
    }

    import config
    if setting == "fullday":
        cur_val = config.PRICE_FULL_DAY
    elif setting == "hours_start":
        cur_val = config.WORK_HOURS_START
    elif setting == "hours_end":
        cur_val = config.WORK_HOURS_END
    else:
        cur_val = current.get(setting, "?")

    await state.update_data(setting_name=setting)
    await callback.message.edit_text(
        f"⚙️ {names.get(setting, setting)}\nТекущее: {cur_val}\n\nВведи новое значение:"
    )
    await state.set_state(AdminStates.editing_setting)
    await callback.answer()


@router.message(AdminStates.editing_setting)
async def adm_save_setting(message: Message, state: FSMContext):
    import config as cfg
    data = await state.get_data()
    setting = data["setting_name"]

    try:
        value = int(message.text.strip())
        if value < 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи положительное число:")
        return

    attr_map = {
        "price": "PRICE_PER_HOUR",
        "fullday": "PRICE_FULL_DAY",
        "hours_start": "WORK_HOURS_START",
        "hours_end": "WORK_HOURS_END",
        "capacity": "MAX_CAPACITY",
    }

    attr = attr_map.get(setting)
    if attr:
        setattr(cfg, attr, value)
        try:
            import re as _re
            config_path = "/opt/scorpion-bot/config.py"
            with open(config_path) as f:
                cfg_content = f.read()
            cfg_content = _re.sub(
                rf'^{attr}\s*=\s*\d+',
                f'{attr} = {value}',
                cfg_content,
                flags=_re.MULTILINE,
            )
            with open(config_path, 'w') as f:
                f.write(cfg_content)
        except Exception as e:
            await message.answer(f"⚠️ В памяти обновлено, файл: {e}")

    await db.add_admin_log(message.from_user.id, "setting", f"{setting} = {value}")
    await state.clear()
    await message.answer(f"✅ {setting} → {value}", reply_markup=admin_menu_kb())


# ═══════════════════════════════════════════════════════════
#  TOP CUSTOMERS
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:top_customers")
async def adm_top_customers(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    top = await db.get_top_customers(15)
    text = f"🏆 Топ клиентов\n{'─' * 28}\n\n"

    if top:
        for i, u in enumerate(top, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            text += (
                f"  {medal} {u['full_name']} — "
                f"{u['booking_count']} бр. | {u['total_spent']:,}₽ | "
                f"{u['visits_count']} визитов\n"
            )
    else:
        text += "Нет данных"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К статистике", callback_data="adm:stats")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════════════
#  MONTHLY REPORT
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "adm:monthly")
async def adm_monthly_report(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    today = date.today()
    report = await db.get_monthly_report(today.year, today.month)

    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }

    base_rev = report["revenue"] - report["extras_revenue"]
    avg_bk = report["revenue"] // report["bookings"] if report["bookings"] else 0
    avg_guest = report["revenue"] // report["guests"] if report["guests"] else 0

    text = (
        f"📊 {month_names[today.month]} {today.year}\n"
        f"{'─' * 28}\n\n"
        f"📋 Бронирований: {report['bookings']}\n"
        f"👥 Гостей: {report['guests']}\n"
        f"⏳ Часов: {report['hours']}\n"
        f"❌ Отмен: {report['cancellations']}\n"
        f"🚷 Неявок: {report['noshows']}\n"
        f"👤 Новых: {report['new_users']}\n\n"
        f"💰 Финансы:\n"
        f"  Выручка: {report['revenue']:,}₽\n"
        f"  Аренда: {base_rev:,}₽\n"
        f"  Допы: {report['extras_revenue']:,}₽\n"
        f"  Ср. чек: {avg_bk:,}₽\n"
        f"  Ср./гость: {avg_guest:,}₽\n"
    )

    prev_m = today.month - 1 if today.month > 1 else 12
    prev_y = today.year if today.month > 1 else today.year - 1
    prev = await db.get_monthly_report(prev_y, prev_m)

    if prev["revenue"] > 0:
        change = ((report["revenue"] - prev["revenue"]) / prev["revenue"]) * 100
        icon = "📈" if change >= 0 else "📉"
        text += f"\n{icon} vs {month_names[prev_m]}: {change:+.0f}%\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К статистике", callback_data="adm:stats")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
