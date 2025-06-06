import logging

from datetime import datetime
from typing import Any, Optional

import pytz

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.db.models import Option, OptionCategory, User, UserOption
from src.bot.utils.decorators import connect_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


@connect_db
async def get_user(session: AsyncSession, tg_id: int) -> User | None:
    return await session.scalar(select(User).where(User.tg_id == tg_id))


@connect_db
async def get_user_points(session: AsyncSession, tg_id: int) -> int:
    points = await session.scalar(select(User.points).where(User.tg_id == tg_id))
    return points if points is not None else 0


@connect_db
async def user_data_exists(session: AsyncSession, tg_id: int) -> bool:
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    logger.info(f'User data exists for tg_id: {tg_id}')

    if not user:
        logger.warning(f'User data not found for tg_id: {tg_id}')
        return False

    has_year = user.year is not None
    logger.info(f'User {tg_id} has year: {has_year}')

    return has_year


@connect_db
async def save_first_user(session: AsyncSession, tg_id: int, first_name: str, username: Optional[str]) -> None:
    utc_timezone = pytz.timezone('UTC')
    created_at_utc = utc_timezone.localize(datetime.utcnow())
    local_timezone = pytz.timezone('Europe/Moscow')
    created_at_local = created_at_utc.astimezone(local_timezone)

    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not user:
        session.add(
            User(
                tg_id=tg_id,
                first_name=first_name,
                username=username,
                date_create=created_at_local,
            )
        )
        await session.commit()


@connect_db
async def set_user_data_save(
    session: AsyncSession,
    tg_id: int,
    year: str,
    gender: str,
    status: str,
    district: str,
    interests: list[str],
) -> None:
    try:
        utc_timezone = pytz.timezone('UTC')
        created_at_utc = utc_timezone.localize(datetime.utcnow())
        local_timezone = pytz.timezone('Europe/Moscow')
        created_at_local = created_at_utc.astimezone(local_timezone)

        # Проверка существующего пользователя
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            logger.error(f'User with tg_id {tg_id} not found')
            raise ValueError(f'User with tg_id {tg_id} not found')

        # Сохроняем tg_id до коммита
        user_tg_id = user.tg_id

        # Обновляем основную информацию о пользователе
        await session.execute(
            update(User)
            .where(User.tg_id == tg_id)
            .values(
                year=year,
                date_update=created_at_local,
            )
        )

        # Находиь ID гендера
        gender_option = await session.scalar(
            select(Option)
            .join(OptionCategory)
            .where(
                OptionCategory.name == 'gender',
                Option.name == gender,
            )
        )
        if not gender_option:
            logger.error(f'Gender {gender} not found in database')
            raise ValueError(f'Gender {gender} not found')

        # Находим ID статуса
        status_option = await session.scalar(
            select(Option)
            .join(OptionCategory)
            .where(
                OptionCategory.name == 'status',
                Option.name == status,
            )
        )
        if not status_option:
            logger.error(f'Status {status} not found in database')
            raise ValueError(f'Status {status} not found')

        # Находиь ID округа
        district_option = await session.scalar(
            select(Option)
            .join(OptionCategory)
            .where(
                OptionCategory.name == 'district',
                Option.name == district,
            )
        )
        if not district_option:
            logger.error(f'District {district} not found in database')
            raise ValueError(f'District {district} not found')

        # Удаляем старый выбор пользователя (кроме интересов)
        await session.execute(
            delete(UserOption).where(
                UserOption.user_id == user.id,
                UserOption.option_id.in_(
                    select(Option.id)
                    .join(OptionCategory)
                    .where(OptionCategory.name.in_(['gender', 'status', 'district']))
                ),
            )
        )

        # Добавляем новый выбор пользователя
        session.add_all(
            [
                UserOption(
                    user_id=user.id,
                    option_id=gender_option.id,
                    selected=True,
                ),
                UserOption(
                    user_id=user.id,
                    option_id=status_option.id,
                    selected=True,
                ),
                UserOption(
                    user_id=user.id,
                    option_id=district_option.id,
                    selected=True,
                ),
            ]
        )

        # Обрабатываем интересы
        if interests:
            await session.execute(
                delete(UserOption).where(
                    UserOption.user_id == user.id,
                    UserOption.option_id.in_(
                        select(Option.id).join(OptionCategory).where(OptionCategory.name == 'interest')
                    ),
                )
            )
            interests_options = await session.scalars(
                select(Option).join(OptionCategory).where(OptionCategory.name == 'interest', Option.name.in_(interests))
            )
            logger.info(f'Added {interests_options} interests for user {user_tg_id}')

            for interest in interests_options:
                session.add(
                    UserOption(
                        user_id=user.id,
                        option_id=interest.id,
                        selected=True,
                    )
                )

            await session.commit()
            logger.info(f'Successfully saved user data for user {user_tg_id}')
    except Exception as e:
        await session.rollback()
        logger.error(f'Failed to save user data: {str(e)}', exc_info=True)
        raise


@connect_db
async def get_user_data(session: AsyncSession, user_id: int) -> dict[str, Any]:
    user = await session.scalar(select(User).where(User.tg_id == user_id))

    if not user:
        return {
            'year': None,
            'gender': None,
            'status': None,
            'district': None,
            'interests': [],
        }

    # Получаем все выбранные опции пользователя
    user_options = await session.execute(
        select(Option.name, OptionCategory.name)
        .select_from(UserOption)
        .join(Option, UserOption.option_id == Option.id)
        .join(OptionCategory, Option.category_id == OptionCategory.id)
        .where(UserOption.user_id == user.id)
    )

    result: dict = {
        'year': user.year,
        'gender': None,
        'status': None,
        'district': None,
        'interests': [],
    }

    for option_name, category_name in user_options:
        if category_name == 'gender':
            result['gender'] = option_name
        if category_name == 'status':
            result['status'] = option_name
        elif category_name == 'district':
            result['district'] = option_name
        elif category_name == 'interest':
            if isinstance(result['interests'], list):
                result['interests'].append(option_name)

    return result
