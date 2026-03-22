"""
Scheduled tasks:
- Reminders (2h before visit)
- Feedback requests (30min after visit ends)
- Birthday promos (7 days before)
- Available slot notifications (weekday evenings)
"""

import logging
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from config import (
    REMINDER_BEFORE_HOURS, FEEDBACK_AFTER_MINUTES,
    BIRTHDAY_DISCOUNT_PERCENT, VENUE_NAME,
)

logger = logging.getLogger(__name__)

_bot = None
_scheduler: AsyncIOScheduler | None = None


def setup_scheduler(bot) -> AsyncIOScheduler:
    global _bot, _scheduler
    _bot = bot
    _scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # Every 5 minutes: check for reminders
    _scheduler.add_job(send_reminders, "interval", minutes=5, id="reminders")

    # Every 10 minutes: check for feedback requests
    _scheduler.add_job(send_feedback_requests, "interval", minutes=10, id="feedback")

    # Daily at 10:00: birthday promos
    _scheduler.add_job(send_birthday_promos, "cron", hour=10, minute=0, id="birthdays")

    # Weekday evenings at 18:00: promo for empty slots
    _scheduler.add_job(
        send_availability_promo, "cron",
        day_of_week="mon-thu", hour=18, minute=0, id="avail_promo"
    )

    _scheduler.start()
    logger.info("Scheduler started with 4 jobs")
    return _scheduler


# ─── Reminders ───────────────────────────────────────────

async def send_reminders():
    if not _bot:
        return
    try:
        bookings = await db.get_upcoming_reminders()
        for b in bookings:
            try:
                await _bot.send_message(
                    b["telegram_id"],
                    f"🔔 Напоминание!\n\n"
                    f"Твоя бронь в {VENUE_NAME}:\n"
                    f"📅 Сегодня в {b['start_time']}\n"
                    f"👥 {b['guests_count']} чел.\n\n"
                    f"Ждём тебя! 🔥",
                )
                await db.mark_reminded(b["id"])
                logger.info(f"Reminder sent for booking #{b['id']}")
            except Exception as e:
                logger.error(f"Failed to send reminder for #{b['id']}: {e}")
    except Exception as e:
        logger.error(f"Reminder job error: {e}")


# ─── Feedback requests ───────────────────────────────────

async def send_feedback_requests():
    if not _bot:
        return
    try:
        bookings = await db.get_completed_needing_feedback()
        for b in bookings:
            try:
                from handlers.feedback import request_feedback
                await request_feedback(_bot, b["telegram_id"], b["id"])
                logger.info(f"Feedback request sent for booking #{b['id']}")
            except Exception as e:
                logger.error(f"Failed to send feedback for #{b['id']}: {e}")
    except Exception as e:
        logger.error(f"Feedback job error: {e}")


# ─── Birthday promos ─────────────────────────────────────

async def send_birthday_promos():
    if not _bot:
        return
    try:
        users = await db.get_users_with_birthday_soon(days_ahead=7)
        for user in users:
            days = user["days_until_birthday"]
            try:
                if days == 0:
                    text = (
                        f"🎂 С Днём Рождения, {user['full_name']}! 🎉\n\n"
                        f"Scorpion Platinum дарит тебе скидку {BIRTHDAY_DISCOUNT_PERCENT}%!\n"
                        f"Приходи отметить — скидка действует 3 дня! 🔥\n\n"
                        f"Нажми «📅 Забронировать» и скидка применится автоматически."
                    )
                elif days <= 3:
                    text = (
                        f"🎁 {user['full_name']}, твой день рождения уже скоро!\n\n"
                        f"Забронируй {VENUE_NAME} на свой ДР "
                        f"и получи скидку {BIRTHDAY_DISCOUNT_PERCENT}%! 🎂\n\n"
                        f"Скидка действует ±3 дня от дня рождения."
                    )
                else:
                    text = (
                        f"🎂 {user['full_name']}, через {days} дней твой день рождения!\n\n"
                        f"Забронируй Scorpion Platinum заранее "
                        f"и получи скидку {BIRTHDAY_DISCOUNT_PERCENT}%! 🎉\n\n"
                        f"Нажми «📅 Забронировать» 👇"
                    )

                await _bot.send_message(user["telegram_id"], text)
                logger.info(f"Birthday promo sent to {user['full_name']}")
            except Exception as e:
                logger.error(f"Failed birthday promo for {user['full_name']}: {e}")
    except Exception as e:
        logger.error(f"Birthday promo job error: {e}")


# ─── Available slots promo ───────────────────────────────

async def send_availability_promo():
    """On weekday evenings, notify users if tonight has open slots."""
    if not _bot:
        return
    try:
        today_str = date.today().isoformat()
        if await db.is_date_blocked(today_str):
            return

        bookings = await db.get_bookings_for_date(today_str)
        # Check if evening slots (18-23) are free
        evening_booked = [
            b for b in bookings
            if int(b["start_time"].split(":")[0]) >= 18
        ]

        if len(evening_booked) < 2:  # Mostly free evening
            users = await db.get_all_users()
            # Only notify users who haven't booked today
            booked_user_ids = {b["user_id"] for b in bookings}

            sent = 0
            for user in users:
                if user["id"] in booked_user_ids:
                    continue
                if sent >= 50:  # Limit per batch
                    break
                try:
                    await _bot.send_message(
                        user["telegram_id"],
                        f"🌙 Сегодня вечером Scorpion Platinum свободен!\n\n"
                        f"Успей забронировать — будний день, "
                        f"цена всего от 1200₽/час 🔥\n\n"
                        f"Нажми «📅 Забронировать»",
                    )
                    sent += 1
                except Exception:
                    pass

            logger.info(f"Availability promo sent to {sent} users")
    except Exception as e:
        logger.error(f"Availability promo error: {e}")
