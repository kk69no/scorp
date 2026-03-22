"""
Admin panel: view bookings, stats, blacklist, promos, no-shows.
"""

from datetime import date, timedelta, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import database as db
from states import AdminStates
from keyboards import (
    admin_menu_kb, admin_bookings_list_kb, admin_confirm_kb, main_menu_kb,
    calendar_kb,
)
from config import ADMIN_IDS, WEEKDAYS_RU, LOYALTY_VISIT_POINTS

router = Router()


async def _check_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    return await db.is_admin(user_id)


# ─── /admin ──────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()

    # Auto-register first admin
    if not ADMIN_IDS:
        user = await db.get_user(message.from_user.id)
        if user:
            await db.set_admin(message.from_user.id)
            ADMIN_IDS.append(message.from_user.id)
            await message.answer(
                "🔑 Ты назначен администратором!\n\n"
                "Админ-панель 👇",
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


# ─── Today's bookings ───────────────────────────────────

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
        f"Всего: {len(bookings)} | 👥 {total_guests} чел. | 💵 {total_revenue}₽\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_bookings_list_kb(bookings, "view"),
    )
    await callback.answer()


# ─── Week bookings ───────────────────────────────────────

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
            text += f"{marker}{d_str} ({wd}): {count} бр. | 👥 {guests} | 💵 {revenue}₽\n"
        else:
            text += f"{marker}{d_str} ({wd}): —\n"

    text += f"\n💰 Итого за неделю: {total_all}₽"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ─── Block date ──────────────────────────────────────────

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


# Calendar nav for admin
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


# ─── Stats ───────────────────────────────────────────────

@router.callback_query(F.data == "adm:stats")
async def adm_stats(callback: CallbackQuery):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    stats = await db.get_stats()

    text = (
        f"📊 Статистика\n"
        f"{'─' * 28}\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📋 Активных броней: {stats['active_bookings']}\n"
        f"✅ Завершённых: {stats['completed_bookings']}\n"
        f"📌 Сегодня: {stats['today_bookings']}\n"
        f"🚷 Неявок: {stats['noshows']}\n\n"
        f"💰 Доход:\n"
        f"  За всё время: {stats['total_revenue']:,}₽\n"
        f"  За 30 дней: {stats['month_revenue']:,}₽\n"
        f"  Средний чек: {stats['avg_check']:,}₽\n\n"
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
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ─── Blacklist ───────────────────────────────────────────

@router.callback_query(F.data == "adm:blacklist")
async def adm_blacklist(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    all_users = await db.get_all_users()
    # Get blacklisted separately
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
                text=f"🔓 Разблокировать {u['full_name']}",
                callback_data=f"adm_unban:{u['telegram_id']}"
            )])
    else:
        text += "Пусто ✅"

    rows.append([InlineKeyboardButton(text="➕ Добавить в ЧС", callback_data="adm:add_blacklist")])
    rows.append([InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_unban:"))
async def adm_unban(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    await db.unblacklist_user(tg_id)
    await callback.answer("✅ Пользователь разблокирован", show_alert=True)
    # Refresh the blacklist view
    await adm_blacklist(callback, None)


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
        await message.answer("Пользователь не найден в базе.")
        await state.clear()
        return

    await db.blacklist_user(tg_id)
    await state.clear()
    await message.answer(
        f"⛔ {user['full_name']} добавлен в чёрный список.",
        reply_markup=admin_menu_kb(),
    )


# ─── Promo broadcast ────────────────────────────────────

@router.callback_query(F.data == "adm:promo")
async def adm_promo(callback: CallbackQuery, state: FSMContext):
    if not await _check_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    await callback.message.edit_text(
        "📢 Рассылка\n\n"
        "Напиши текст сообщения для всех пользователей:"
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


# ─── Complete booking ────────────────────────────────────

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

    # Award loyalty
    user = await db.get_user_by_id(booking["user_id"])
    if user:
        visits = await db.increment_visits(user["telegram_id"])
        await db.add_loyalty_points(user["telegram_id"], LOYALTY_VISIT_POINTS)

        # Notify user
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


# ─── No-show ─────────────────────────────────────────────

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


# ─── View booking from admin ─────────────────────────────

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
        f"💵 {booking['total_price']}₽\n"
        f"📌 Статус: {booking['status']}\n"
    )

    if booking.get("extras"):
        text += "\n🛒 Допы:\n"
        for ext in booking["extras"]:
            text += f"  • {ext['item_name']} — {ext['price']}₽\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:today")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
