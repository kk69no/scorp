"""
Post-visit feedback + contact manager.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from states import FeedbackStates
from keyboards import rating_kb, feedback_comment_kb, main_menu_kb
from config import VENUE_PHONE, VENUE_INSTAGRAM

router = Router()


# ─── Leave feedback (triggered by scheduler or manually) ─

async def request_feedback(bot, telegram_id: int, booking_id: int):
    """Called by scheduler after visit ends."""
    try:
        await bot.send_message(
            telegram_id,
            "🙏 Спасибо за визит в Scorpion Platinum!\n\n"
            "Оцени своё впечатление:",
            reply_markup=rating_kb(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("rate:"))
async def rate_visit(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.update_data(feedback_rating=rating)

    stars = "⭐" * rating
    await callback.message.edit_text(
        f"Ты поставил: {stars}\n\n"
        "Хочешь оставить комментарий? Напиши или пропусти:",
        reply_markup=feedback_comment_kb(),
    )
    await state.set_state(FeedbackStates.waiting_comment)
    await callback.answer()


@router.callback_query(FeedbackStates.waiting_comment, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(callback.from_user.id)
    if user:
        await db.create_review(
            user_id=user["id"],
            booking_id=data.get("feedback_booking_id"),
            rating=data["feedback_rating"],
            comment="",
        )
    await state.clear()
    await callback.message.edit_text("Спасибо за оценку! ❤️")
    await callback.answer()


@router.message(FeedbackStates.waiting_comment)
async def feedback_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    if user:
        await db.create_review(
            user_id=user["id"],
            booking_id=data.get("feedback_booking_id"),
            rating=data["feedback_rating"],
            comment=message.text or "",
        )

        # Notify admins about the review
        from config import ADMIN_IDS
        all_users = await db.get_all_users()
        admin_ids = list(ADMIN_IDS)
        for u in all_users:
            if u["is_admin"] and u["telegram_id"] not in admin_ids:
                admin_ids.append(u["telegram_id"])

        stars = "⭐" * data["feedback_rating"]
        for admin_id in admin_ids:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"📝 Новый отзыв от {user['full_name']}\n"
                    f"{stars}\n"
                    f"💬 {message.text}",
                )
            except Exception:
                pass

    await state.clear()
    await message.answer(
        "Спасибо за отзыв! Мы ценим твоё мнение ❤️",
        reply_markup=main_menu_kb(),
    )


# ─── Contact manager ────────────────────────────────────

@router.message(F.text == "💬 Связь с менеджером")
async def contact_manager(message: Message):
    await message.answer(
        "💬 Связаться с нами:\n\n"
        f"📱 Телефон / WhatsApp: {VENUE_PHONE}\n"
        f"📸 Instagram: {VENUE_INSTAGRAM}\n\n"
        "Или напиши свой вопрос прямо сюда — мы передадим менеджеру! 👇"
    )


@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_({
    "📅 Забронировать", "🔄 Как в прошлый раз", "📋 Мои брони",
    "🎁 Бонусы", "ℹ️ О нас", "💬 Связь с менеджером",
    "📱 Отправить номер", "Пропустить ➡️",
}))
async def forward_to_admin(message: Message, state: FSMContext):
    """Forward unrecognized text to admins as support messages."""
    current_state = await state.get_state()
    if current_state:
        return  # Don't intercept if user is in some FSM flow

    user = await db.get_user(message.from_user.id)
    if not user:
        return

    from config import ADMIN_IDS
    all_users = await db.get_all_users()
    admin_ids = list(ADMIN_IDS)
    for u in all_users:
        if u["is_admin"] and u["telegram_id"] not in admin_ids:
            admin_ids.append(u["telegram_id"])

    if not admin_ids:
        return

    for admin_id in admin_ids:
        try:
            username = f"@{message.from_user.username}" if message.from_user.username else ""
            await message.bot.send_message(
                admin_id,
                f"💬 Сообщение от {user['full_name']} {username}\n"
                f"ID: {message.from_user.id}\n\n"
                f"{message.text}",
            )
        except Exception:
            pass

    await message.answer(
        "✅ Сообщение передано менеджеру. Мы ответим в ближайшее время!",
        reply_markup=main_menu_kb(),
    )
