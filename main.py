import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.admin import router_admin
from app.database.models import create_db_and_tables
from app.handlers import router_user


load_dotenv()


async def main() -> None:
    TOKEN = os.environ.get("BOT_TOKEN")

    if TOKEN is None:
        raise ValueError("BOT_TOKEN is not set")

    await create_db_and_tables()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router_user)
    dp.include_router(router_admin)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is stopped")
