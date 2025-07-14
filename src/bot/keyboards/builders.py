import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from src.bot.db.repositories.options_repository import (
    get_all_age_range,
    get_all_districts,
    get_all_gender,
    get_all_interests,
    get_all_marital_status,
    get_all_target,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_main_kb(user_data_exists: bool) -> ReplyKeyboardMarkup:
    main_menu = ReplyKeyboardBuilder()

    if user_data_exists:
        main_menu.add(
            KeyboardButton(text='Резиденты'),
            KeyboardButton(text='Мероприятия'),
            KeyboardButton(text='Баллы'),
            KeyboardButton(text='Чат'),
        )
    else:
        main_menu.add(
            KeyboardButton(text='🎉 Начнём 🎉'),
        )

    main_menu.adjust(1 if not user_data_exists else 2)

    return main_menu.as_markup(
        resize_keyboard=True,
        input_field_placeholder='Выберите действие',
    )


async def get_residents_menu_kb() -> InlineKeyboardMarkup:
    menu_inline = InlineKeyboardBuilder()
    menu_inline.add(
        InlineKeyboardButton(text='Посмотреть свой профиль', callback_data='profile'),
        InlineKeyboardButton(text='Изменить профиль', callback_data='edit_profile'),
        InlineKeyboardButton(text='Посмотреть пользователей чата', callback_data='find_user'),
        InlineKeyboardButton(text='Найти людей', callback_data='find_people'),
    )

    menu_inline.adjust(1)
    return menu_inline.as_markup()


async def get_chats_kb() -> InlineKeyboardMarkup:
    menu_inline = InlineKeyboardBuilder()
    menu_inline.add(
        InlineKeyboardButton(text='Чат', url='https://t.me/+hAwst9wJ-4kzNTdi'),
    )

    menu_inline.adjust(1)
    return menu_inline.as_markup()


async def show_more_people_kb() -> InlineKeyboardMarkup:
    menu_inline = InlineKeyboardBuilder()
    menu_inline.add(
        InlineKeyboardButton(text='Показать ещё', callback_data='show_more_people'),
    )

    menu_inline.adjust(1)
    return menu_inline.as_markup()


async def send_message_user_and_like_kb(
    tg_id: int,
    username: str | None,
    state: FSMContext,
    target: str,
) -> InlineKeyboardMarkup:
    data = await state.get_data()

    liked_ids = data.get('liked_profile_ids', [])
    friend_ids = data.get('friend_profile_ids', [])
    reciprocated_ids = data.get('reciprocated_profile_ids', [])
    logger.info(f'*** liked_ids: {liked_ids}, friend_ids: {friend_ids}, reciprocated_ids: {reciprocated_ids}')

    is_liked = tg_id in liked_ids
    is_friend = tg_id in friend_ids
    is_reciprocated = tg_id in reciprocated_ids
    logger.info(f'*** is_liked: {is_liked}, is_friend: {is_friend}, is_reciprocated: {is_reciprocated}')

    menu_inline = InlineKeyboardBuilder()

    if target == 'Отношения':
        menu_inline.add(
            InlineKeyboardButton(
                text='💌 Написать' if is_reciprocated else '✉️ Написать',
                url=f'https://t.me/{username}' if username else f'https://t.me/{tg_id}',
            )
        )
    elif target == 'Дружба':
        menu_inline.add(
            InlineKeyboardButton(
                text='📧 Написать' if is_reciprocated else '✉️ Написать',
                url=f'https://t.me/{username}' if username else f'https://t.me/{tg_id}',
            )
        )

    if target == 'Отношения':
        if not is_reciprocated:
            menu_inline.add(
                InlineKeyboardButton(
                    text='♥️' if is_liked else '🩶',
                    callback_data=f'like_toggle_{tg_id}',
                )
            )
    elif target == 'Дружба':
        if not is_reciprocated:
            menu_inline.add(
                InlineKeyboardButton(
                    text='♥️' if is_friend else '🩶',
                    callback_data=f'friend_toggle_{tg_id}',
                )
            )

    menu_inline.adjust(2)
    return menu_inline.as_markup()


async def get_events_kb() -> InlineKeyboardMarkup:
    menu_inline = InlineKeyboardBuilder()
    menu_inline.add(
        InlineKeyboardButton(text='Подборка', callback_data='events'),
        InlineKeyboardButton(text='Изменить профиль', callback_data='edit_events'),
        InlineKeyboardButton(text='Персональный помощник', url='https://t.me/weekender_main'),
    )

    menu_inline.adjust(1)
    return menu_inline.as_markup()


async def age_range_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    current_age_range = data.get('age_ranges', [])
    age_range = await get_all_age_range()

    keyboard = InlineKeyboardBuilder()
    for age in sorted(age_range, key=lambda x: x.id):
        selected = age.name in current_age_range
        emoji = '✅' if selected else ''
        button = InlineKeyboardButton(
            text=f'{emoji} {age.name}',
            callback_data=f'age_range_{age.name}',
        )
        keyboard.add(button)

    keyboard.row(
        InlineKeyboardButton(
            text='🎯 Готово',
            callback_data='age_done',
        )
    )

    keyboard.adjust(2)
    return keyboard.as_markup()


async def gender_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    current_gender = data.get('gender')
    all_gender = await get_all_gender()

    keyboard = InlineKeyboardBuilder()
    for gender in sorted(all_gender, key=lambda x: x.name):
        selected = gender.name == current_gender
        emoji = '✅' if selected else ''
        button = InlineKeyboardButton(
            text=f'{emoji} {gender.name}',
            callback_data=f'gender_{gender.name}',
        )
        keyboard.add(button)

    keyboard.adjust(2)
    return keyboard.as_markup()


async def marital_status_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    current_status = data.get('status')
    all_marital_status = await get_all_marital_status()

    keyboard = InlineKeyboardBuilder()
    for status in sorted(all_marital_status, key=lambda x: x.id):
        selected = status.name == current_status
        emoji = '✅' if selected else ''

        display_status_name = status.name
        if status.name == 'Свободен':
            display_status_name = 'Свободен(а)'
        button = InlineKeyboardButton(
            text=f'{emoji} {display_status_name}',
            callback_data=f'status_{status.name}',
        )
        keyboard.add(button)

    keyboard.adjust(2)
    return keyboard.as_markup()


async def target_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    current_target = data.get('target')
    all_all_target = await get_all_target()

    keyboard = InlineKeyboardBuilder()
    for terget in sorted(all_all_target, key=lambda x: x.id):
        selected = terget.name == current_target
        emoji = '✅' if selected else ''
        button = InlineKeyboardButton(
            text=f'{emoji} {terget.name}',
            callback_data=f'target_{terget.name}',
        )
        keyboard.add(button)

    keyboard.adjust(2)
    return keyboard.as_markup()


async def district_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    current_district = data.get('district')
    districts = await get_all_districts()

    keyboard = InlineKeyboardBuilder()
    for district in sorted(districts, key=lambda x: x.name):
        selected = district.name == current_district
        emoji = '✅' if selected else ''
        button = InlineKeyboardButton(
            text=f'{emoji} {district.name}',
            callback_data=f'district_{district.name}',
        )
        keyboard.add(button)

    keyboard.adjust(2)
    return keyboard.as_markup()


async def interests_kb(state: FSMContext) -> InlineKeyboardMarkup:
    data = await state.get_data()
    current_interests = data.get('interests', [])
    interests = await get_all_interests()

    keyboard = InlineKeyboardBuilder()
    for interest in sorted(interests, key=lambda x: x.name):
        selected = interest.name in current_interests
        emoji = '✅' if selected else ''
        button = InlineKeyboardButton(
            text=f'{emoji} {interest.name}',
            callback_data=f'interests_{interest.name}',
        )
        keyboard.add(button)

    keyboard.row(
        InlineKeyboardButton(
            text='🎯 Готово',
            callback_data='interests_done',
        )
    )
    keyboard.adjust(2)
    return keyboard.as_markup()
