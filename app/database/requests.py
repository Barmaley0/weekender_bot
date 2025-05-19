import logging

from collections.abc import Awaitable, Sequence
from datetime import datetime
from typing import Any, Callable, Optional

import pytz

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Event, Option, OptionCategory, User, UserOption, async_session


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def connect_db(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with async_session() as session:
            return await func(session, *args, **kwargs)

    return wrapper


def get_age_range(age: int) -> str | None:
    ranges = {
        (18, 24): '18-24',
        (25, 34): '25-34',
        (35, 44): '35-44',
        (45, 54): '45-54',
        (55, 60): '55-60',
    }

    for (min_age, max_age), age_range in ranges.items():
        if min_age <= age <= max_age:
            return age_range

    return None


@connect_db
async def get_user(session: AsyncSession, tg_id: int) -> User | None:
    return await session.scalar(select(User).where(User.tg_id == tg_id))


@connect_db
async def get_user_points(session: AsyncSession, tg_id: int) -> int:
    points = await session.scalar(select(User.points).where(User.tg_id == tg_id))
    return points if points is not None else 0


@connect_db
async def get_all_marital_status(session: AsyncSession) -> set[Option]:
    marital_status = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'status').order_by(Option.name)
    )

    return set(marital_status.all())


@connect_db
async def set_user(session: AsyncSession, tg_id: int, first_name: str, username: Optional[str]) -> None:
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
                    select(Option.id).join(OptionCategory).where(OptionCategory.name.in_(['status', 'district']))
                ),
            )
        )

        # Добавляем новый выбор пользователя
        session.add_all(
            [
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
async def get_event_for_user(session: AsyncSession, year: int, status: str) -> Sequence[Event] | None:
    age_range = get_age_range(year)
    events = await session.scalars(select(Event).where(Event.year == age_range, Event.status == status))
    return events.all()


@connect_db
async def is_admin(session: AsyncSession, tg_id: int) -> bool:
    try:
        check_admin = await session.scalar(select(User.is_admin).where(User.tg_id == tg_id))
        if check_admin:
            return bool(check_admin)
        return False
    except Exception as e:
        print(f'Проверка администратора для tg_id {tg_id} {e}')
        return False


@connect_db
async def get_all_admin(session: AsyncSession) -> list[int]:
    admin = await session.scalars(select(User.tg_id).where(User.is_admin))
    list_admin = [tg_id for tg_id in admin.all()]

    return list_admin


@connect_db
async def get_user_district(session: AsyncSession, user_id: int) -> int | None:
    district = await session.scalar(
        select(UserOption.option_id)
        .join(Option)
        .join(OptionCategory)
        .where(UserOption.user_id == user_id, OptionCategory.name == 'district')
    )

    logger.info(f'Get user district {district}')
    return district


# TODO: нужен ли этот вариант
@connect_db
async def get_user_interests(session: AsyncSession, user_id: int) -> set[int]:
    interests = await session.scalars(
        select(UserOption.option_id)
        .join(Option)
        .join(OptionCategory)
        .where(UserOption.user_id == user_id, OptionCategory.name == 'interest')
    )

    logger.info(f'Get user interests {set(interests.all())}')
    return set(interests.all())


@connect_db
async def get_all_districts(session: AsyncSession) -> set[Option]:
    districts = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'district').order_by(Option.name)
    )

    return set(districts.all())


@connect_db
async def get_all_interests(session: AsyncSession) -> set[Option]:
    interests = await session.scalars(
        select(Option).join(OptionCategory).where(OptionCategory.name == 'interest').order_by(Option.name)
    )

    return set(interests.all())


@connect_db
async def get_user_data(session: AsyncSession, user_id: int) -> dict[str, Any]:
    user = await session.scalar(select(User).where(User.tg_id == user_id))

    if not user:
        return {
            'year': None,
            'status': None,
            'district': None,
            'interests': [],
        }

    # Получаем все выбранные опции пользователя
    user_options = await session.execute(
        select(Option.name, OptionCategory.name)
        .join(UserOption, UserOption.option_id == Option.id)
        .join(OptionCategory, Option.category_id == OptionCategory.id)
        .where(UserOption.user_id == user.id)
    )

    result: dict = {
        'year': user.year,
        'status': None,
        'district': None,
        'interests': [],
    }

    for option_name, category_name in user_options:
        if category_name == 'status':
            result['status'] = option_name
        elif category_name == 'district':
            result['district'] = option_name
        elif category_name == 'interest':
            if isinstance(result['interests'], list):
                result['interests'].append(option_name)

    return result
