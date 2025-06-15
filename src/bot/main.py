import asyncio
import logging
import os

from pathlib import Path

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.bot.db.models import create_db_and_tables
from src.bot.handlers.user import router_user


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / '.env.local'

    if env_path.exists():
        load_dotenv(env_path)
        logger.info('Load bot: .env.local')
    else:
        load_dotenv()
        logger.info('Load bot: .env')

    TOKEN = os.environ.get('BOT_TOKEN')

    if TOKEN is None:
        raise ValueError('BOT_TOKEN is not set')

    logger.info('Connecting to database...')
    await create_db_and_tables()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router_user)
    logger.info('Application startup complete')
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Application shutdown complete')
