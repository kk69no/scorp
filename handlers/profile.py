"""
User profile: view, edit, notifications, referrals, points redemption.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from states import ProfileStates
from keyboards import main_menu_kb
from config import (
    FREE_HOUR_EVERY_N_VISITS, LOYALTY_VISIT_POINTS,
    LOYALTY_REFERRAL_POINTS, BIRTHDAY_DISCOUNT_PERCENT,
)

router = Router()

TIERS = [
    (0, "🥉 Бронза"),
    (5, "🥈 Серебро"),
    (10, "🥇 Золото"),
    (20, "💎 Платина"),
]


def get_tier(visits: int) -> tuple:
    tier_name = TIERS[0][1]
    next_info = ""
    for i, (min_v, name) in enumerate(TIERS):
        if visits >= min_v:
            tier_name = name
        else:
            remaining = min_v - visits
            next_info = f"До {name}: ещё {remaining} визит(ов)"
            break
    else:
        next_info = "Максимальный уровень! 🏆"
    return tier_name, next_info


def _bar(current, total, length=10):
    filled = min(int(current / total * length) if total else 0, length)
    return "█" * filled + "░" * (length - filled)


@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    tier, next_tier = get_tier(user["visits_count"])
    next_free = FREE_HOUR_EVERY_N_VISITS - (user["visits_count"] % FREE_HOUR_EVERY_N_VISITS)
    if next_free == FREE_HOUR_EVERY_N_VISITS and user["visits_count"] > 0:
        free_text = "🎁 Бесплатный час доступен!"
    else:
        done = FREE_HOUR_EVERY_N_VISITS - next_free
        free_text = f"До бесплатного часа: [{_bar(done, FREE_HOUR_EVERY_N_VISITS)}] {done}/{FREE_HOUR_EVERY_N_VISITS}"

    referrals = await db.get_referrals(user["id"])
    total_spent = await db.get_user_total_spent(message.from_user.id)

    text = (
        f"👤 Твой профиль\n"
        f"{'─' * 28}\n\n"
        f"📛 {user['full_name']}\n"
        f"📱 {user.get('phone') or '—'}\n"
        f"🎂 {user.get('birthday') or '—'}\n"
        f"🎟 Код: {user['referral_code']}\n\n"
        f"{tier}\n"
        f"{next_tier}\n\n"
        f"🏆 Визитов: {user['visits_count']}\n"
        f"💎 Баллов: {user['loyalty_points']}\n"
        f"💰 Потрачено: {total_spent:,}₽\n"
        f"👥 Друзей: {len(referrals)}\n"
        f"{free_text}\n"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="prof:edit"),
         InlineKeyboardButton(text="🔔 Уведомления", callback_data="prof:notif")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="prof:referrals"),
         InlineKeyboardButton(text="💎 Потратить баллы", callback_data="prof:redeem")],
        [InlineKeyboardButton(text="💰 Калькулятор цены", callback_data="prof:calc")],
    ])
    await message.answer(text, reply_markup=kb)


# ─── Edit profile ────────────────────────────────────────

@router.callback_query(F.data == "prof:edit")
async def profile_edit_menu(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📛 Имя: {user['full_name']}", callback_data="prof_ed:name")],
        [InlineKeyboardButton(text=f"📱 Тел: {user.get('phone') or '—'}", callback_data="prof_ed:phone")],
        [InlineKeyboardButton(text=f"🎂 ДР: {user.get('birthday') or '—'}", callback_data="prof_ed:birthday")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="prof:back")],
    ])
    await callback.message.edit_text("✏️ Что изменить?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "prof:back")
async def profile_back(callback: CallbackQuery):
    await callback.message.edit_text("Нажми «👤 Профиль» в меню для обновления.")
    await callback.answer()


@router.callback_query(F.data.startswith("prof_ed:"))
async def profile_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    prompts = {
        "name": "📛 Введи новое имя:",
        "phone": "📱 Введи номер телефона:",
        "birthday": "🎂 Дата рождения (ДД.ММ.ГГГГ):",
    }
    states_map = {
        "name": ProfileStates.editing_name,
        "phone": ProfileStates.editing_phone,
        "birthday": ProfileStates.editing_birthday,
    }
    await callback.message.edit_text(prompts[field])
    await state.set_state(states_map[field])
    await callback.answer()


@router.message(ProfileStates.editing_name)
async def save_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("2–50 символов:")
        return
    await db.update_user(message.from_user.id, full_name=name)
    await state.clear()
    await message.answer(f"✅ Имя: {name}", reply_markup=main_menu_kb())


@router.message(ProfileStates.editing_phone)
async def save_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if len(cleaned) < 10:
        await message.answer("Введи корректный номер:")
        return
    await db.update_user(message.from_user.id, phone=phone)
    await state.clear()
    await message.answer(f"✅ Телефон: {phone}", reply_markup=main_menu_kb())


@router.message(ProfileStates.editing_birthday)
async def save_birthday(message: Message, state: FSMContext):
    from datetime import datetime
    try:
        bday = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        if bday.year < 1950 or bday.year > 2015:
            raise ValueError
    except ValueError:
        await message.answer("Формат: ДД.ММ.ГГГГ")
        return
    await db.update_user(message.from_user.id, birthday=message.text.strip())
    await state.clear()
    await message.answer(f"✅ ДР: {message.text.strip()}", reply_markup=main_menu_kb())


# ─── Notifications ───────────────────────────────────────

@router.callback_query(F.data == "prof:notif")
async def profile_notifications(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    prefs = {
        "reminders": user.get("notify_reminders", 1),
        "promos": user.get("notify_promos", 1),
        "birthday": user.get("notify_birthday", 1),
    }

    def icon(v):
        return "✅" if v else "❌"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{icon(prefs['reminders'])} Напоминания", callback_data="notif:reminders")],
        [InlineKeyboardButton(text=f"{icon(prefs['promos'])} Акции и рассылки", callback_data="notif:promos")],
        [InlineKeyboardButton(text=f"{icon(prefs['birthday'])} Поздравления", callback_data="notif:birthday")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="prof:back")],
    ])
    await callback.message.edit_text("🔔 Уведомления\nНажми чтобы вкл/выкл:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("notif:"))
async def toggle_notif(callback: CallbackQuery):
    pref = callback.data.split(":")[1]
    col = {"reminders": "notify_reminders", "promos": "notify_promos", "birthday": "notify_birthday"}.get(pref)
    if not col:
        return
    user = await db.get_user(callback.from_user.id)
    new_val = 0 if user.get(col, 1) else 1
    await db.update_user(callback.from_user.id, **{col: new_val})
    status = "вкл" if new_val else "выкл"
    await callback.answer(f"{'✅' if new_val else '❌'} {status}", show_alert=True)
    await profile_notifications(callback)


# ─── Referrals ───────────────────────────────────────────

@router.callback_query(F.data == "prof:referrals")
async def profile_referrals(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    referrals = await db.get_referrals(user["id"])

    text = f"👥 Приглашённые ({len(referrals)})\n{'─' * 28}\n\n"
    if referrals:
        for i, r in enumerate(referrals, 1):
            text += f"  {i}. {r['full_name']} — {r['visits_count']} визитов\n"
        text += f"\n💎 Начислено: {len(referrals) * LOYALTY_REFERRAL_POINTS} баллов"
    else:
        text += (
            f"Пока никого.\n\n"
            f"🎟 Код: {user['referral_code']}\n"
            f"+{LOYALTY_REFERRAL_POINTS} баллов за каждого друга!"
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться",
            switch_inline_query=f"Приходи в Scorpion Platinum! Код: {user['referral_code']}"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="prof:back")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ─── Redeem points ───────────────────────────────────────

@router.callback_query(F.data == "prof:redeem")
async def profile_redeem(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    points = user["loyalty_points"]
    pending = user.get("pending_discount", 0)

    text = f"💎 Баллы: {points}\n"
    if pending:
        text += f"🎁 Активная скидка: {pending}₽\n"
    text += f"{'─' * 28}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    opts = []
    if points >= 500:
        opts.append([InlineKeyboardButton(text="🎁 -500₽ (500 баллов)", callback_data="redeem:500")])
    if points >= 1000:
        opts.append([InlineKeyboardButton(text="🎁 -1000₽ (1000 баллов)", callback_data="redeem:1000")])
    if points >= 2000:
        opts.append([InlineKeyboardButton(text="🎁 Час бесплатно (2000)", callback_data="redeem:2000")])

    if opts:
        text += "Выбери награду:"
    else:
        text += f"Накопи 500 баллов.\nОсталось: {500 - points}"

    opts.append([InlineKeyboardButton(text="◀️ Назад", callback_data="prof:back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=opts))
    await callback.answer()


@router.callback_query(F.data.startswith("redeem:"))
async def redeem_points(callback: CallbackQuery):
    amount = int(callback.data.split(":")[1])
    user = await db.get_user(callback.from_user.id)
    if user["loyalty_points"] < amount:
        await callback.answer("Недостаточно баллов", show_alert=True)
        return

    new_pts = user["loyalty_points"] - amount
    await db.set_loyalty_points(callback.from_user.id, new_pts)

    # Convert to ruble discount
    disc_map = {500: 500, 1000: 1000, 2000: 1000}
    disc = disc_map.get(amount, amount)
    current_pending = user.get("pending_discount", 0) or 0
    await db.update_user(callback.from_user.id, pending_discount=current_pending + disc)

    rewards = {500: "Скидка 500₽", 1000: "Скидка 1000₽", 2000: "Бесплатный час (1000₽)"}
    await callback.message.edit_text(
        f"🎁 Активировано: {rewards.get(amount)}!\n\n"
        f"💎 Баллов осталось: {new_pts}\n"
        f"Скидка применится при следующей брони автоматически."
    )
    await callback.answer("🎁 Активировано!", show_alert=True)


# ─── Price calculator ────────────────────────────────────

@router.callback_query(F.data == "prof:calc")
async def price_calculator(callback: CallbackQuery):
    from config import PRICE_PER_HOUR, PRICE_FULL_DAY, MIN_BOOKING_HOURS, MAX_BOOKING_HOURS
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    rows = []
    row = []
    for h in range(MIN_BOOKING_HOURS, min(MAX_BOOKING_HOURS + 1, 13)):
        price = PRICE_PER_HOUR * h
        row.append(InlineKeyboardButton(text=f"{h}ч={price//1000}k", callback_data="ignore"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=f"🌟 Сутки = {PRICE_FULL_DAY//1000}k₽", callback_data="ignore")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="prof:back")])

    await callback.message.edit_text(
        f"💰 Калькулятор цены\n{'─' * 28}\n\n"
        f"Базовая цена: {PRICE_PER_HOUR:,}₽/час\n"
        f"Сутки: {PRICE_FULL_DAY:,}₽\n\n"
        f"Не включает кальян и допы.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()
