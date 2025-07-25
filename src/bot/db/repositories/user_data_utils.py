import logging

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.db.models import Option, OptionCategory, User, UserOption
from src.bot.utils.decorators import connect_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


@connect_db
async def get_user_data(session: AsyncSession, user_id: int) -> dict[str, Any]:
    user = await session.scalar(select(User).where(User.tg_id == user_id))

    if not user:
        return {
            'first_name': None,
            'username': None,
            'total_likes': None,
            'year': None,
            'gender': None,
            'status': None,
            'target': None,
            'district': None,
            'profession': None,
            'about': None,
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
        'first_name': user.first_name,
        'username': user.username,
        'year': user.year,
        'total_likes': user.total_likes,
        'gender': None,
        'status': None,
        'target': None,
        'district': None,
        'profession': user.profession,
        'about': user.about,
        'interests': [],
    }

    for option_name, category_name in user_options:
        if category_name == 'gender':
            result['gender'] = option_name
        if category_name == 'status':
            result['status'] = option_name
        if category_name == 'target':
            result['target'] = option_name
        if category_name == 'district':
            result['district'] = option_name
        if category_name == 'interest':
            if isinstance(result['interests'], list):
                result['interests'].append(option_name)

    return result
