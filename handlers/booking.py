"""
Full booking flow:
Date -> Time -> Duration -> Guests -> Extras -> Confirmation
"""

from datetime import date, datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from states import BookingStates
from config import (
    WORK_HOURS_START, WORK_HOURS_END, MAX_CAPACITY, MAX_BOOKING_HOURS,
    PRICE_PER_HOUR, PRICE_FULL_DAY,
    EXTRAS_HOOKAH, EXTRAS_DRINKS, EXTRAS_FOOD,
    BIRTHDAY_DISCOUNT_PERCENT, FREE_HOUR_EVERY_N_VISITS,
    LOYALTY_VISIT_POINTS, VENUE_NAME, DELIVERY_NOTE,
)
from keyboards import (
    calendar_kb, time_slots_kb, duration_kb, guests_kb,
    extras_menu_kb, extras_items_kb, confirmation_kb, main_menu_kb,
)

router = Router()


def _get_work_hours() -> list[str]:
    """Generate list of working hour slots like ['10:00', '11:00', ..., '02:00']."""
    slots = []
    if WORK_HOURS_END <= WORK_HOURS_START:
        for h in range(WORK_HOURS_START, 24):
            slots.append(f"{h:02d}:00")
        for h in range(0, WORK_HOURS_END):
            slots.append(f"{h:02d}:00")
    else:
        for h in range(WORK_HOURS_START, WORK_HOURS_END):
            slots.append(f"{h:02d}:00")
    return slots


def _max_duration_from(start_time: str) -> int:
    """Max consecutive hours from start_time until closing."""
    all_slots = _get_work_hours()
    try:
        idx = all_slots.index(start_time)
    except ValueError:
        return 1
    return min(len(all_slots) - idx, MAX_BOOKING_HOURS)


def _calc_price(booking_date: str, start_time: str, duration: int, is_full_day: bool = False) -> int:
    """Calculate base price. Full day = flat rate."""
    if is_full_day:
        return PRICE_FULL_DAY
    return PRICE_PER_HOUR * duration


# ─── Start booking ───────────────────────────────────────

@router.message(F.text == "📅 Забронировать")
async def start_booking(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return
    if user["is_blacklisted"]:
        await message.answer("⛔ Ваш аккаунт заблокирован.")
        return

    await state.clear()
    await state.update_data(
        selected_extras={"hookah": [], "drinks": [], "food": []},
        is_full_day=False,
    )
    await message.answer(
        "📅 Выбери дату:",
        reply_markup=calendar_kb(0),
    )
    await state.set_state(BookingStates.choosing_date)


# ─── Quick rebook ────────────────────────────────────────

@router.message(F.text == "🔄 Как в прошлый раз")
async def quick_rebook(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    last = await db.get_last_booking(message.from_user.id)
    if not last:
        await message.answer(
            "У тебя пока нет завершённых бронирований.\n"
            "Нажми «📅 Забронировать» для первой брони!",
            reply_markup=main_menu_kb(),
        )
        return

    extras_list = []
    for ext in last.get("extras", []):
        extras_list.append(ext["item_name"])

    extras_text = ", ".join(extras_list) if extras_list else "без допов"

    await state.clear()
    await state.update_data(
        selected_extras={
            "hookah": [e["item_name"] for e in last.get("extras", []) if e["category"] == "hookah"],
            "drinks": [e["item_name"] for e in last.get("extras", []) if e["category"] == "drinks"],
            "food": [e["item_name"] for e in last.get("extras", []) if e["category"] == "food"],
        },
        duration=last["duration_hours"],
        guests=last["guests_count"],
        is_full_day=False,
        rebook=True,
    )

    await message.answer(
        f"🔄 Прошлая бронь:\n"
        f"⏰ {last['duration_hours']} ч. | 👥 {last['guests_count']} чел.\n"
        f"🛒 {extras_text}\n\n"
        f"Выбери дату для повторной брони:",
        reply_markup=calendar_kb(0),
    )
    await state.set_state(BookingStates.choosing_date)


# ─── Calendar navigation ────────────────────────────────

@router.callback_query(BookingStates.choosing_date, F.data.startswith("cal_prev:"))
async def cal_prev(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    new_offset = max(0, offset - 1)
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(new_offset))
    await callback.answer()


@router.callback_query(BookingStates.choosing_date, F.data.startswith("cal_next:"))
async def cal_next(callback: CallbackQuery):
    offset = int(callback.data.split(":")[1])
    new_offset = min(offset + 1, 2)
    await callback.message.edit_reply_markup(reply_markup=calendar_kb(new_offset))
    await callback.answer()


@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    await callback.answer()


# ─── Date selected ───────────────────────────────────────

@router.callback_query(BookingStates.choosing_date, F.data.startswith("date:"))
async def date_selected(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[1]
    selected = date.fromisoformat(date_str)

    if await db.is_date_blocked(date_str):
        await callback.answer("⛔ Эта дата закрыта для бронирования", show_alert=True)
        return

    await state.update_data(booking_date=date_str)

    # Filter available time slots
    all_slots = _get_work_hours()
    now = datetime.now()
    available = []

    for slot in all_slots:
        h = int(slot.split(":")[0])
        if selected == date.today():
            if h <= WORK_HOURS_START and h < WORK_HOURS_END:
                slot_dt = datetime.combine(selected + timedelta(days=1), datetime.strptime(slot, "%H:%M").time())
            else:
                slot_dt = datetime.combine(selected, datetime.strptime(slot, "%H:%M").time())
            if slot_dt <= now + timedelta(hours=1):
                continue

        capacity = await db.get_available_capacity(date_str, slot, 1)
        if capacity > 0:
            available.append(slot)

    if not available:
        await callback.answer("На эту дату нет свободных слотов 😔", show_alert=True)
        return

    from config import WEEKDAYS_RU
    wd = WEEKDAYS_RU[selected.weekday()]
    await callback.message.edit_text(
        f"📅 Дата: {date_str} ({wd})\n\n⏰ Выбери время начала:",
        reply_markup=time_slots_kb(available),
    )
    await state.set_state(BookingStates.choosing_time)
    await callback.answer()


# ─── Back buttons ────────────────────────────────────────

@router.callback_query(F.data == "back_to_date")
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📅 Выбери дату:", reply_markup=calendar_kb(0))
    await state.set_state(BookingStates.choosing_date)
    await callback.answer()


@router.callback_query(F.data == "back_to_time")
async def back_to_time(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    date_str = data.get("booking_date", "")
    all_slots = _get_work_hours()
    available = []
    for slot in all_slots:
        capacity = await db.get_available_capacity(date_str, slot, 1)
        if capacity > 0:
            available.append(slot)
    await callback.message.edit_text(
        f"📅 Дата: {date_str}\n\n⏰ Выбери время начала:",
        reply_markup=time_slots_kb(available),
    )
    await state.set_state(BookingStates.choosing_time)
    await callback.answer()


@router.callback_query(F.data == "back_to_duration")
async def back_to_duration(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    max_h = _max_duration_from(data.get("start_time", "10:00"))
    await callback.message.edit_text(
        f"📅 {data['booking_date']} в {data['start_time']}\n\n⏳ На сколько часов?",
        reply_markup=duration_kb(max_h),
    )
    await state.set_state(BookingStates.choosing_duration)
    await callback.answer()


@router.callback_query(F.data == "back_to_guests")
async def back_to_guests(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    max_g = await db.get_available_capacity(
        data["booking_date"], data["start_time"], data["duration"]
    )
    max_g = min(max_g, MAX_CAPACITY)
    await callback.message.edit_text(
        f"📅 {data['booking_date']} в {data['start_time']} ({data['duration']}ч)\n\n"
        f"👥 Сколько гостей? (макс. {max_g})",
        reply_markup=guests_kb(max_g),
    )
    await state.set_state(BookingStates.choosing_guests)
    await callback.answer()


@router.callback_query(F.data == "back_to_extras")
async def back_to_extras(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        "🛒 Добавить что-нибудь к бронированию?",
        reply_markup=extras_menu_kb(data.get("selected_extras")),
    )
    await state.set_state(BookingStates.choosing_extras_menu)
    await callback.answer()


# ─── Time selected ───────────────────────────────────────

@router.callback_query(BookingStates.choosing_time, F.data.startswith("time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext):
    start_time = callback.data.split(":")[1] + ":00"
    await state.update_data(start_time=start_time)

    data = await state.get_data()

    # Check if this is a rebook with pre-set duration
    if data.get("rebook") and data.get("duration"):
        max_h = _max_duration_from(start_time)
        if data["duration"] > max_h:
            await state.update_data(duration=max_h)

        max_g = await db.get_available_capacity(
            data["booking_date"], start_time, data.get("duration", 1)
        )
        if data.get("guests", 1) > max_g:
            await state.update_data(guests=max_g)

        await _show_confirmation(callback, state)
        return

    max_h = _max_duration_from(start_time)
    await callback.message.edit_text(
        f"📅 {data['booking_date']} в {start_time}\n\n"
        f"⏳ На сколько часов? (мин. 3 ч.)",
        reply_markup=duration_kb(max_h),
    )
    await state.set_state(BookingStates.choosing_duration)
    await callback.answer()


# ─── Duration selected ───────────────────────────────────

@router.callback_query(BookingStates.choosing_duration, F.data == "dur:fullday")
async def duration_fullday(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    max_h = _max_duration_from(data["start_time"])
    await state.update_data(duration=max_h, is_full_day=True)

    max_guests = await db.get_available_capacity(
        data["booking_date"], data["start_time"], max_h
    )
    max_guests = min(max_guests, MAX_CAPACITY)

    if max_guests < 1:
        await callback.answer("Нет мест на выбранное время 😔", show_alert=True)
        return

    await callback.message.edit_text(
        f"📅 {data['booking_date']} — СУТКИ 🌟\n\n"
        f"👥 Сколько гостей? (макс. {max_guests})",
        reply_markup=guests_kb(max_guests),
    )
    await state.set_state(BookingStates.choosing_guests)
    await callback.answer()


@router.callback_query(BookingStates.choosing_duration, F.data.startswith("dur:"))
async def duration_selected(callback: CallbackQuery, state: FSMContext):
    duration = int(callback.data.split(":")[1])
    await state.update_data(duration=duration, is_full_day=False)

    data = await state.get_data()
    max_guests = await db.get_available_capacity(
        data["booking_date"], data["start_time"], duration
    )
    max_guests = min(max_guests, MAX_CAPACITY)

    if max_guests < 1:
        await callback.answer("Нет мест на выбранное время 😔", show_alert=True)
        return

    await callback.message.edit_text(
        f"📅 {data['booking_date']} в {data['start_time']} ({duration}ч)\n\n"
        f"👥 Сколько гостей? (макс. {max_guests})",
        reply_markup=guests_kb(max_guests),
    )
    await state.set_state(BookingStates.choosing_guests)
    await callback.answer()


# ─── Guests selected ─────────────────────────────────────

@router.callback_query(BookingStates.choosing_guests, F.data.startswith("guests:"))
async def guests_selected(callback: CallbackQuery, state: FSMContext):
    guests = int(callback.data.split(":")[1])
    await state.update_data(guests=guests)

    data = await state.get_data()

    # If no extras available at all, go straight to confirmation
    has_extras = bool(EXTRAS_HOOKAH or EXTRAS_DRINKS or EXTRAS_FOOD)
    if not has_extras:
        await _show_confirmation(callback, state)
        return

    await callback.message.edit_text(
        f"📅 {data['booking_date']} в {data['start_time']} ({data['duration']}ч) | 👥 {guests}\n\n"
        "🛒 Добавить что-нибудь к бронированию?",
        reply_markup=extras_menu_kb(data.get("selected_extras")),
    )
    await state.set_state(BookingStates.choosing_extras_menu)
    await callback.answer()


# ─── Extras ──────────────────────────────────────────────

@router.callback_query(BookingStates.choosing_extras_menu, F.data.startswith("extras:"))
async def extras_category(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "done" or action == "skip":
        await _show_confirmation(callback, state)
        return

    data = await state.get_data()
    selected = data.get("selected_extras", {})
    category_selected = selected.get(action, [])

    cat_names = {"hookah": "🔥 Кальян", "drinks": "🥤 Напитки", "food": "🍕 Еда"}
    await callback.message.edit_text(
        f"{cat_names.get(action, action)} — выбери позиции:\n(нажми ещё раз чтобы убрать)",
        reply_markup=extras_items_kb(action, category_selected),
    )
    await state.update_data(current_extras_category=action)
    await callback.answer()


@router.callback_query(BookingStates.choosing_extras_menu, F.data.startswith("ext_item:"))
async def extras_item_toggle(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    category = parts[1]
    item_name = parts[2]

    data = await state.get_data()
    selected = data.get("selected_extras", {"hookah": [], "drinks": [], "food": []})

    if item_name in selected.get(category, []):
        selected[category].remove(item_name)
        await callback.answer(f"❌ Убрано: {item_name}")
    else:
        selected.setdefault(category, []).append(item_name)
        await callback.answer(f"✅ Добавлено: {item_name}")

    await state.update_data(selected_extras=selected)
    category_selected = selected.get(category, [])
    await callback.message.edit_reply_markup(
        reply_markup=extras_items_kb(category, category_selected),
    )


# ─── Confirmation ────────────────────────────────────────

async def _show_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(callback.from_user.id)

    booking_date = data["booking_date"]
    start_time = data["start_time"]
    duration = data["duration"]
    guests = data["guests"]
    is_full_day = data.get("is_full_day", False)
    selected = data.get("selected_extras", {"hookah": [], "drinks": [], "food": []})

    # Calculate end time
    start_h = int(start_time.split(":")[0])
    end_h = (start_h + duration) % 24
    end_time = f"{end_h:02d}:00"

    # Base price
    base_price = _calc_price(booking_date, start_time, duration, is_full_day)

    # Extras price
    extras_price = 0
    extras_list = []
    price_maps = {"hookah": EXTRAS_HOOKAH, "drinks": EXTRAS_DRINKS, "food": EXTRAS_FOOD}
    for cat, items in selected.items():
        for item_name in items:
            price = price_maps.get(cat, {}).get(item_name, 0)
            extras_price += price
            extras_list.append({"category": cat, "item_name": item_name, "price": price})

    # Discounts
    discount = 0
    discount_reasons = []

    # Birthday discount
    if user and user.get("birthday"):
        try:
            from datetime import date as d_type
            bday = datetime.strptime(user["birthday"], "%d.%m.%Y").date()
            today = d_type.today()
            bd_this_year = bday.replace(year=today.year)
            days_diff = abs((bd_this_year - today).days)
            if days_diff <= 3:
                bd_disc = int(base_price * BIRTHDAY_DISCOUNT_PERCENT / 100)
                discount += bd_disc
                discount_reasons.append(f"🎂 День рождения: −{bd_disc}₽")
        except (ValueError, TypeError):
            pass

    # Free hour for loyalty
    if user and user["visits_count"] > 0 and (user["visits_count"] + 1) % FREE_HOUR_EVERY_N_VISITS == 0:
        free_hour_val = PRICE_PER_HOUR
        discount += free_hour_val
        discount_reasons.append(f"🎁 Каждый {FREE_HOUR_EVERY_N_VISITS}-й визит — час бесплатно: −{free_hour_val}₽")

    total = max(0, base_price + extras_price - discount)

    await state.update_data(
        end_time=end_time,
        base_price=base_price,
        extras_price=extras_price,
        extras_list=extras_list,
        discount=discount,
        total_price=total,
    )

    # Build summary
    d = date.fromisoformat(booking_date)
    from config import WEEKDAYS_RU
    wd = WEEKDAYS_RU[d.weekday()]

    duration_label = "СУТКИ 🌟" if is_full_day else f"{duration} ч."

    text = (
        f"📋 Итого бронирования:\n"
        f"{'─' * 28}\n"
        f"📅 {booking_date} ({wd})\n"
        f"⏰ {start_time} — {end_time} ({duration_label})\n"
        f"👥 Гостей: {guests}\n"
    )

    if extras_list:
        text += f"\n🛒 Допы:\n"
        for ext in extras_list:
            cat_emoji = {"hookah": "🔥", "drinks": "🥤", "food": "🍕"}.get(ext["category"], "•")
            text += f"  {cat_emoji} {ext['item_name']} — {ext['price']}₽\n"

    text += f"\n💰 Комната: {base_price:,}₽"
    if is_full_day:
        text += " (тариф «Сутки»)"
    text += "\n"

    if extras_price:
        text += f"🛒 Допы: {extras_price:,}₽\n"
    if discount:
        text += f"\n🎁 Скидки:\n"
        for r in discount_reasons:
            text += f"  {r}\n"

    text += f"\n{'─' * 28}\n"
    text += f"💵 Итого: {total:,}₽\n"

    text += f"\n📦 {DELIVERY_NOTE}"

    await callback.message.edit_text(text, reply_markup=confirmation_kb())
    await state.set_state(BookingStates.confirmation)
    await callback.answer()


@router.callback_query(BookingStates.confirmation, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(callback.from_user.id)

    # Apply promo code & pending discount
    total_price = data["total_price"]
    promo_code = data.get("promo_code")
    promo_disc_pct = data.get("promo_discount_percent", 0)
    promo_disc_amt = data.get("promo_discount_amount", 0)
    pending_disc = user.get("pending_discount", 0) or 0

    if promo_disc_pct:
        total_price = int(total_price * (100 - promo_disc_pct) / 100)
    if promo_disc_amt:
        total_price = max(0, total_price - promo_disc_amt)
    if pending_disc:
        total_price = max(0, total_price - pending_disc)
        await db.update_user(callback.from_user.id, pending_discount=0)
    if promo_code:
        await db.use_promo_code(promo_code)

    booking_id = await db.create_booking(
        user_id=user["id"],
        booking_date=data["booking_date"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        duration_hours=data["duration"],
        guests_count=data["guests"],
        base_price=data["base_price"],
        extras_price=data["extras_price"],
        discount=data["discount"],
        total_price=total_price,
        extras=data.get("extras_list"),
    )

    await state.clear()

    text = (
        f"✅ Бронь #{booking_id} подтверждена!\n\n"
        f"📅 {data['booking_date']} с {data['start_time']} до {data['end_time']}\n"
        f"👥 {data['guests']} чел. | 💵 {data['total_price']:,}₽\n\n"
        f"Мы напомним за 2 часа до визита! 🔔\n"
        f"Ждём тебя в Scorpion Platinum 🔥"
    )

    await callback.message.edit_text(text)
    await callback.message.answer("Что дальше? 👇", reply_markup=main_menu_kb())

    # Notify admins
    from config import ADMIN_IDS
    admin_ids = list(ADMIN_IDS)
    all_users = await db.get_all_users()
    for u in all_users:
        if u["is_admin"] and u["telegram_id"] not in admin_ids:
            admin_ids.append(u["telegram_id"])

    for admin_id in admin_ids:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🆕 Новая бронь #{booking_id}\n"
                f"👤 {user['full_name']} ({user.get('phone', 'нет тел.')})\n"
                f"📅 {data['booking_date']} {data['start_time']}–{data['end_time']}\n"
                f"👥 {data['guests']} чел. | 💵 {data['total_price']:,}₽",
            )
        except Exception:
            pass

    await callback.answer("Забронировано! ✅")


# ─── Cancel ──────────────────────────────────────────────

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Бронирование отменено.")
    await callback.message.answer("Главное меню 👇", reply_markup=main_menu_kb())
    await callback.answer()


# ─── Promo code at confirmation ──────────────────────────

@router.callback_query(BookingStates.confirmation, F.data == "book:promo")
async def booking_promo_start(callback: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await callback.message.edit_text(
        "🎫 Введи промокод:\n\n"
        "Отправь код текстом или нажми пропустить.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="book:skip_promo")],
        ]),
    )
    await state.update_data(awaiting_promo=True)
    await callback.answer()


@router.callback_query(BookingStates.confirmation, F.data == "book:skip_promo")
async def booking_skip_promo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(awaiting_promo=False, promo_code=None)
    await _show_confirmation(callback, state)
    await callback.answer()


@router.message(BookingStates.confirmation)
async def booking_promo_text(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("awaiting_promo"):
        return
    code = message.text.strip().upper()
    promo = await db.validate_promo_code(code)
    if not promo:
        await message.answer("❌ Промокод недействителен. Попробуй другой или пропусти.")
        return
    await state.update_data(
        awaiting_promo=False,
        promo_code=code,
        promo_discount_percent=promo.get("discount_percent", 0),
        promo_discount_amount=promo.get("discount_amount", 0),
    )
    await message.answer(f"✅ Промокод {code} применён!")
    # Show updated confirmation - we need to get a way to show without callback
    # Use message.answer with the confirmation text
    data = await state.get_data()
    total = data.get("total_price", 0)
    pct = promo.get("discount_percent", 0)
    amt = promo.get("discount_amount", 0)
    disc_text = ""
    if pct:
        disc_text = f"Скидка {pct}% будет применена"
    elif amt:
        disc_text = f"Скидка {amt}₽ будет применена"
    await message.answer(
        f"🎫 Промокод применён!\n{disc_text}\n\nНажми «✅ Подтвердить» для завершения.",
        reply_markup=confirmation_kb(),
    )
