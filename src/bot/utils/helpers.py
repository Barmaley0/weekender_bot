import asyncio
import logging

from typing import Optional, Union

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    MaybeInaccessibleMessage,
    Message,
)

import src.bot.db.repositories.admin_repository as req_admin
import src.bot.db.repositories.event_repository as req_event
import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb

from src.bot.fsm.user_states import UserData


InputMediaType = Union[
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument,
]


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Проверка пользователя на администратора
class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is not None:
            return await req_admin.is_admin(message.from_user.id)
        return False


# Получаем значение обрабатываем и возвращаем старое и новое значение
async def data_get_update(callback: CallbackQuery, state: FSMContext, key: str) -> tuple[str, Optional[str]] | None:
    if callback.data is None:
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return None

    value = callback.data.split('_')[1]
    data = await state.get_data()

    current_value = data.get(key)
    new_value = None if current_value == value else value

    return value, new_value


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
    callback: CallbackQuery,
    events: list,
    bot: Bot,
) -> None:
    if not callback.message or not isinstance(callback.message, Message):
        logger.error('callback.message is None')
        return

    chat_id = callback.message.chat.id
    logger.info(f'chat_id: {chat_id}')

    async def show_typing() -> None:
        await bot.send_chat_action(chat_id=chat_id, action='typing')

    if not events:
        await show_typing()
        await asyncio.sleep(2)
        await callback.message.answer(
            """
⏳ К сожалению, сейчас нет подходящих мероприятий. Мы сообщим, когда появятся новые!

А пока можешь присоединиться к чату @weekender_chat и позвать туда своих друзей 💜
            """
        )
        await callback.answer()
        return

    for event in events:
        await show_typing()
        await asyncio.sleep(2)
        event_message = f'{event.description if event.description else ""}\n\n{event.url}'

        await callback.message.answer(event_message)


# Проверка возраста
def is_age_in_range(user_age: int, event_age_range: str) -> bool:
    if not event_age_range:
        return False

    try:
        if '-' in event_age_range:
            min_age, max_age = map(int, event_age_range.split('-'))
            return min_age <= user_age <= max_age
        elif event_age_range.endswith('+'):
            return user_age >= int(event_age_range[:-1])
        else:
            return int(event_age_range) == user_age
    except (ValueError, AttributeError):
        logger.error(f'Invalid age range format: {event_age_range}')
        return False


# Общая логика для handlers message и callback_query
async def start_events_list(user_id: int, message: Message, state: FSMContext) -> None:
    if not user_id:
        return

    user_data = await req_event.get_user_data(user_id)

    await state.set_data(
        {
            'year': user_data.get('year'),
            'gender': user_data.get('gender'),
            'status': user_data.get('status'),
            'target': user_data.get('target'),
            'district': user_data.get('district'),
            'profession': user_data.get('profession'),
            'about': user_data.get('about'),
            'interests': user_data.get('interests', []),
            'shown_events': user_data.get('shown_events', []),
        }
    )

    await state.update_data(shown_events=[])
    await state.set_state(UserData.year)
    await message.answer(
        """
<b>А теперь чуть ближе к делу 😉</b>
Сколько тебе лет?
👀 Это нужно, чтобы подобрать тебе события и людей примерно твоего вайба.
        """,
        parse_mode='html',
    )


# Показать профиль с фотографиями
async def show_profile_with_photos(callback: CallbackQuery) -> None:
    """Показать профиль с фотографиями"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        return

    try:
        user_data = await req_user.get_user_data(callback.from_user.id)
        photo_ids = await req_user.get_user_photo(callback.from_user.id)

        if photo_ids:
            media_group: list[InputMediaType] = [InputMediaPhoto(media=photo_id) for photo_id in photo_ids[:10]]
            await callback.message.answer_media_group(media=media_group)
        else:
            await callback.message.answer('Нет фотографий профиля')

        profile_text = f"""
    👤 <b>{user_data.get('first_name', 'не указан')}</b>

🎂 <b>Возраст:</b> {user_data.get('year', 'не указан')}
♂️ <b>Пол:</b> {user_data.get('gender', 'не указан')}
💍 <b>Статус:</b> {user_data.get('status', 'не указан')}(а)
🎯 <b>Цель:</b> {user_data.get('target', 'не указана')}
🏙 <b>Район:</b> {user_data.get('district', 'не указан')}
💼 <b>Профессия:</b> {user_data.get('profession', 'не указана')}
❤️ <b>Интересы:</b> {', '.join(user_data.get('interests', [])) or 'не указаны'}
📄 <b>О себе:</b> {user_data.get('about', 'не указано')}
    """

        await callback.message.answer(profile_text, parse_mode='html')
        await callback.answer()

    except Exception as e:
        logger.error(f'Error in get_profile handler: {e}')
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


async def show_people_results(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает результаты поиска людей"""
    if not callback.from_user or not callback.data or not callback.message or not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    shown_ids = data.get('shown_people_ids', [])
    age_ranges = data.get('age_ranges', [])

    try:
        # Ищем совместимых пользователей
        users = await req_user.find_compatible_users(
            tg_id=callback.from_user.id, age_ranges=age_ranges, limit=7, exclude_ids=shown_ids
        )

        if not users:
            await callback.message.answer('😔 Больше подходящих людей не найдено, попробуй изменить анкету')
            await state.clear()
            await state.update_data(shown_people_ids=[])
            return

        # Показываем каждого пользователя
        for user in users:
            await show_user_profile(callback.message, user.tg_id)

        # Обновляем список показанных ID
        new_shown_ids = shown_ids + [user.tg_id for user in users]
        await state.update_data(shown_people_ids=new_shown_ids)

        await callback.message.answer(
            'Хотите увидеть больше?',
            reply_markup=await kb.show_more_people_kb(),
        )

    except Exception as e:
        logger.error(f'Error in show_people_results: {e}', exc_info=True)
        await callback.message.answer('❌ Ошибка при показе результатов')


async def show_user_profile(message: Message, tg_id: int, username: str | None = None) -> None:
    """Показывает профиль пользователя с фото"""
    if not message or not isinstance(message, Message):
        return

    try:
        # Получаем данные пользователя
        user_data = await req_user.get_user_data(tg_id)
        if not user_data:
            await message.answer('❌ Профиль пользователя не найден')
            return

        # Обработка фотографий
        photo_ids = await req_user.get_user_photo(tg_id)

        try:
            if photo_ids:
                media_group: list[InputMediaType] = [InputMediaPhoto(media=photo_id) for photo_id in photo_ids[:10]]
                await message.answer_media_group(media=media_group)
            else:
                await message.answer('Нет фотографий профиля')
        except Exception as media_error:
            logger.error(f'Failed to send media for user {tg_id}: {media_error}')
            await message.answer('❌ Не удалось загрузить фотографии профиля')

        # Формирование текста профиля с защитой от None
        interests = user_data.get('interests', [])
        if interests is None:  # Дополнительная проверка на None
            interests = []

        profile_text = f"""
    👤 <b>{user_data.get('first_name', 'не указан')}</b>

🎂 <b>Возраст:</b> {user_data.get('year', 'не указан')}
♂️ <b>Пол:</b> {user_data.get('gender', 'не указан')}
💍 <b>Статус:</b> {user_data.get('status', 'не указан')}(а)
🎯 <b>Цель:</b> {user_data.get('target', 'не указана')}
🏙 <b>Район:</b> {user_data.get('district', 'не указан')}
💼 <b>Профессия:</b> {user_data.get('profession', 'не указана')}
❤️ <b>Интересы:</b> {', '.join(user_data.get('interests', [])) or 'не указаны'}
📄 <b>О себе:</b> {user_data.get('about', 'не указано')}
    """

        user_name = user_data.get('username')
        try:
            if user_name:
                await message.answer(
                    profile_text,
                    reply_markup=await kb.send_message_user_kb(tg_id=tg_id, username=user_name),
                    parse_mode='html',
                )
            else:
                await message.answer(
                    profile_text,
                    parse_mode='html',
                )
        except Exception as text_error:
            logger.error(f'Failed to send text for user {tg_id}: {text_error}')
            await message.answer('❌ Не удалось отправить текст профиля')

    except Exception as e:
        logger.error(f'Error showing user profile {tg_id}: {e}')
