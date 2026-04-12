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
    # Manual booking
    manual_choosing_user = State()
    manual_choosing_date = State()
    manual_choosing_time = State()
    manual_choosing_duration = State()
    manual_choosing_guests = State()
    manual_note = State()
    # Edit booking
    edit_choosing_field = State()
    edit_new_value = State()
    # User management
    search_user = State()
    adjust_points = State()
    message_user = State()
    # Admin roles
    adding_admin = State()
    # Settings
    setting_price = State()
    setting_hours_start = State()
    setting_hours_end = State()
    setting_capacity = State()
    editing_setting = State()
    # Unblock date
    unblock_choosing_date = State()
    # Export
    export_choosing_period = State()
    # Promo codes
    creating_promo_code = State()
    promo_discount = State()
    promo_max_uses = State()
    # User notes
    adding_user_note = State()
    # Console management
    console_note = State()
    # Targeted promo
    targeted_promo_text = State()
