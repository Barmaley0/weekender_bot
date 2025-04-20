from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.requests import get_categories_years, get_marital_status


main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎉Подобрать мероприятие🎉")],
        [KeyboardButton(text="Проверить баллы 🔍"), KeyboardButton(text="Остались вопросы❓")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)


async def categories_years() -> InlineKeyboardMarkup | ReplyKeyboardMarkup:
    all_categories_years = await get_categories_years()
    keyboard = InlineKeyboardBuilder()

    for category in all_categories_years:
        keyboard.add(InlineKeyboardButton(text=category.year, callback_data=f"category_{category.year}"))
    return keyboard.as_markup()


async def marital_status() -> InlineKeyboardMarkup | ReplyKeyboardMarkup:
    all_marital_status = await get_marital_status()
    keyboard = InlineKeyboardBuilder()

    for status in all_marital_status:
        keyboard.add(InlineKeyboardButton(text=status.status, callback_data=f"status_{status.status}"))
    return keyboard.as_markup()
