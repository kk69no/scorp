"""
Scorpion Platinum — Telegram Booking Bot
Configuration
"""

BOT_TOKEN = "8298303089:AAH_xkJgfmuh_fK4kvVmV8kS6lyiaD8jyj8"

# ──── Админы (Telegram user IDs) ────
# Первый пользователь /admin автоматически станет админом,
# либо укажи ID вручную:
ADMIN_IDS: list[int] = []

# ──── Заведение ────
VENUE_NAME = "Scorpion Platinum"
VENUE_ADDRESS = "г. Нальчик, ул. Чернышевского, 230/178"
VENUE_PHONE = "+7 (938) 701-97-55"
VENUE_INSTAGRAM = "@scorpion.nalchik"
VENUE_DESCRIPTION = (
    "Премиум-лаунж с PlayStation 5, кальяном и едой.\n"
    "Одна большая приватная комната — идеально для компании."
)

# ──── Режим работы ────
WORK_HOURS_START = 10  # с 10:00
WORK_HOURS_END = 3     # до 03:00 (следующего дня)
SLOT_DURATION_MINUTES = 60  # один слот = 1 час

# ──── Комната ────
MAX_CAPACITY = 15          # макс. гостей одновременно
MIN_GUESTS = 1
MAX_BOOKING_HOURS = 8      # макс. длительность брони
MIN_BOOKING_HOURS = 1

# ──── Цены (руб.) ────
PRICE_PER_HOUR = 1500      # аренда комнаты за час
PRICE_PER_HOUR_WEEKDAY_DISCOUNT = 1200  # скидка пн-чт до 17:00

# ──── Допы ────
EXTRAS_HOOKAH = {
    "Классика":      800,
    "Фрукты":        1000,
    "Премиум микс":  1200,
    "Двойной":       1500,
}

EXTRAS_DRINKS = {
    "Чай фирменный":       200,
    "Лимонад фирменный":   250,
    "Кофе":                 200,
    "Вода / Сок":           150,
}

EXTRAS_FOOD = {
    "Сет закусок":       500,
    "Пицца":             600,
    "Бургер":            450,
    "Наггетсы":          350,
    "Фри":               250,
}

# ──── Лояльность ────
LOYALTY_VISIT_POINTS = 100        # баллов за визит
LOYALTY_REFERRAL_POINTS = 200     # баллов за приглашённого друга
LOYALTY_POINTS_PER_RUBLE = 0.05   # 1 руб = 0.05 балла с чека
FREE_HOUR_EVERY_N_VISITS = 5      # каждое N-е посещение — бесплатный час
BIRTHDAY_DISCOUNT_PERCENT = 20    # скидка на ДР

# ──── Напоминания ────
REMINDER_BEFORE_HOURS = 2      # напомнить за N часов до визита
FEEDBACK_AFTER_MINUTES = 30    # запросить отзыв через N минут после окончания

# ──── Предоплата ────
PREPAYMENT_REQUIRED = False    # требовать предоплату?
PREPAYMENT_PERCENT = 50        # процент предоплаты

# ──── Дни недели ────
WEEKDAYS_RU = {
    0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт",
    4: "Пт", 5: "Сб", 6: "Вс"
}

# ──── Игры PS5 ────
PS5_GAMES = [
    "FIFA 25", "GTA V", "Mortal Kombat 1", "UFC 5",
    "Call of Duty: MW III", "It Takes Two", "Gran Turismo 7",
    "NBA 2K25", "Tekken 8", "Spider-Man 2",
    "God of War: Ragnarök", "Hogwarts Legacy",
    "Overcooked! All You Can Eat", "Crash Team Rumble",
]

# ──── База данных ────
DATABASE_PATH = "scorpion_platinum.db"

# ──── No-show ────
NOSHOW_BLACKLIST_THRESHOLD = 3  # после N неявок — в чёрный список
