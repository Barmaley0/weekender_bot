import asyncio
import logging

from typing import Any, Callable, Optional, Union

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

import src.bot.db.repositories.admin_repository as req_admin


InputMediaType = Union[
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument,
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Проверка пользователя на администратора
class AdminFilter(logging.Filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is not None:
            return await req_admin.is_admin(message.from_user.id)
        return False


async def selection_message_handler(
    callback: CallbackQuery,
    state: FSMContext,
    key: str,
) -> tuple[str, list[str]]:
    """Обработка выбора диапазона возраста, района, пола, статуса"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return '', []

    value = callback.data.split('_')[-1]  # age_range_18-25 -> 18-25, select_district_САО -> САО....
    data = await state.get_data()
    logger.info(f'➡️ Admin age select: {callback.data} current state: {data.get(key, [])}')

    current_ranges = data.get(key, [])
    if isinstance(current_ranges, str):
        current_ranges = [current_ranges] if current_ranges else []

    # Обновляем список выбранных диапазонов
    updated_ranges = (
        [item for item in current_ranges if item != value] if value in current_ranges else [*current_ranges, value]
    )

    if key == 'age_users':
        await state.update_data(age_users=updated_ranges)
        updated_data = await state.get_data()
        logger.info(f'✅ Updated age ranges: {updated_data}')
    elif key == 'district_users':
        await state.update_data(district_users=updated_ranges)
        updated_data = await state.get_data()
        logger.info(f'✅ Updated district ranges: {updated_data}')
    elif key == 'target_users':
        await state.update_data(target_users=updated_ranges)
        updated_data = await state.get_data()
        logger.info(f'✅ Updated status ranges: {updated_data}')
    elif key == 'gender_users':
        await state.update_data(gender_users=updated_ranges)
        updated_data = await state.get_data()
        logger.info(f'✅ Updated gender ranges: {updated_data}')
    else:
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return '', []

    return value, updated_ranges


async def process_single_media(message: Message) -> Optional[dict[str, Any]]:
    """Обработка одиночного медиафайла"""
    if message.photo:
        return {'type': 'photo', 'file_id': message.photo[-1].file_id, 'caption': message.caption}
    elif message.video:
        return {'type': 'video', 'file_id': message.video.file_id, 'caption': message.caption}
    elif message.document:
        return {'type': 'document', 'file_id': message.document.file_id, 'caption': message.caption}
    return None


async def validate_callback(callback: CallbackQuery) -> bool:
    """Проверка валидности callback"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return False
    return True


async def validate_content(text: str, media_list: list, callback: CallbackQuery) -> bool:
    """Проверка наличия контента для рассылки"""
    if not text and not media_list:
        await callback.answer('❌ Нет контента для рассылки!')
        return False
    return True


async def process_mailing(
    users: list[int], text: str, media_list: list, bot: Bot, progress_msg: Message
) -> tuple[int, int]:
    """Обработка рассылки сообщений"""
    success = 0
    errors = 0
    total = len(users)

    for i, tg_id in enumerate(users, 1):
        try:
            if media_list:
                await send_media_message(tg_id, text, media_list, bot, i)
            else:
                await send_text_message(tg_id, text, bot)

            success += 1
            await update_progress(progress_msg, i, total, success, errors)

        except Exception as e:
            errors += 1
            logger.error(f'Ошибка отправки для {tg_id}: {e}')

        await asyncio.sleep(2)  # Задержка перед следующей итерацией

    return success, errors


async def send_media_message(chat_id: int, text: str, media_list: list, bot: Bot, current_index: int) -> None:
    """Отправка медиа-сообщения"""
    if len(media_list) == 1:
        await send_single_media(chat_id, text, media_list[0], bot)
    else:
        await send_media_group(chat_id, text, media_list, bot, current_index)


async def send_single_media(chat_id: int, text: str, media: dict, bot: Bot) -> None:
    """Отправка одиночного медиафайла с явной типизацией"""
    media_types: dict[str, Callable[..., Any]] = {
        'photo': bot.send_photo,
        'video': bot.send_video,
        'document': bot.send_document,
    }

    if media['type'] in media_types:
        send_func = media_types[media['type']]
        media_file = str(media['file_id']) if isinstance(media['file_id'], str) else media['file_id']

        await send_func(
            chat_id=chat_id,
            **{media['type']: media_file},  # photo=file_id или video=file_id и т.д.
            caption=media.get('caption', text) or None,
            parse_mode='HTML',
        )


async def send_media_group(chat_id: int, text: str, media_list: list, bot: Bot, current_index: int) -> None:
    """Отправка группы медиафайлов"""
    media_types = {'photo': InputMediaPhoto, 'video': InputMediaVideo, 'document': InputMediaDocument}

    media_group = [
        media_types[media['type']](
            media=media['file_id'], caption=media.get('caption') if current_index == 0 else None, parse_mode='HTML'
        )
        for media in media_list
        if media['type'] in media_types
    ]

    await bot.send_media_group(chat_id=chat_id, media=media_group)

    if text and not any(m.get('caption') for m in media_list):
        await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')


async def send_text_message(chat_id: int, text: str, bot: Bot) -> None:
    """Отправка текстового сообщения"""
    await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')


async def update_progress(progress_msg: Message, current: int, total: int, success: int, errors: int) -> None:
    """Обновление прогресса рассылки"""
    if current % 10 == 0 or current == total:
        try:
            await progress_msg.edit_text(
                f'⏳ Рассылка... {current}/{total}\n✅ Успешно: {success}\n❌ Ошибок: {errors}'
            )
        except Exception:
            pass


async def send_final_report(message: Message, total: int, success: int, errors: int) -> None:
    """Отправка финального отчета"""
    await message.answer(f'📤 Рассылка завершена\n▪ Всего: {total}\n▪ Успешно: {success}\n▪ Ошибок: {errors}')
