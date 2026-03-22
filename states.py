"""FSM States for all conversation flows."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_birthday = State()


class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    choosing_duration = State()
    choosing_guests = State()
    choosing_extras_menu = State()
    choosing_hookah = State()
    choosing_drinks = State()
    choosing_food = State()
    confirmation = State()


class RescheduleStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()


class FeedbackStates(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()


class AdminStates(StatesGroup):
    sending_promo = State()
    blocking_date = State()
    blocking_reason = State()
    adding_to_blacklist = State()
