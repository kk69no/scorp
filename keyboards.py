"""
All inline & reply keyboards.
"""

from datetime import date, timedelta, datetime
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

from config import (
    WORK_HOURS_START, WORK_HOURS_END, MAX_BOOKING_HOURS, MIN_BOOKING_HOURS,
    EXTRAS_HOOKAH, EXTRAS_DRINKS, EXTRAS_FOOD, WEEKDAYS_RU,
)


# ─── Main menu ───────────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Забронировать"), KeyboardButton(text="🔄 Как в прошлый раз")],
            [KeyboardButton(text="📋 Мои брони"), KeyboardButton(text="🎁 Бонусы")],
            [KeyboardButton(text="ℹ️ О нас"), KeyboardButton(text="💬 Связь с менеджером")],
        ],
        resize_keyboard=True,
    )


# ─── Registration ────────────────────────────────────────

def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить ➡️", callback_data="skip")]
    ])


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
            [KeyboardButton(text="Пропустить ➡️")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── Calendar ────────────────────────────────────────────

def calendar_kb(month_offset: int = 0) -> InlineKeyboardMarkup:
    today = date.today()
    first_day = today.replace(day=1)
    if month_offset > 0:
        for _ in range(month_offset):
            first_day = (first_day + timedelta(days=32)).replace(day=1)

    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }

    rows = []

    # Month/year header with nav arrows
    rows.append([
        InlineKeyboardButton(text="◀️", callback_data=f"cal_prev:{month_offset}"),
        InlineKeyboardButton(
            text=f"{month_names[first_day.month]} {first_day.year}",
            callback_data="ignore"
        ),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_next:{month_offset}"),
    ])

    # Weekday headers
    rows.append([
        InlineKeyboardButton(text=d, callback_data="ignore")
        for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ])

    # Days grid
    import calendar
    cal = calendar.monthcalendar(first_day.year, first_day.month)
    for week in cal:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                d = date(first_day.year, first_day.month, day_num)
                if d < today:
                    row.append(InlineKeyboardButton(text="·", callback_data="ignore"))
                elif d == today:
                    row.append(InlineKeyboardButton(
                        text=f"[{day_num}]",
                        callback_data=f"date:{d.isoformat()}"
                    ))
                else:
                    row.append(InlineKeyboardButton(
                        text=str(day_num),
                        callback_data=f"date:{d.isoformat()}"
                    ))
        rows.append(row)

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Time slots ──────────────────────────────────────────

def time_slots_kb(available_slots: list[str]) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for slot in available_slots:
        row.append(InlineKeyboardButton(text=slot, callback_data=f"time:{slot}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_date"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Duration ────────────────────────────────────────────

def duration_kb(max_hours: int | None = None) -> InlineKeyboardMarkup:
    limit = min(max_hours or MAX_BOOKING_HOURS, MAX_BOOKING_HOURS)
    rows = []
    row = []
    for h in range(MIN_BOOKING_HOURS, limit + 1):
        label = f"{h} ч"
        row.append(InlineKeyboardButton(text=label, callback_data=f"dur:{h}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_time"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Guests ──────────────────────────────────────────────

def guests_kb(max_guests: int) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for g in range(1, max_guests + 1):
        row.append(InlineKeyboardButton(text=str(g), callback_data=f"guests:{g}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_duration"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Extras menu ─────────────────────────────────────────

def extras_menu_kb(selected: dict | None = None) -> InlineKeyboardMarkup:
    selected = selected or {}
    hookah_count = len(selected.get("hookah", []))
    drinks_count = len(selected.get("drinks", []))
    food_count = len(selected.get("food", []))

    h_label = f"🔥 Кальян ({hookah_count})" if hookah_count else "🔥 Кальян"
    d_label = f"🥤 Напитки ({drinks_count})" if drinks_count else "🥤 Напитки"
    f_label = f"🍕 Еда ({food_count})" if food_count else "🍕 Еда"

    rows = [
        [InlineKeyboardButton(text=h_label, callback_data="extras:hookah")],
        [InlineKeyboardButton(text=d_label, callback_data="extras:drinks")],
        [InlineKeyboardButton(text=f_label, callback_data="extras:food")],
        [InlineKeyboardButton(text="✅ Готово — к итогу", callback_data="extras:done")],
        [InlineKeyboardButton(text="⏭ Без допов", callback_data="extras:skip")],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_guests"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def extras_items_kb(category: str, selected_items: list[str] | None = None) -> InlineKeyboardMarkup:
    selected_items = selected_items or []
    items_map = {
        "hookah": EXTRAS_HOOKAH,
        "drinks": EXTRAS_DRINKS,
        "food": EXTRAS_FOOD,
    }
    items = items_map.get(category, {})

    rows = []
    for name, price in items.items():
        check = "✅ " if name in selected_items else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{check}{name} — {price}₽",
                callback_data=f"ext_item:{category}:{name}"
            )
        ])

    rows.append([InlineKeyboardButton(text="◀️ Назад к допам", callback_data="back_to_extras")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Confirmation ────────────────────────────────────────

def confirmation_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking"),
        ],
    ])


# ─── My bookings ────────────────────────────────────────

def my_bookings_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for b in bookings[:10]:
        d = b["booking_date"]
        t = b["start_time"]
        rows.append([
            InlineKeyboardButton(
                text=f"📅 {d} в {t} ({b['duration_hours']}ч) — {b['total_price']}₽",
                callback_data=f"view_booking:{b['id']}"
            )
        ])
    if not rows:
        rows.append([InlineKeyboardButton(text="Нет активных броней", callback_data="ignore")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def booking_actions_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_bk:{booking_id}"),
            InlineKeyboardButton(text="📅 Перенести", callback_data=f"reschedule:{booking_id}"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_my_bookings")],
    ])


# ─── Loyalty ─────────────────────────────────────────────

def loyalty_kb(referral_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться ссылкой",
            switch_inline_query=f"Приходи в Scorpion Platinum! Мой код: {referral_code}"
        )],
        [InlineKeyboardButton(text="📊 История баллов", callback_data="loyalty_history")],
    ])


# ─── Feedback ────────────────────────────────────────────

def rating_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'⭐' * i}", callback_data=f"rate:{i}") for i in range(1, 6)]
    ])


def feedback_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить ➡️", callback_data="skip_comment")]
    ])


# ─── Admin ───────────────────────────────────────────────

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Брони сегодня", callback_data="adm:today")],
        [InlineKeyboardButton(text="📅 Брони на неделю", callback_data="adm:week")],
        [InlineKeyboardButton(text="🚫 Заблокировать дату", callback_data="adm:block_date")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")],
        [InlineKeyboardButton(text="⛔ Чёрный список", callback_data="adm:blacklist")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:promo")],
        [InlineKeyboardButton(text="✅ Отметить завершение", callback_data="adm:complete")],
        [InlineKeyboardButton(text="🚷 Отметить неявку", callback_data="adm:noshow")],
    ])


def admin_bookings_list_kb(bookings: list[dict], action: str = "view") -> InlineKeyboardMarkup:
    rows = []
    for b in bookings[:15]:
        user_name = b.get("full_name", "?")
        rows.append([
            InlineKeyboardButton(
                text=f"{b['start_time']}–{b['end_time']} | {user_name} ({b['guests_count']} чел.)",
                callback_data=f"adm_{action}:{b['id']}"
            )
        ])
    if not rows:
        rows.append([InlineKeyboardButton(text="Нет броней", callback_data="ignore")])
    rows.append([InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_confirm_kb(action: str, booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"adm_confirm_{action}:{booking_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="adm:menu"),
        ]
    ])


# ─── Showcase ────────────────────────────────────────────

def showcase_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Прайс", callback_data="show:price")],
        [InlineKeyboardButton(text="🎮 Игры PS5", callback_data="show:games")],
        [InlineKeyboardButton(text="🔥 Меню кальянов", callback_data="show:hookah")],
        [InlineKeyboardButton(text="🍕 Еда и напитки", callback_data="show:food")],
        [InlineKeyboardButton(text="📍 Как добраться", callback_data="show:location")],
    ])
