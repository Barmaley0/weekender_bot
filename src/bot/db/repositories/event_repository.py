import logging

from collections.abc import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.db.models import Event, EventInterest, Option, OptionCategory
from src.bot.db.repositories.user_data_utils import get_user_data
from src.bot.utils.age_range_utils import is_age_in_range
from src.bot.utils.decorators import connect_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


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

    # Фильтр по возрасту (обязательный)
    age_ranges = await session.scalars(select(Event.year).where(Event.year.is_not(None)).distinct())
    age_conds = []
    for age_range in age_ranges:
        if is_age_in_range(user_age, age_range):
            age_conds.append(Event.year == age_range)

    if not age_conds:
        return []
    conditions.append(or_(*age_conds))

    # Фильтр по полу (если указан)
    if gender := user_data.get('gender'):
        conditions.append(or_(Event.gender == gender, Event.gender.is_(None), Event.gender == 'Любой'))

    # Фильтр по статусу (если указан)
    if status := user_data.get('status'):
        conditions.append(or_(Event.status == status, Event.status.is_(None), Event.status == 'Любой'))

    # Фильтр по интересам (только если указаны)
    if interests := user_data.get('interests'):
        stmt = (
            select(EventInterest.event_id)
            .join(Option, EventInterest.interest_id == Option.id)
            .join(OptionCategory, Option.category_id == OptionCategory.id)
            .where(OptionCategory.name == 'interest', Option.name.in_(interests))
        )
        conditions.append(Event.id.in_(stmt))

    # Исключаем уже показанные события
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
