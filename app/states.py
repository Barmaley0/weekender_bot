from aiogram.fsm.state import State, StatesGroup


class DateUser(StatesGroup):
    year = State()
    status = State()


class EventLetter(StatesGroup):
    message = State()
    user_id = State()
