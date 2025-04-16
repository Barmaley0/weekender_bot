from app.database.models import async_session
from app.database.models import User
from sqlalchemy import select, update, delete


async def set_user(tg_id: int, first_name: str, username: str | None) -> None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            session.add(User(tg_id=tg_id, first_name=first_name, username=username))
            await session.commit()
