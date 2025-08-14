import logging

from collections.abc import Sequence
from datetime import datetime
from typing import Optional, Union

import pytz

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.bot.db.models import FriendRequest, LikeProfile, Option, OptionCategory, PhotoProfile, User, UserOption
from src.bot.db.repositories.user_data_utils import get_user_data
from src.bot.utils.decorators import connect_db
from src.bot.utils.user_helpers import send_match_notification


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
async def add_total_like(session: AsyncSession, to_tg_id: int) -> None:
    user_exists = await session.scalar(select(exists().where(User.tg_id == to_tg_id)))
    if not user_exists:
        return

    await session.execute(update(User).where(User.tg_id == to_tg_id).values(total_likes=User.total_likes + 1))
    await session.commit()


@connect_db
async def delete_total_like(session: AsyncSession, to_tg_id: int) -> None:
    user_exists = await session.scalar(select(exists().where(User.tg_id == to_tg_id)))
    if not user_exists:
        return

    await session.execute(
        update(User).where(User.tg_id == to_tg_id).values(total_likes=func.greatest(User.total_likes - 1, 0))
    )
    await session.commit()


@connect_db
async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(func.lower(User.username) == func.lower(username)))


@connect_db
async def get_user_photos(session: AsyncSession, tg_id: int) -> list[str] | None:
    """Получает фото пользователя"""
    photo_list = await session.scalar(
        select(PhotoProfile.profile_photo_ids).join(User, PhotoProfile.user_id == User.id).where(User.tg_id == tg_id)
    )

    logger.info(f'User {tg_id} photo list: {photo_list}')

    return photo_list or []


@connect_db
async def update_user_photos(session: AsyncSession, bot: Bot, tg_id: int) -> list[str]:
    """Обновляет фото пользователя и возвращает свежие file_id"""
    try:
        # Получаем свежие фото
        user_photos = await bot.get_user_profile_photos(user_id=tg_id, limit=10)
        new_photo_ids = (
            [photo[-1].file_id for photo in user_photos.photos] if user_photos and user_photos.photos else []
        )

        # Сохраняем в базу
        await save_user_photos(session, tg_id, new_photo_ids)
        return new_photo_ids
    except Exception as e:
        logger.error(f'Failed to update photos for user {tg_id}: {e}')
        return []


@connect_db
async def update_only_interests(session: AsyncSession, tg_id: int, interests: list[str]) -> bool:
    """Обновляет только интересы пользователя"""
    try:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            logger.warning(f'User {tg_id} not found')
            return False

        # Удаляем старые интересы
        await session.execute(
            delete(UserOption).where(
                UserOption.user_id == user.id,
                UserOption.option_id.in_(
                    select(Option.id).join(OptionCategory).where(OptionCategory.name == 'interest')
                ),
            )
        )

        # Добавляем новые интересы
        interest_options = await session.scalars(
            select(Option).join(OptionCategory).where(OptionCategory.name == 'interest', Option.name.in_(interests))
        )

        for option in interest_options:
            session.add(UserOption(user_id=user.id, option_id=option.id, selected=True))

        await session.commit()
        logger.info(f'Interests updated for user {tg_id}')
        return True

    except Exception as e:
        logger.error(f'Error updating interests: {e}')
        await session.rollback()
        return False


@connect_db
async def find_compatible_users(
    session: AsyncSession, tg_id: int, age_ranges: list[str], limit: int = 7, exclude_ids: list[int] | None = None
) -> Sequence[User]:
    """Находит совместимых пользователей с учетом цели (по возрасту и округу)"""
    logger.info(f'Searching compatible users for tg_id: {tg_id}')

    # Получаем данные текущего пользователя
    current_user = await get_user(tg_id)
    if not current_user:
        return []

    user_data = await get_user_data(tg_id)
    if not user_data:
        return []

    # Базовые условия
    conditions = [User.tg_id != tg_id]

    # 1. Фильтр по возрасту
    age_conditions = []
    for age_range in age_ranges:
        try:
            if age_range.endswith('+'):
                min_age = int(age_range[:-1])
                age_conditions.append(User.year >= min_age)
            else:
                min_age, max_age = map(int, age_range.split('-'))
                age_conditions.append(and_(User.year >= min_age, User.year <= max_age))
        except (ValueError, AttributeError):
            continue

    if age_conditions:
        conditions.append(or_(*age_conditions))

    DISTRICT_GROUPS = {
        'ЦАО': ['ЦАО', 'ЗАО', 'СЗАО', 'САО', 'СВАО', 'ВАО', 'ЮВАО', 'ЮАО', 'ЮЗАО'],
        'ЗАО': ['ЗАО', 'СЗАО', 'ЮЗАО', 'ЦАО'],
        'СЗАО': ['СЗАО', 'САО', 'ЗАО', 'ЦАО'],
        'САО': ['САО', 'СЗАО', 'СВАО', 'ЦАО'],
        'СВАО': ['СВАО', 'САО', 'ВАО', 'ЦАО'],
        'ВАО': ['ВАО', 'СВАО', 'ЮВАО', 'ЦАО'],
        'ЮВАО': ['ЮВАО', 'ВАО', 'ЮАО', 'ЦАО'],
        'ЮАО': ['ЮАО', 'ЮВАО', 'ЮЗАО', 'ЦАО'],
        'ЮЗАО': ['ЮЗАО', 'ЮАО', 'ЗАО', 'ЦАО'],
    }

    districts = DISTRICT_GROUPS.get(user_data['district'], [user_data['district']])
    logger.info(f'User districts: {user_data["district"]},  searched districts: {districts}')

    # 2. Фильтр по округу
    if user_data.get('district'):
        district_condition = exists().where(
            and_(
                UserOption.user_id == User.id,
                UserOption.option_id == Option.id,
                Option.name.in_(districts),
                OptionCategory.name == 'district',
                UserOption.selected,
            )
        )
        conditions.append(district_condition)

    # Исключаем уже показанных пользователей
    if exclude_ids:
        conditions.append(User.tg_id.not_in(exclude_ids))

    # Формируем запрос
    query = (
        select(User)
        .where(and_(*conditions))
        .options(
            selectinload(User.photo_profile),
            selectinload(User.options).joinedload(UserOption.option).joinedload(Option.category),
        )
        .order_by(func.random())
        .limit(limit)
    )

    try:
        result = await session.scalars(query)
        return result.unique().all()
    except Exception as e:
        logger.error(f'Error finding compatible users: {e}')
        return []


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
async def save_user_photos(session: AsyncSession, tg_id: int, photo_ids: list[str], max_photos: int = 10) -> None:
    try:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if not user:
            logger.error(f'User with tg_id {tg_id} not found')
            return

        if len(photo_ids) > max_photos:
            photo_ids = photo_ids[:max_photos]

        logger.info(f'➡️ User {tg_id} tried to save {len(photo_ids)} photos, limiting to  {max_photos}')
        await session.execute(delete(PhotoProfile).where(PhotoProfile.user_id == user.id))

        session.add(
            PhotoProfile(
                user_id=user.id,
                profile_photo_ids=photo_ids,
            )
        )
        await session.commit()
        logger.info(f'User {tg_id} photos saved')
    except Exception as e:
        logger.error(f'Failed to save user {tg_id} photos: {e}', exc_info=True)


@connect_db
async def set_user_data_save(
    session: AsyncSession,
    tg_id: int,
    year: str,
    gender: str,
    status: str,
    target: str,
    district: str,
    profession: str,
    about: str,
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
                profession=profession,
                about=about,
            )
        )

        # Находим ID гендера
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

        # Находим ID цели
        target_option = await session.scalar(
            select(Option)
            .join(OptionCategory)
            .where(
                OptionCategory.name == 'target',
                Option.name == target,
            )
        )
        if not target_option:
            logger.error(f'Target {target} not found in database')
            raise ValueError(f'Target {target} not found')

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
                    .where(OptionCategory.name.in_(['gender', 'status', 'target', 'district']))
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
                    option_id=target_option.id,
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
async def load_user_like_and_friend(session: AsyncSession, user_id: int, state: FSMContext) -> None:
    """Загрузка пользователем своих лайков и друзей"""
    try:
        # Получаем пользователя из БД
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            logger.error(f'User {user_id} not found')
            return

        # Получаем все лайки пользователя
        like_ids = await session.scalars(
            select(User.tg_id)
            .join(LikeProfile, User.id == LikeProfile.to_user_id)
            .where(LikeProfile.from_user_id == user.id)
        )

        # Получаем все запросы в друзья
        friend_ids = await session.scalars(
            select(User.tg_id)
            .join(FriendRequest, User.id == FriendRequest.to_user_id)
            .where(FriendRequest.from_user_id == user.id)
        )

        # Получаем взаимные лайки
        reciprocated_like_ids = await session.scalars(
            select(User.tg_id)
            .join(LikeProfile, User.id == LikeProfile.from_user_id)
            .where(
                LikeProfile.to_user_id == user.id,
                LikeProfile.is_reciprocated,
            )
        )

        # Получаем взаимные запросы в друзья
        reciprocated_friend_ids = await session.scalars(
            select(User.tg_id)
            .join(FriendRequest, User.id == FriendRequest.from_user_id)
            .where(
                FriendRequest.to_user_id == user.id,
                FriendRequest.is_reciprocated,
            )
        )

        reciprocated_ids = set(reciprocated_like_ids) | set(reciprocated_friend_ids)

        # Обновляем состояние
        await state.update_data(
            {
                'liked_profile_ids': list(like_ids),
                'friend_profile_ids': list(friend_ids),
                'reciprocated_profile_ids': list(reciprocated_ids),
            }
        )

        logger.info(
            f'Loaded likes and friends for user {user_id}: '
            f'likes={list(like_ids)}, friends={list(friend_ids)}, '
            f'reciprocated={list(reciprocated_ids)}'
        )

    except Exception as e:
        logger.error(f'Error loading likes and friends: {e}')
        raise


@connect_db
async def add_like_and_friend_to_db(
    session: AsyncSession,
    from_tg_id: int,
    to_tg_id: int,
    action_type: str,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Добавление лайка и дружбы в БД, проверка существования пользователей"""

    try:
        # Проверяем существование пользователей
        from_user_exists = await session.scalar(select(exists().where(User.tg_id == from_tg_id)))
        to_user_exists = await session.scalar(select(exists().where(User.tg_id == to_tg_id)))

        if not from_user_exists or not to_user_exists:
            logger.info(f'*** Пользователи с tg_id  {from_tg_id} и {to_tg_id} не существуют в базе данных')
            return

        # Получаем id пользователей
        from_user_id = await session.scalar(select(User.id).where(User.tg_id == from_tg_id))
        to_user_id = await session.scalar(select(User.id).where(User.tg_id == to_tg_id))
        logger.info(
            f'*** Пользователи с id  {from_tg_id}-{from_user_id} и {to_tg_id}-{to_user_id} получают существующие id'
        )

        model: Union[type[LikeProfile], type[FriendRequest]]

        # Определяем модель
        if action_type == 'like':
            model = LikeProfile
        elif action_type == 'friend':
            model = FriendRequest
        else:
            raise ValueError(f'Unknown action type: {action_type}')

        # Проверяем существование связи
        exist = await session.scalar(
            select(
                exists().where(
                    model.from_user_id == from_user_id,
                    model.to_user_id == to_user_id,
                )
            )
        )

        if not exist:
            session.add(
                model(
                    from_user_id=from_user_id,
                    to_user_id=to_user_id,
                    date_create=datetime.now(),
                )
            )
            await session.commit()

        # Проверяем взамность лайков
        is_reciprocal = await session.scalar(
            select(
                exists().where(
                    model.from_user_id == to_user_id,
                    model.to_user_id == from_user_id,
                )
            )
        )

        # Устанавливаем взамность True
        if is_reciprocal:
            data = await state.get_data()
            reciprocated_ids = data.get('reciprocated_profile_ids', [])
            if from_tg_id not in reciprocated_ids:
                reciprocated_ids.append(from_tg_id)
            if to_tg_id not in reciprocated_ids:
                reciprocated_ids.append(to_tg_id)
            await state.update_data({'reciprocated_profile_ids': reciprocated_ids})
            await session.execute(
                update(model)
                .where(model.from_user_id == to_user_id)
                .where(model.to_user_id == from_user_id)
                .values(is_reciprocated=True)
            )
            await session.execute(
                update(model)
                .where(model.from_user_id == from_user_id)
                .where(model.to_user_id == to_user_id)
                .values(is_reciprocated=True)
            )
            await session.commit()

            # Получаем цель
            target = 'like' if action_type == 'like' else 'friend'

            # Отправляем уведомления обоим пользователям
            if bot:
                try:
                    await send_match_notification(bot, from_tg_id, to_tg_id, state, target)
                    await send_match_notification(bot, to_tg_id, from_tg_id, state, target)
                except Exception as e:
                    logger.error(f'*** Ошибка в send_match_notification: {e}', exc_info=True)

    except Exception as e:
        logger.error(f'*** Ошибка в add_like_and_friend_to_db: {e}', exc_info=True)
        await session.rollback()
    finally:
        data = await state.get_data()
        liked_ids = data.get('liked_profile_ids', [])
        logger.info(f'*** liked_ids: {liked_ids}')

        if to_tg_id not in liked_ids:
            liked_ids.append(to_tg_id)
            await state.update_data({'liked_profile_ids': liked_ids})


@connect_db
async def delete_like_and_friend_from_db(
    session: AsyncSession,
    from_tg_id: int,
    to_tg_id: int,
    action_type: str,
) -> None:
    """Удаление лайка и дружбы из БД, проверка перед удалением"""

    # Проверяем существование пользователей
    from_user_exists = await session.scalar(select(exists().where(User.tg_id == from_tg_id)))
    to_user_exists = await session.scalar(select(exists().where(User.tg_id == to_tg_id)))

    if not from_user_exists or not to_user_exists:
        logger.info(f'*** Пользователи с tg_id  {from_tg_id} и {to_tg_id} не существуют в базе данных')
        return

    # Получаем id пользователей
    from_user_id = await session.scalar(select(User.id).where(User.tg_id == from_tg_id))
    to_user_id = await session.scalar(select(User.id).where(User.tg_id == to_tg_id))
    logger.info(
        f'*** Пользователи с id  {from_tg_id}-{from_user_id} и {to_tg_id}-{to_user_id} получают существующие id'
    )

    model: Union[type[LikeProfile], type[FriendRequest]]

    if action_type == 'like':
        model = LikeProfile
    elif action_type == 'friend':
        model = FriendRequest
    else:
        raise ValueError(f'Unknown action type: {action_type}')

    await session.execute(
        delete(model).where(
            model.from_user_id == from_user_id,
            model.to_user_id == to_user_id,
        )
    )
    await session.commit()


@connect_db
async def check_reciprocity(session: AsyncSession, from_tg_id: int, to_tg_id: int) -> bool | None:
    # Сначала находим пользователей по tg_id
    from_user = await session.scalar(select(User).where(User.tg_id == from_tg_id))
    to_user = await session.scalar(select(User).where(User.tg_id == to_tg_id))

    if not from_user or not to_user:
        return False

    # Теперь сравниваем их внутренние ID
    return await session.scalar(
        select(exists().where(LikeProfile.from_user_id == from_user.id, LikeProfile.to_user_id == to_user.id))
    )
