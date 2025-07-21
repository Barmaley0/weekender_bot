import logging

from typing import Optional

from aiogram.fsm.context import FSMContext
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.bot.db.models import Option, User, UserOption
from src.bot.utils.decorators import connect_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


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
async def get_users_for_mass_send(session: AsyncSession, state: FSMContext) -> list[tuple[int, Optional[str]]]:
    """Получаем список всех пользователей (tg_id, username) согласно фильтрам рассылки"""
    data = await state.get_data()

    # Базовый запрос
    query = select(User.tg_id, User.username).where(User.username.is_not(None))

    # Оптимизация возрастных диапазонов
    if age_ranges := data.get('age_users', []):
        age_conditions = []
        current_min: Optional[int] = None
        current_max: Optional[int] = None

        # Сортируем диапазоны
        sorted_ranges = sorted([r for r in age_ranges if isinstance(r, str)], key=lambda x: int(x.split('-')[0]))

        for age_range in sorted_ranges:
            try:
                range_min, range_max = map(int, age_range.split('-'))
                if current_min is None or current_max is None:
                    current_min, current_max = range_min, range_max
                elif range_min == current_max + 1:
                    current_max = range_max
                else:
                    if current_min is not None and current_max is not None:
                        age_conditions.append((User.year >= current_min) & (User.year <= current_max))
                    current_min, current_max = range_min, range_max
            except (ValueError, AttributeError):
                continue

        if current_min is not None and current_max is not None:
            age_conditions.append((User.year >= current_min) & (User.year <= current_max))

        if age_conditions:
            query = query.where(or_(*age_conditions))

    # Собираем ID опций для фильтров
    option_filters = []

    # Фильтр по району
    if districts := data.get('district_users', []):
        district_options = await session.scalars(select(Option.id).where(Option.name.in_(districts)))
        option_filters.append(district_options.all())  # Сохраняем список ID

    # Фильтр по цели
    if targets := data.get('target_users', []):
        target_options = await session.scalars(select(Option.id).where(Option.name.in_(targets)))
        option_filters.append(target_options.all())

    # Фильтр по полу
    if genders := data.get('gender_users', []):
        gender_options = await session.scalars(select(Option.id).where(Option.name.in_(genders)))
        option_filters.append(gender_options.all())

    # Добавляем условия JOIN для каждого фильтра
    for i, option_ids in enumerate(option_filters):
        if not option_ids:  # Пропускаем пустые списки
            continue

        uo_alias = aliased(UserOption, name=f'uo_{i}')
        query = query.join(
            uo_alias,
            and_(
                uo_alias.user_id == User.id,
                uo_alias.selected,
                uo_alias.option_id.in_(option_ids),  # Теперь передается список ID
            ),
        )

    # Выполняем запрос
    result = await session.execute(query)
    return [(row.tg_id, row.username) for row in result.unique()]
