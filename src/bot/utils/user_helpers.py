import asyncio
import logging

from typing import Optional, Union

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    MaybeInaccessibleMessage,
    Message,
    ReplyKeyboardMarkup,
)

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
        await send_user_profile(callback, callback.from_user.id)
        await callback.answer()

    except Exception as e:
        logger.error(f'Error in get_profile handler: {e}')
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


# Показать результаты поиска пользователей с фотографиями и без.
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
            # Очищаем состояние
            await state.clear()
            await state.update_data(shown_people_ids=[])
            return

        # Показываем каждого пользователя
        for user in users:
            await show_user_profile(callback.message, user.tg_id, state=state)

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


# Показать свой профиль
async def show_user_profile(message: Message, tg_id: int, state: FSMContext, username: str | None = None) -> None:
    """Показывает профиль пользователя с фото"""
    if not message or not isinstance(message, Message):
        return

    try:
        await send_user_profile(message, tg_id, state=state)
    except Exception as e:
        logger.error(f'Error showing user profile {tg_id}: {e}')


# Обновить сообщение профиля
async def refresh_profile_message(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        return

    target_id = int(callback.data.split('_')[-1])
    user_data = await req_user.get_user_data(target_id)

    current_markup = callback.message.reply_markup

    new_markup = await kb.send_message_user_and_like_kb(
        tg_id=target_id,
        username=user_data.get('username'),
        state=state,
        target=user_data.get('target'),
    )

    if str(current_markup) != str(new_markup):
        try:
            await callback.message.edit_reply_markup(reply_markup=new_markup)
        except Exception as e:
            logger.error(f'Error in refresh_profile_message: {e}')
    else:
        logger.info('No need to refresh profile message')


# Отправить уведомление о взаимном лайке
async def send_match_notification(
    bot: Bot,
    recipient_tg_id: int,
    matched_user_tg_id: int,
    state: FSMContext,
    target: str,
) -> None:
    try:
        # Отправляем уведомление о взаимном лайке
        if target == 'like':
            match_title = '💖 Это взаимно! Вы понравились этому пользователю'
        elif target == 'friend':
            match_title = '🙂 Это взаимно! С вами хотят дружить'

        await bot.send_message(chat_id=recipient_tg_id, text=match_title)

        await send_user_profile(recipient_tg_id, matched_user_tg_id, bot=bot, state=state)

    except Exception as e:
        logger.error(f'Failed to send match notification: {e}')


async def get_user_profile_data(user_id: int) -> tuple[list[str] | None, str] | tuple[None, None]:
    """
    Получает данные профиля пользователя
    Возвращает tuple: (список photo_ids, текст профиля) или (None, None) если пользователь не найден
    """
    user_data = await req_user.get_user_data(user_id)

    if not user_data:
        return None, None

    photo_ids = await req_user.get_user_photo(user_id)

    interests = user_data.get('interests', []) or []

    profile_text = f"""
👤 <b>{user_data.get('first_name', 'не указан')}</b>

❤️ <b>Лайков:</b> {user_data.get('total_likes', '_')}

🎂 <b>Возраст:</b> {user_data.get('year', 'не указан')}
♂️ <b>Пол:</b> {user_data.get('gender', 'не указан')}
💍 <b>Статус:</b> {user_data.get('status', 'не указан')}{'(а)' if user_data.get('status') == 'Свободен' else ''}
🎯 <b>Цель:</b> {user_data.get('target', 'не указана')}
🏙 <b>Район:</b> {user_data.get('district', 'не указан')}
🎮 <b>Интересы:</b> {', '.join(interests) or 'не указаны'}
💼 <b>Профессия:</b> {user_data.get('profession', 'не указана')}
📄 <b>О себе:</b> {user_data.get('about', 'не указано')}
    """
    return photo_ids, profile_text


# Отправить профиль
async def send_user_profile(
    recipient: Union[Message, CallbackQuery, int],
    user_id: int,
    bot: Optional[Bot] = None,
    state: Optional[FSMContext] = None,
) -> bool:
    """
    Отправляет профиль пользователя
    Возвращает True если успешно, False если ошибка
    """
    try:
        photo_ids, profile_text = await get_user_profile_data(user_id)
        if profile_text is None:
            await _send_error(recipient, '❌ Профиль пользователя не найден', bot)
            return False

        # Отправка медиа
        if photo_ids:
            media_group: list[InputMediaType] = [InputMediaPhoto(media=pid) for pid in photo_ids[:10]]
            await _send_media(media_group, recipient, bot)
        else:
            await _send_message('Нет фотографий профиля', recipient, bot)

        # Отправка текста профиля
        user_data = await req_user.get_user_data(user_id)
        reply_markup = (
            await kb.send_message_user_and_like_kb(
                tg_id=user_id,
                username=user_data.get('username'),
                state=state,
                target=user_data.get('target'),
            )
            if state
            else None
        )

        await _send_message(profile_text, recipient, bot, reply_markup)
        return True

    except Exception as e:
        logger.error(f'Error showing user profile {user_id}: {e}')
        await _send_error(recipient, '❌ Не удалось загрузить профиль', bot)
        return False


#  --- Вспомогательные функции системы лайков ---
async def _send_media(
    media: list[InputMediaType],
    recipient: Union[Message, CallbackQuery, int],
    bot: Optional[Bot] = None,
) -> None:
    try:
        if isinstance(recipient, Message):
            await recipient.answer_media_group(media=media)
        elif isinstance(recipient, CallbackQuery):
            if recipient.message and isinstance(recipient.message, Message):
                await recipient.message.answer_media_group(media=media)
            else:
                if not bot:
                    raise ValueError('Bot instance is required when recipient.message is not available')
                await bot.send_media_group(chat_id=recipient.from_user.id, media=media)
        elif isinstance(recipient, int) and bot:
            await bot.send_media_group(chat_id=recipient, media=media)
        else:
            raise ValueError('Invalid recipient type or missing bot instance')
    except Exception as e:
        logger.error(f'Failed to send media: {e}')
        raise


async def _send_message(
    text: str,
    recipient: Union[Message, CallbackQuery, int],
    bot: Optional[Bot],
    reply_markup: Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]] = None,
) -> None:
    if isinstance(recipient, Message):
        await recipient.answer(
            text,
            reply_markup=reply_markup,
            parse_mode='html',
        )
    elif isinstance(recipient, CallbackQuery):
        if recipient.message is not None and isinstance(recipient.message, Message):
            await recipient.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode='html',
            )
        elif bot:
            await bot.send_message(
                chat_id=recipient.from_user.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='html',
            )
    elif bot and isinstance(recipient, int):
        await bot.send_message(
            chat_id=recipient,
            text=text,
            reply_markup=reply_markup,
            parse_mode='html',
        )


async def _send_error(recipient: Union[Message, CallbackQuery, int], text: str, bot: Optional[Bot]) -> None:
    await _send_message(text, recipient, bot)
