from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎉Подобрать мероприятие🎉")],
        [KeyboardButton(text="Проверить баллы 🔍"), KeyboardButton(text="Остались вопросы❓")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)
