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
    total_likes = State()  # int


class PeopleSearch(StatesGroup):
    age_range = State()  # list[str]
    shown_people_ids = State()  # list[int]
    waiting_for_username = State()  # str


class LikeFriendProfile(StatesGroup):
    liked_profiles_ids = State()  # ID профилей, которым поставлен лайк list[int]
    friend_profiles_ids = State()  # ID профилей, которым поставлен лайк друзья list[int]
    reciprocated_profile_ids = State()  # ID взаимных лайков list[int]
    is_reciprocated = State()  # Флфг наличия взаимных лайков bool
