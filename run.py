import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.hanglers import router


load_dotenv()
TOKEN = os.environ.get("BOT_TOKEN")
if TOKEN is None:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN)
dp = Dispatcher()


async def main() -> None:
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is stopped")
