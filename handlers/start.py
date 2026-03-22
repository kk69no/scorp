"""
/start, registration flow, main menu.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

import database as db
from states import RegistrationStates
from keyboards import main_menu_kb, skip_kb, phone_kb
from config import VENUE_NAME

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    # Check for referral deep link: /start ref_XXXXXXXX
    referral_code = None
    if message.text and len(message.text.split()) > 1:
        arg = message.text.split()[1]
        if arg.startswith("ref_"):
            referral_code = arg[4:]
            await state.update_data(referral_code=referral_code)

    user = await db.get_user(message.from_user.id)
    if user:
        if user["is_blacklisted"]:
            await message.answer(
                "⛔ Ваш аккаунт заблокирован. Обратитесь к администратору."
            )
            return
        await message.answer(
            f"С возвращением, {user['full_name']}! 👋\n\n"
            f"Добро пожаловать в {VENUE_NAME}.",
            reply_markup=main_menu_kb(),
        )
        return

    # New user — registration
    await message.answer(
        f"Добро пожаловать в {VENUE_NAME}! 🎮🔥\n\n"
        "Давай познакомимся. Как тебя зовут?",
    )
    await state.set_state(RegistrationStates.waiting_name)


@router.message(RegistrationStates.waiting_name)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Введи настоящее имя (2–50 символов):")
        return

    await state.update_data(full_name=name)
    await message.answer(
        f"Приятно познакомиться, {name}! 🤝\n\n"
        "Отправь свой номер телефона — чтобы мы могли связаться при необходимости.",
        reply_markup=phone_kb(),
    )
    await state.set_state(RegistrationStates.waiting_phone)


@router.message(RegistrationStates.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await _ask_birthday(message, state)


@router.message(RegistrationStates.waiting_phone)
async def reg_phone_text(message: Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    if text in ("Пропустить ➡️", "пропустить"):
        await state.update_data(phone=None)
        await _ask_birthday(message, state)
        return

    # Basic phone validation
    cleaned = text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not (cleaned.startswith("+") or cleaned.startswith("7") or cleaned.startswith("8")):
        await message.answer("Введи номер телефона или нажми «Пропустить»:")
        return
    await state.update_data(phone=text)
    await _ask_birthday(message, state)


async def _ask_birthday(message: Message, state: FSMContext):
    await message.answer(
        "Когда у тебя день рождения? 🎂\n"
        "Формат: ДД.ММ.ГГГГ (например 15.03.2000)\n\n"
        "Мы подарим скидку! Можно пропустить.",
        reply_markup=skip_kb(),
    )
    await state.set_state(RegistrationStates.waiting_birthday)


@router.callback_query(RegistrationStates.waiting_birthday, F.data == "skip")
async def reg_birthday_skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(birthday=None)
    await _finish_registration(callback.message, state, callback.from_user)


@router.message(RegistrationStates.waiting_birthday)
async def reg_birthday(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.lower() in ("пропустить", "skip"):
        await state.update_data(birthday=None)
        await _finish_registration(message, state, message.from_user)
        return

    from datetime import datetime
    try:
        bday = datetime.strptime(text, "%d.%m.%Y")
        if bday.year < 1950 or bday.year > 2015:
            raise ValueError
        await state.update_data(birthday=text)
    except ValueError:
        await message.answer("Неверный формат. Введи дату как ДД.ММ.ГГГГ:")
        return

    await _finish_registration(message, state, message.from_user)


async def _finish_registration(message: Message, state: FSMContext, tg_user):
    data = await state.get_data()
    user = await db.create_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        full_name=data["full_name"],
        phone=data.get("phone"),
        birthday=data.get("birthday"),
        referred_by_code=data.get("referral_code"),
    )
    await state.clear()

    welcome = (
        f"Регистрация завершена! ✅\n\n"
        f"👤 {user['full_name']}\n"
    )
    if user.get("phone"):
        welcome += f"📱 {user['phone']}\n"
    if user.get("birthday"):
        welcome += f"🎂 {user['birthday']}\n"

    welcome += (
        f"\n🎟 Твой реферальный код: {user['referral_code']}\n"
        f"Приглашай друзей и получай бонусы!\n\n"
        f"Выбери действие из меню 👇"
    )
    await message.answer(welcome, reply_markup=main_menu_kb())
