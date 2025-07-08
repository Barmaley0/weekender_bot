from aiogram.fsm.state import State, StatesGroup


class UserData(StatesGroup):
    year = State()  # int
    gender = State()  # str
    status = State()  # str
    target = State()  # str
    district = State()  # str
    profession = State()  # str
    about = State()  # str
    interests = State()  # list[str]
    shown_events = State()  # str
    edit_mode = State()  # str


class PeopleSearch(StatesGroup):
    age_range = State()  # list[str]
    shown_people_ids = State()  # list[int]
    waiting_for_username = State()  # str
