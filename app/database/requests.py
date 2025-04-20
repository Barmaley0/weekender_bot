from datetime import datetime

import pytz

from sqlalchemy import ScalarResult, select, update

from app.database.models import CategoryYear, MaritalStatus, User, async_session


async def set_user(tg_id: int, first_name: str, username: str | None) -> None:

    utc_timezone = pytz.timezone("UTC")
    created_at_utc = utc_timezone.localize(datetime.utcnow())
    local_timezone = pytz.timezone("Europe/Moscow")
    created_at_local = created_at_utc.astimezone(local_timezone)

    async with async_session() as session:
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


async def get_categories_years() -> ScalarResult[CategoryYear]:
    async with async_session() as session:
        return await session.scalars(select(CategoryYear))


async def get_marital_status() -> ScalarResult[MaritalStatus]:
    async with async_session() as session:
        return await session.scalars(select(MaritalStatus))


async def set_user_data_save(tg_id: int, year: str, status: str) -> None:

    utc_timezone = pytz.timezone("UTC")
    created_at_utc = utc_timezone.localize(datetime.utcnow())
    local_timezone = pytz.timezone("Europe/Moscow")
    created_at_local = created_at_utc.astimezone(local_timezone)

    async with async_session() as session:
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
