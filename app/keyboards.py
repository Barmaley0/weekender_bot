from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎉Подобрать мероприятие🎉")],
        [KeyboardButton(text="Проверить баллы 🔍"), KeyboardButton(text="Остались вопросы❓")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

years_category = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="18-24", callback_data="18-24"),
            InlineKeyboardButton(text="25-34", callback_data="25-34"),
            InlineKeyboardButton(text="35-44", callback_data="35-44"),
            InlineKeyboardButton(text="45-54", callback_data="45-54"),
            InlineKeyboardButton(text="55+", callback_data="55+"),
        ],
    ]
)

marital_status = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Женат", callback_data="Женат"),
            InlineKeyboardButton(text="Замужем", callback_data="Замужем"),
            InlineKeyboardButton(text="Не женат", callback_data="Не женат"),
            InlineKeyboardButton(text="Не замужем", callback_data="Не замужем"),
        ],
    ]
)
