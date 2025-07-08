import logging

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.db.models import Option, OptionCategory
from src.bot.utils.decorators import connect_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


@connect_db
async def get_all_gender(session: AsyncSession) -> Sequence[Option]:
    gender = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'gender').order_by(Option.id)
    )

    return gender.all()


@connect_db
async def get_all_marital_status(session: AsyncSession) -> Sequence[Option]:
    marital_status = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'status').order_by(Option.id)
    )

    return marital_status.all()


@connect_db
async def get_all_target(session: AsyncSession) -> Sequence[Option]:
    target = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'target').order_by(Option.id)
    )

    return target.all()


@connect_db
async def get_all_districts(session: AsyncSession) -> Sequence[Option]:
    districts = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'district').order_by(Option.id)
    )

    return districts.all()


@connect_db
async def get_all_interests(session: AsyncSession) -> Sequence[Option]:
    interests = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'interest').order_by(Option.id)
    )

    return interests.all()


@connect_db
async def get_all_age_range(session: AsyncSession) -> Sequence[Option]:
    age_range = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'age_ranges').order_by(Option.id)
    )

    return age_range.all()
