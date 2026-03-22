"""
Scorpion Platinum — Telegram Booking Bot
Entry point
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database import init_db
from handlers import get_all_routers
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Scorpion Platinum Bot...")

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Create bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None),
    )

    # Create dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Register all routers
    for r in get_all_routers():
        dp.include_router(r)
    logger.info("Routers registered")

    # Start scheduler
    setup_scheduler(bot)
    logger.info("Scheduler started")

    # Start polling
    logger.info("Bot is running! Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
