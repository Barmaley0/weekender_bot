from aiogram.fsm.state import State, StatesGroup


class UserData(StatesGroup):
    year = State()
    status = State()
    district = State()
    interests = State()
