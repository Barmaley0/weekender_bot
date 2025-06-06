from aiogram.fsm.state import State, StatesGroup


class UserData(StatesGroup):
    year = State()
    gender = State()
    status = State()
    district = State()
    interests = State()
    shown_events = State()
