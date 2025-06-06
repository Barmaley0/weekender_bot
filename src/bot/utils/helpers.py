import asyncio
import logging

from typing import Optional

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, MaybeInaccessibleMessage, Message

import src.bot.db.repositories.admin_repository as req_admin


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()
router_admin = Router()


# Проверка пользователя на администратора
class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is not None:
            return await req_admin.is_admin(message.from_user.id)
        return False


# Удаление сообщения
async def safe_delete_message(message: MaybeInaccessibleMessage) -> bool:
    if not isinstance(message, Message):
        logger.info('Message is not a Message object')
        return False
    try:
        await message.delete()
        logger.info(f'Deleted message: {message.message_id}, chat_id: {message.chat.id}')
        return True
    except TelegramBadRequest as e:
        error_message = str(e).lower()

        if 'message to delete not found' in error_message:
            logger.info(f'Message {message.message_id} already deleted')
            return True
        elif 'message is not modified' in error_message:
            logger.info(f'Message {message.message_id} has not changes')
            return True
        elif 'reply markup not modified' in error_message:
            try:
                await message.edit_reply_markup(reply_markup=None)
                return True
            except Exception as e:
                logger.info(f'Failed to delete message: {e}')
                return False
        else:
            logger.info(f'Failed to delete message {message.message_id}: {error_message}')
            return False


# Отправка списка мероприятий
async def send_events_list(
    message: Message,
    events: list,
    bot: Bot,
    callback: Optional[CallbackQuery] = None,
) -> None:
    chat_id = message.chat.id
    logger.info(f'chat_id: {chat_id}')

    async def show_typing() -> None:
        await bot.send_chat_action(chat_id=chat_id, action='typing')

    if not events:
        await show_typing()
        await asyncio.sleep(1)
        await message.answer(
            """
⏳ К сожалению, сейчас нет подходящих мероприятий. Мы сообщим, когда появятся новые!

А пока можешь присоединиться к чату @weekender_chat и позвать туда своих друзей 💜
            """
        )
        return

    for event in events:
        await show_typing()
        await asyncio.sleep(1)
        event_message = f'{event.description if event.description else ""}\n\n{event.url}'

        await message.answer(event_message)


# Проверка возраста
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
