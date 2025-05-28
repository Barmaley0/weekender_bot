import logging

from collections.abc import Awaitable, Sequence
from datetime import datetime
from typing import Any, Callable, Optional

import pytz

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Event, EventInterest, Option, OptionCategory, User, UserOption, async_session


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


def connect_db(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with async_session() as session:
            return await func(session, *args, **kwargs)

    return wrapper


def is_age_in_range(user_age: int, event_age_range: str) -> bool:
    try:
        if '-' in event_age_range:
            min_age, max_age = map(int, event_age_range.split('-'))
            return min_age <= user_age <= max_age
        elif event_age_range.endswith('+'):
            return user_age >= int(event_age_range[:-1])
        else:
            return int(event_age_range) == user_age
    except (ValueError, AttributeError):
        return False


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


# RECOMMENDATIONS -->
@connect_db
async def get_recommended_events(session: AsyncSession, tg_id: int, limit: int = 3) -> Sequence[Event] | None:
    logger.info(f'Starting recommendations for tg_id: {tg_id}')

    # Получаем данные пользователя
    user_data = await get_user_data(tg_id)
    if not user_data:
        logger.warning(f'User data not found for tg_id: {tg_id}')
        return None

    # Проверка возраста (обязательное поле)
    if not user_data.get('year'):
        logger.warning(f'Age not specified for user: {tg_id}')
        return None

    try:
        user_age = int(user_data['year'])
    except (ValueError, TypeError) as e:
        logger.error(f'Invalid age format for user {tg_id}: {e}')
        return None

    # Базовый запрос с джойном интересов
    query = (
        select(Event)
        .distinct()
        .outerjoin(EventInterest, Event.id == EventInterest.event_id)
        .outerjoin(Option, EventInterest.interest_id == Option.id)
        .outerjoin(OptionCategory, Option.category_id == OptionCategory.id)
    )

    conditions = []

    # 1. Фильтр по возрасту (обязательный)
    age_conditions = []
    all_age_ranges = (await session.scalars(select(Event.year).distinct())).all()
    logger.info(f'Available age ranges: {all_age_ranges}')

    for age_range in all_age_ranges:
        if age_range and is_age_in_range(user_age, age_range):
            age_conditions.append(Event.year == age_range)

    if not age_conditions:
        logger.info(f'No events for age {user_age}')
        return []

    conditions.append(or_(*age_conditions))

    # 2. Фильтр по полу (если указан)
    if user_data.get('gender'):
        conditions.append(or_(Event.gender == user_data['gender'], Event.gender.is_(None), Event.gender == 'Любой'))

    # 3. Фильтр по статусу (если указан)
    if user_data.get('status'):
        conditions.append(or_(Event.status == user_data['status'], Event.status.is_(None), Event.status == 'Любой'))

    # 4. Фильтр по интересам (если указаны)
    if user_data.get('interests'):
        # Получаем ID выбранных интересов
        interest_ids = (
            await session.scalars(
                select(Option.id)
                .join(OptionCategory)
                .where(OptionCategory.name == 'interest', Option.name.in_(user_data['interests']))
            )
        ).all()

        if interest_ids:
            # Создаем подзапрос для событий с этими интересами
            subquery = (
                select(EventInterest.event_id).where(EventInterest.interest_id.in_(interest_ids)).distinct()
            ).scalar_subquery()

            conditions.append(Event.id.in_(subquery))
        else:
            logger.info('No matching interests found')
            return []

    # Применяем все условия
    final_query = query.where(and_(*conditions))

    # Сортировка и лимит
    final_query = final_query.order_by(Event.id.desc()).limit(limit)

    logger.info(f'Final query: {final_query}')

    try:
        result = await session.scalars(final_query)
        events = result.all()

        if not events:
            logger.info('No events after all filters applied')
            return []

        return events
    except Exception as e:
        logger.error(f'Query execution error: {e}')
        return None


# END RECOMMENDATIONS


@connect_db
async def get_recommended_events_new(
    session: AsyncSession,
    tg_id: int,
    limit: int = 3,
    exclude_ids: list[int] | None = None,
) -> Sequence[Event] | None:
    # Получаем данные пользователя
    user_data = await get_user_data(tg_id)
    if not user_data or not user_data.get('year'):
        return None

    try:
        user_age = int(user_data['year'])
    except (ValueError, TypeError):
        return None

    # Базовый запрос без лишних джойнов
    query = select(Event)

    # Основные условия фильтрации
    conditions = []

    # 1. Фильтр по возрасту (обязательный)
    age_ranges = await session.scalars(select(Event.year).where(Event.year.is_not(None)).distinct())
    age_conds = []
    for age_range in age_ranges:
        if is_age_in_range(user_age, age_range):
            age_conds.append(Event.year == age_range)

    if not age_conds:
        return []
    conditions.append(or_(*age_conds))

    # 2. Фильтр по полу (если указан)
    if gender := user_data.get('gender'):
        conditions.append(or_(Event.gender == gender, Event.gender.is_(None), Event.gender == 'Любой'))

    # 3. Фильтр по статусу (если указан)
    if status := user_data.get('status'):
        conditions.append(or_(Event.status == status, Event.status.is_(None), Event.status == 'Любой'))

    # 4. Фильтр по интересам (только если указаны)
    if interests := user_data.get('interests'):
        stmt = (
            select(EventInterest.event_id)
            .join(Option, EventInterest.interest_id == Option.id)
            .join(OptionCategory, Option.category_id == OptionCategory.id)
            .where(OptionCategory.name == 'interest', Option.name.in_(interests))
        )
        conditions.append(Event.id.in_(stmt))

    # 5. Исключаем уже показанные события
    if exclude_ids:
        conditions.append(Event.id.not_in(exclude_ids))

    # Применяем все условия
    query = query.where(and_(*conditions))

    # Случайная сортировка и лимит
    query = query.order_by().limit(limit)

    try:
        return (await session.scalars(query)).all()
    except Exception as e:
        logger.error(f'Query error: {e}')
        return None


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
