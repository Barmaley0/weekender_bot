from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.database.requests import (
    get_all_districts,
    get_all_gender,
    get_all_interests,
    get_all_marital_status,
)


async def get_main_kb(user_data_exists: bool) -> ReplyKeyboardMarkup:
    main_menu = ReplyKeyboardBuilder()

    if user_data_exists:
        main_menu.add(
            KeyboardButton(text='🔄️Повторить подборку'),
            KeyboardButton(text='🔀Изменить подборку'),
        )
    else:
        main_menu.add(
            KeyboardButton(text='🎉 Начнём 🎉'),
        )

    main_menu.add(KeyboardButton(text='Меню 🗄️'))
    main_menu.adjust(2 if not user_data_exists else 2, 1)

    return main_menu.as_markup(
        resize_keyboard=True,
        input_field_placeholder='Выберите действие',
    )


async def get_menu_kb() -> InlineKeyboardMarkup:
    menu_inline = InlineKeyboardBuilder()
    menu_inline.add(
        InlineKeyboardButton(text='Проверить баллы', callback_data='check_'),
        InlineKeyboardButton(text='Персональный помощник', url='https://t.me/weekender_main'),
        InlineKeyboardButton(text='Чат поиска компании', url='https://t.me/weekender_chat'),
    )
    menu_inline.adjust(1)
    return menu_inline.as_markup()


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

    keyboard.adjust(1)
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

    keyboard.adjust(1)
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
