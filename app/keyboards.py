from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.database.requests import get_categories_years, get_marital_status


async def get_main_keyboard() -> ReplyKeyboardMarkup:
    main_menu = ReplyKeyboardBuilder()
    main_menu.row(KeyboardButton(text="🎉 Начнём 🎉"), KeyboardButton(text="Меню 🗄️"))
    return main_menu.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


async def get_menu_keyboars() -> InlineKeyboardMarkup:
    menu_inline = InlineKeyboardBuilder()
    menu_inline.add(
        InlineKeyboardButton(text="Проверить баллы", callback_data="check_"),
        InlineKeyboardButton(text="Остались вопросы?", url="https://t.me/weekender_main"),
    )
    menu_inline.adjust(1)
    return menu_inline.as_markup()


async def categories_years() -> InlineKeyboardMarkup | ReplyKeyboardMarkup:
    all_categories_years = await get_categories_years()
    keyboard = InlineKeyboardBuilder()

    for category in all_categories_years:
        keyboard.add(InlineKeyboardButton(text=category.year, callback_data=f"category_{category.year}"))
        keyboard.adjust(1)
    return keyboard.as_markup()


async def marital_status() -> InlineKeyboardMarkup | ReplyKeyboardMarkup:
    all_marital_status = await get_marital_status()
    keyboard = InlineKeyboardBuilder()

    for status in all_marital_status:
        keyboard.add(InlineKeyboardButton(text=status.status, callback_data=f"status_{status.status}"))
        keyboard.adjust(1)
    return keyboard.as_markup()


async def admin_answer(user_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="Ответить", callback_data=f"answer_{user_id}"))
    return keyboard.as_markup()
