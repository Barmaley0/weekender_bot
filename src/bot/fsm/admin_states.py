from aiogram.fsm.state import State, StatesGroup


class MassSendMessage(StatesGroup):
    age_users = State()  # list[str]
    district_users = State()  # list[str]
    target_users = State()  # list[str]
    gender_users = State()  # list[str]
    message_text = State()  # str
    media_upload = State()  # list[dict]
    preview = State()  # bool - состояние предппросмотра
    selected_users = State()  # list[int]
    is_full_mailing = State()  # bool


class AdminChatState(StatesGroup):
    waiting_for_reply = State()  # str
    current_ticket_id = State()  # int
