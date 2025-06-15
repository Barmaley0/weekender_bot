from aiogram.fsm.state import State, StatesGroup


class UserData(StatesGroup):
    year = State()  # int
    gender = State()  # str
    status = State()  # str
    district = State()  # str
    interests = State()  # list[str]
    shown_events = State()  # str
