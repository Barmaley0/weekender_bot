from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import pytz

from sqlalchemy import ScalarResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CategoryYear, MaritalStatus, User, async_session


def connect_db(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with async_session() as session:
            return await func(session, *args, **kwargs)

    return wrapper


@connect_db
async def get_user(session: AsyncSession, tg_id: int) -> User | None:
    return await session.scalar(select(User).where(User.tg_id == tg_id))


@connect_db
async def get_user_points(session: AsyncSession, tg_id: int) -> int:
    points = await session.scalar(select(User.points).where(User.tg_id == tg_id))
    return points if points is not None else 0


@connect_db
async def set_user(session: AsyncSession, tg_id: int, first_name: str, username: Optional[str]) -> None:

    utc_timezone = pytz.timezone("UTC")
    created_at_utc = utc_timezone.localize(datetime.utcnow())
    local_timezone = pytz.timezone("Europe/Moscow")
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
async def get_categories_years(session: AsyncSession) -> ScalarResult[CategoryYear]:
    return await session.scalars(select(CategoryYear))


@connect_db
async def get_marital_status(session: AsyncSession) -> ScalarResult[MaritalStatus]:
    return await session.scalars(select(MaritalStatus))


@connect_db
async def set_user_data_save(session: AsyncSession, tg_id: int, year: str, status: str) -> None:

    utc_timezone = pytz.timezone("UTC")
    created_at_utc = utc_timezone.localize(datetime.utcnow())
    local_timezone = pytz.timezone("Europe/Moscow")
    created_at_local = created_at_utc.astimezone(local_timezone)

    await session.execute(
        update(User)
        .where(User.tg_id == tg_id)
        .values(
            year=year,
            status=status,
            date_update=created_at_local,
        )
    )
    await session.commit()


@connect_db
async def is_admin(session: AsyncSession, tg_id: int) -> bool:
    try:
        check_admin = await session.scalar(select(User.is_admin).where(User.tg_id == tg_id))
        if check_admin:
            return bool(check_admin)
        return False
    except Exception as e:
        print(f"Проверка администратора для tg_id {tg_id} {e}")
        return False


@connect_db
async def get_all_admin(session: AsyncSession) -> list[int]:
    admin = await session.scalars(select(User.tg_id).where(User.is_admin))
    list_admin = [tg_id for tg_id in admin.all()]

    return list_admin
