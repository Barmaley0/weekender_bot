from aiogram.fsm.state import StatesGroup, State


class DateUser(StatesGroup):
    year = State()
    status = State()
