import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.handlers import router_user
from app.database.models import create_db_and_tables


load_dotenv()


async def main() -> None:
    TOKEN = os.environ.get("BOT_TOKEN")

    if TOKEN is None:
        raise ValueError("BOT_TOKEN is not set")

    await create_db_and_tables()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router_user)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is stopped")

"""
1. Пользователь нажимает кнопку старт.
1.1 Выходит приветствие.
1.2 Информацию уходит в базу данных.
1.3 Вывод клавиатуры ReplyKeboardMarkup(Кнопи клавиатуры: Подобрать мероприятие,
Проверить баллы, Остались вопросы, Изменить ифльтры, Чат Weekender).
2. Пользователь нажимает кнопку Подобрать мероприятие.
2.1 Выходит сообщение(Введите данные для поиска. Выберите возрастную категорию).
2.2 К сообщению прекреплена клавиатура InlineKeyboardMarkup(Кнопки клавиатуры возраст:
18-24, 25-34, 35-44, 45-54, 55+).
2.3 Выходит сооищение(Введите семейный статус).
2.4 К сообщению прекреплена клавиатура InlineKeyboardMarkup(Кнопки клавиатуры статус:
Женат, Замужем, Не женат, Не замужем).
2.5 Информация уходит в базу данных.
"""
