import logging
import os

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env.local'

if env_path.exists():
    load_dotenv(env_path)
    logger.info('Load db: .env.local')
else:
    load_dotenv()
    logger.info('Load db: .env')

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL is None:
    raise ValueError('DATABASE_URL is not set')

engine = create_async_engine(url=DATABASE_URL)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass
