import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.db.models import User
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
