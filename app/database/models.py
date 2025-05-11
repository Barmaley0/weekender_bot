import logging
import os

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(String(40), nullable=True)
    username: Mapped[str] = mapped_column(String(40), nullable=True)
    year: Mapped[str] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=True)
    date_create: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    date_update: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    points: Mapped[int] = mapped_column(Integer(), default=100, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)

    def __repr__(self) -> str:
        return f'User id: {self.id}, tg_id: {self.tg_id}'


class CategoryYear(Base):
    __tablename__ = 'categories_years'

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[str] = mapped_column(String(20), nullable=True)


class MaritalStatus(Base):
    __tablename__ = 'marital_statuses'

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=True)


class Event(Base):
    __tablename__ = 'events'

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(150), nullable=False)


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
