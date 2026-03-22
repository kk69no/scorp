"""
View, cancel, reschedule bookings.
"""

from datetime import date, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from states import RescheduleStates
from keyboards import (
    my_bookings_kb, booking_actions_kb, main_menu_kb,
    calendar_kb, time_slots_kb,
)
from config import WEEKDAYS_RU

router = Router()


@router.message(F.text == "📋 Мои брони")
async def my_bookings(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    active = await db.get_user_bookings(message.from_user.id, active_only=True)
    all_bookings = await db.get_user_bookings(message.from_user.id, active_only=False)

    if not all_bookings:
        await message.answer(
            "У тебя пока нет бронирований.\nНажми «📅 Забронировать»!",
            reply_markup=main_menu_kb(),
        )
        return

    text = "📋 Твои бронирования:\n\n"

    if active:
        text += "🟢 Активные:\n"
        for b in active:
            d = date.fromisoformat(b["booking_date"])
            wd = WEEKDAYS_RU[d.weekday()]
            text += (
                f"  #{b['id']} — {b['booking_date']} ({wd}) "
                f"{b['start_time']}–{b['end_time']} | "
                f"👥 {b['guests_count']} | 💵 {b['total_price']}₽\n"
            )

    # Show recent history
    completed = [b for b in all_bookings if b["status"] == "completed"][:5]
    if completed:
        text += "\n📜 Последние визиты:\n"
        for b in completed:
            text += f"  #{b['id']} — {b['booking_date']} | {b['total_price']}₽ ✅\n"

    cancelled = [b for b in all_bookings if b["status"] == "cancelled"][:3]
    if cancelled:
        text += "\n❌ Отменённые:\n"
        for b in cancelled:
            text += f"  #{b['id']} — {b['booking_date']}\n"

    await message.answer(
        text,
        reply_markup=my_bookings_kb(active) if active else main_menu_kb(),
    )


@router.callback_query(F.data == "back_to_my_bookings")
async def back_to_my_bookings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    active = await db.get_user_bookings(callback.from_user.id, active_only=True)
    if active:
        await callback.message.edit_text(
            "📋 Активные брони:",
            reply_markup=my_bookings_kb(active),
        )
    else:
        await callback.message.edit_text("Нет активных броней.")
    await callback.answer()


# ─── View booking details ────────────────────────────────

@router.callback_query(F.data.startswith("view_booking:"))
async def view_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Бронь не найдена", show_alert=True)
        return

    d = date.fromisoformat(booking["booking_date"])
    wd = WEEKDAYS_RU[d.weekday()]

    text = (
        f"📋 Бронь #{booking['id']}\n"
        f"{'─' * 28}\n"
        f"📅 {booking['booking_date']} ({wd})\n"
        f"⏰ {booking['start_time']} — {booking['end_time']} ({booking['duration_hours']} ч.)\n"
        f"👥 Гостей: {booking['guests_count']}\n"
        f"📌 Статус: {_status_text(booking['status'])}\n"
    )

    if booking.get("extras"):
        text += "\n🛒 Допы:\n"
        for ext in booking["extras"]:
            cat_emoji = {"hookah": "🔥", "drinks": "🥤", "food": "🍕"}.get(ext["category"], "•")
            text += f"  {cat_emoji} {ext['item_name']} — {ext['price']}₽\n"

    text += (
        f"\n💰 Комната: {booking['base_price']}₽\n"
        f"🛒 Допы: {booking['extras_price']}₽\n"
    )
    if booking["discount"]:
        text += f"🎁 Скидка: −{booking['discount']}₽\n"
    text += f"💵 Итого: {booking['total_price']}₽\n"

    if booking["status"] in ("confirmed", "pending"):
        await callback.message.edit_text(text, reply_markup=booking_actions_kb(booking_id))
    else:
        await callback.message.edit_text(text)
    await callback.answer()


def _status_text(status: str) -> str:
    return {
        "pending": "⏳ Ожидание",
        "confirmed": "✅ Подтверждена",
        "completed": "✅ Завершена",
        "cancelled": "❌ Отменена",
        "no_show": "🚷 Неявка",
    }.get(status, status)


# ─── Cancel booking ──────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_bk:"))
async def cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    success = await db.cancel_booking(booking_id)
    if success:
        await callback.message.edit_text(f"❌ Бронь #{booking_id} отменена.")

        # Notify admins
        booking = await db.get_booking(booking_id)
        if booking:
            user = await db.get_user_by_id(booking["user_id"])
            all_users = await db.get_all_users()
            from config import ADMIN_IDS
            for admin_id in ADMIN_IDS:
                try:
                    await callback.bot.send_message(
                        admin_id,
                        f"❌ Бронь #{booking_id} отменена клиентом\n"
                        f"👤 {user['full_name'] if user else '?'}\n"
                        f"📅 {booking['booking_date']} {booking['start_time']}",
                    )
                except Exception:
                    pass
            for u in all_users:
                if u["is_admin"] and u["telegram_id"] not in ADMIN_IDS:
                    try:
                        await callback.bot.send_message(
                            u["telegram_id"],
                            f"❌ Бронь #{booking_id} отменена клиентом\n"
                            f"👤 {user['full_name'] if user else '?'}\n"
                            f"📅 {booking['booking_date']} {booking['start_time']}",
                        )
                    except Exception:
                        pass
    else:
        await callback.answer("Не удалось отменить бронь", show_alert=True)
    await callback.answer()


# ─── Reschedule booking ──────────────────────────────────

@router.callback_query(F.data.startswith("reschedule:"))
async def reschedule_start(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Бронь не найдена", show_alert=True)
        return

    await state.update_data(
        reschedule_booking_id=booking_id,
        duration=booking["duration_hours"],
        guests=booking["guests_count"],
    )

    await callback.message.edit_text(
        f"📅 Перенос брони #{booking_id}\n\nВыбери новую дату:",
        reply_markup=calendar_kb(0),
    )
    await state.set_state(RescheduleStates.choosing_date)
    await callback.answer()


@router.callback_query(RescheduleStates.choosing_date, F.data.startswith("date:"))
async def reschedule_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[1]
    if await db.is_date_blocked(date_str):
        await callback.answer("⛔ Дата закрыта", show_alert=True)
        return

    await state.update_data(new_date=date_str)

    # Show available times
    from handlers.booking import _get_work_hours
    data = await state.get_data()
    duration = data.get("duration", 1)
    all_slots = _get_work_hours()
    available = []
    for slot in all_slots:
        cap = await db.get_available_capacity(date_str, slot, duration)
        if cap >= data.get("guests", 1):
            available.append(slot)

    if not available:
        await callback.answer("Нет свободных слотов на эту дату", show_alert=True)
        return

    await callback.message.edit_text(
        f"📅 Новая дата: {date_str}\n\n⏰ Выбери время:",
        reply_markup=time_slots_kb(available),
    )
    await state.set_state(RescheduleStates.choosing_time)
    await callback.answer()


@router.callback_query(RescheduleStates.choosing_time, F.data.startswith("time:"))
async def reschedule_time(callback: CallbackQuery, state: FSMContext):
    new_time = callback.data.split(":")[1] + ":00"
    data = await state.get_data()
    booking_id = data["reschedule_booking_id"]

    # Cancel old booking
    await db.cancel_booking(booking_id)

    # Get old booking details for re-creating
    old_booking = await db.get_booking(booking_id)
    if not old_booking:
        await callback.message.edit_text("Ошибка: бронь не найдена.")
        await state.clear()
        return

    duration = data["duration"]
    start_h = int(new_time.split(":")[0])
    end_h = (start_h + duration) % 24
    end_time = f"{end_h:02d}:00"

    from handlers.booking import _calc_price
    base_price = _calc_price(data["new_date"], new_time, duration)
    total_price = base_price + old_booking["extras_price"] - old_booking["discount"]
    total_price = max(0, total_price)

    new_id = await db.create_booking(
        user_id=old_booking["user_id"],
        booking_date=data["new_date"],
        start_time=new_time,
        end_time=end_time,
        duration_hours=duration,
        guests_count=data["guests"],
        base_price=base_price,
        extras_price=old_booking["extras_price"],
        discount=old_booking["discount"],
        total_price=total_price,
        extras=old_booking.get("extras"),
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ Бронь перенесена!\n\n"
        f"Старая: #{booking_id} — отменена\n"
        f"Новая: #{new_id} — {data['new_date']} {new_time}–{end_time}\n"
        f"💵 {total_price}₽"
    )
    await callback.message.answer("Главное меню 👇", reply_markup=main_menu_kb())
    await callback.answer()


# Calendar nav for reschedule
@router.callback_query(RescheduleStates.choosing_date, F.data.startswith("cal_prev:"))
async def reschedule_cal_prev(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(max(0, offset - 1)))
    await callback.answer()


@router.callback_query(RescheduleStates.choosing_date, F.data.startswith("cal_next:"))
async def reschedule_cal_next(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(min(offset + 1, 2)))
    await callback.answer()
