import asyncio
import logging
import os

from pathlib import Path

import sqlalchemy as sa

from database.models import Option, OptionCategory, async_session
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_connection() -> bool:
    try:
        project_root = Path(__file__).parent.parent
        env_path = project_root / '.env.local'

        if env_path.exists():
            load_dotenv(env_path)
            logger.info('Load bot: .env.local')
        else:
            load_dotenv()
            logger.info('Load bot: .env')

        DATABASE_URLS = os.environ.get('DATABASE_URL')
        print(DATABASE_URLS)

        if DATABASE_URLS is None:
            logger.error(f'DATABASE_URL is not set ->> {DATABASE_URLS}')
        async with async_session() as session:
            try:
                await asyncio.wait_for(session.execute(sa.select(1)), timeout=5)
            except asyncio.TimeoutError:
                logger.error('Database connection timeout')
                return False
        return True
    except Exception as e:
        logger.error(f'Connection error 1: {e}')
        return False


async def seed_data() -> bool:
    if not await check_connection():
        logger.info('Connection error 2')
        return False

    try:
        async with async_session() as session:
            existing_categories = await session.execute(sa.select(OptionCategory).limit(1))
            if existing_categories.scalars().first():
                logger.info('Data already exists - skipping')
                return False

            categories = [
                OptionCategory(name='status'),
                OptionCategory(name='district'),
                OptionCategory(name='interest'),
            ]
            session.add_all(categories)
            logger.info('Categories added')
            await session.flush()

            options = [
                Option(category_id=categories[0], name='Замужем'),
                Option(category_id=categories[0], name='Женат'),
                Option(category_id=categories[0], name='Не замужем'),
                Option(category_id=categories[0], name='Не женат'),
                Option(category_id=categories[1], name='ЦАО'),
                Option(category_id=categories[1], name='ЗАО'),
                Option(category_id=categories[1], name='СЗАО'),
                Option(category_id=categories[1], name='САО'),
                Option(category_id=categories[1], name='СВАО'),
                Option(category_id=categories[1], name='ВАО'),
                Option(category_id=categories[1], name='ЮВАО'),
                Option(category_id=categories[1], name='ЮАО'),
                Option(category_id=categories[1], name='ЮЗАО'),
                Option(category_id=categories[2], name='Only girls'),
                Option(category_id=categories[2], name='Активный отдых'),
                Option(category_id=categories[2], name='Бизнес'),
                Option(category_id=categories[2], name='Вечеринки, караоке'),
                Option(category_id=categories[2], name='Гастро'),
                Option(category_id=categories[2], name='Дейтинг'),
                Option(category_id=categories[2], name='Загород'),
                Option(category_id=categories[2], name='Кино'),
                Option(category_id=categories[2], name='Концерт'),
                Option(category_id=categories[2], name='Культура'),
                Option(category_id=categories[2], name='Настолки, квизы'),
                Option(category_id=categories[2], name='Нетворкинг'),
                Option(category_id=categories[2], name='Образовательное'),
                Option(category_id=categories[2], name='Спорт'),
                Option(category_id=categories[2], name='Творчество, мастер-классы'),
                Option(category_id=categories[2], name='Телеска'),
            ]

            session.add_all(options)
            await session.commit()
            logger.info('Data seeded successfully')
            return True
    except Exception as e:
        logger.error(f'Failed to seed data: {e}')
        await session.rollback()
        return False
    finally:
        await session.close()


if __name__ == '__main__':
    result = asyncio.run(seed_data())
    if not result:
        logger.error('Data seeding failed')
        exit(1)
