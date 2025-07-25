import logging

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.bot.db.models import SupportMessage, SupportTicket, User
from src.bot.utils.decorators import connect_db


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MOSCOW_TZ = 3  # UTC+3


@connect_db
async def get_active_ticket_for_user(session: AsyncSession, tg_id: int) -> Optional[SupportTicket]:
    """Только получаем активный тикет для существующего пользователя (без создания)"""
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not user:
        return None

    result = await session.scalar(
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id, SupportTicket.is_active)
        .order_by(SupportTicket.date_create.desc())
        .limit(1)
    )

    return result


@connect_db
async def create_support_ticket(session: AsyncSession, tg_id: int) -> SupportTicket:
    """Создаёт новый тикет (только для существующих пользователей)"""
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not user:
        raise ValueError(f'User {tg_id} not found')

    ticket = SupportTicket(user_id=user.id, is_active=True, date_create=datetime.now() + timedelta(hours=MOSCOW_TZ))
    session.add(ticket)
    await session.commit()
    return ticket


@connect_db
async def add_message_to_ticket(session: AsyncSession, ticket_id: int, text: str, is_from_user: bool) -> None:
    """Добавляем сообщение в тикет"""
    message = SupportMessage(
        ticket_id=ticket_id,
        text=text,
        is_from_user=is_from_user,
        date_create=datetime.now() + timedelta(hours=MOSCOW_TZ),
    )

    session.add(message)
    await session.commit()


@connect_db
async def close_ticket(session: AsyncSession, ticket_id: int) -> None:
    """Закрываем тикет"""
    ticket = await session.execute(update(SupportTicket).where(SupportTicket.id == ticket_id).values(is_active=False))
    logger.info(f'⛔ Ticket {ticket_id} closed - {ticket}')

    await session.commit()


@connect_db
async def get_active_tickets(session: AsyncSession) -> Sequence[SupportTicket]:
    """Получаем список активных тикетов с информацией о пользователях"""
    result = await session.execute(
        select(SupportTicket)
        .join(User)  # Джойним с пользователями
        .where(SupportTicket.is_active)  # Только активные тикеты
        .order_by(SupportTicket.date_create.desc())  # Сортировка по дате (новые сначала)
    )
    return result.scalars().all()


@connect_db
async def get_ticket_with_messages(session: AsyncSession, ticket_id: int) -> Optional[SupportTicket]:
    """Получаем тикеты с загруженными сообщениями"""
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.user))  # Жадно загружаем пользователя
        .options(selectinload(SupportTicket.messages))  # И все сообщения
        .where(SupportTicket.id == ticket_id)
    )
    return result.scalars().first()


@connect_db
async def get_ticket_by_id(session: AsyncSession, ticket_id: int) -> Optional[SupportTicket]:
    """Получаем тикет по ID с информацией о пользователе"""
    try:
        result = await session.execute(
            select(SupportTicket).options(selectinload(SupportTicket.user)).where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f'❗Error getting ticket by id: {ticket_id} - {e}')
        return None


@connect_db
async def get_all_messages_from_ticket(session: AsyncSession, ticket_id: int) -> Sequence[SupportMessage]:
    result = await session.execute(
        select(SupportMessage).where(SupportMessage.ticket_id == ticket_id).order_by(SupportMessage.date_create)
    )
    return result.scalars().all()
