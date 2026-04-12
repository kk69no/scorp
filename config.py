"""
Scorpion Platinum — Telegram Booking Bot
Configuration
"""

BOT_TOKEN = "8298303089:AAH_xkJgfmuh_fK4kvVmV8kS6lyiaD8jyj8"

# ──── Админы (Telegram user IDs) ────
ADMIN_IDS: list[int] = []

# ──── Заведение ────
VENUE_NAME = "Scorpion Platinum"
VENUE_ADDRESS = "г. Нальчик, ул. Шарданова, 7"
VENUE_PHONE = "+7 (928) 709-30-62"
VENUE_INSTAGRAM = "@scorpion.nalchik"
VENUE_DESCRIPTION = (
    "Премиум-лаунж с PlayStation 3, PlayStation 5 Pro, кальяном и доставкой еды.\n"
    "Одна большая приватная комната — идеально для компании."
)

# ──── Режим работы ────
WORK_HOURS_START = 10
WORK_HOURS_END = 3
SLOT_DURATION_MINUTES = 60

# ──── Комната ────
MAX_CAPACITY = 12
MIN_GUESTS = 1
MAX_BOOKING_HOURS = 17
MIN_BOOKING_HOURS = 3

# ──── Цены (руб.) ────
PRICE_PER_HOUR = 1000
PRICE_PER_HOUR_WEEKDAY_DISCOUNT = 1000
PRICE_FULL_DAY = 12000

# ──── Допы ────
EXTRAS_HOOKAH = {
    "Аренда кальяна": 500,
}

EXTRAS_DRINKS = {}
EXTRAS_FOOD = {}

DELIVERY_NOTE = "Еду и напитки можно заказать с доставкой от наших партнёров прямо в комнату!"

# ──── Лояльность ────
LOYALTY_VISIT_POINTS = 100
LOYALTY_REFERRAL_POINTS = 200
LOYALTY_POINTS_PER_RUBLE = 0.05
FREE_HOUR_EVERY_N_VISITS = 5
BIRTHDAY_DISCOUNT_PERCENT = 20

# ──── Напоминания ────
REMINDER_BEFORE_HOURS = 2
FEEDBACK_AFTER_MINUTES = 30

# ──── Предоплата ────
PREPAYMENT_REQUIRED = False
PREPAYMENT_PERCENT = 50

# ──── Дни недели ────
WEEKDAYS_RU = {
    0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт",
    4: "Пт", 5: "Сб", 6: "Вс"
}

# ──── Консоли и игры ────
CONSOLES = ["PlayStation 3", "PlayStation 5 Pro"]

PS5_GAMES = [
    "FIFA 25", "GTA V", "GTA Online", "Mortal Kombat 1", "UFC 5",
    "Call of Duty: MW III", "Call of Duty: BO6", "It Takes Two",
    "Gran Turismo 7", "NBA 2K25", "Tekken 8", "Spider-Man 2",
    "God of War: Ragnarok", "Hogwarts Legacy", "The Last of Us Part I",
    "The Last of Us Part II", "Uncharted: Legacy of Thieves",
    "Overcooked! All You Can Eat", "Astro Bot",
    "и другие популярные игры",
]

# ──── База данных ────
DATABASE_PATH = "scorpion_platinum.db"

# ──── No-show ────
NOSHOW_BLACKLIST_THRESHOLD = 3

# ──── Геолокация ────
VENUE_LATITUDE = 43.4833
VENUE_LONGITUDE = 43.6067
