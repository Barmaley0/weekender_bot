import asyncio
import logging

from typing import Any, Union

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
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
import src.bot.keyboards.builders as kb

from src.bot.db.repositories.admin_repository import is_admin
from src.bot.fsm.admin_states import MassSendMessage
from src.bot.utils.admin_helpers import (
    process_mailing_with_report,
    process_single_media,
    selection_message_handler,
    validate_callback,
    validate_content,
)


InputMediaType = Union[
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    InputMediaDocument,
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_admin = Router()

media_groups: dict[str, dict[str, Any]] = {}


@router_admin.callback_query(F.data == 'mass_send')
async def age_selection_question(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало массовой рассылки и выбор возраста"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    await state.update_data(is_full_mailing=False)
    await state.set_state(MassSendMessage.age_users)
    try:
        await callback.message.answer(
            '<b>Выберите возрастные диапазоны пользователей:</b>',
            reply_markup=await kb.age_select_users_kb(state=state),
            parse_mode='html',
        )
        await callback.answer()
    except Exception as e:
        logger.error(f'❗Error in age_selection_question: {e}', exc_info=True)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data.startswith('select_age'))
async def age_selection_answer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора возраста"""
    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    try:
        age_users, updated_ranges = await selection_message_handler(callback=callback, state=state, key='age_users')
        try:
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=await kb.age_select_users_kb(state=state))
                await callback.answer(f'Диапазон: {age_users if age_users in updated_ranges else "сброшен"}')
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text='Обновите выбор возраста',
                    reply_markup=await kb.age_select_users_kb(state=state),
                )
        except TelegramBadRequest as e:
            if 'message is not modified' not in str(e):
                logger.error(f'Failed to update message: {e}')
                await callback.answer('❌ Ошибка обновления. Попробуйте ещё раз!', show_alert=True)
    except Exception as e:
        logger.error(f'Error in get_age_users: {e}', exc_info=True)
        await callback.answer('❌ Ошибка выбора возраста. Попробуйте ещё раз!')


@router_admin.callback_query(F.data == 'done_age_select')
async def age_select_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик завершения выбора возраста"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    await state.set_state(MassSendMessage.district_users)
    try:
        await callback.message.answer(
            '<b>Выберите районы пользователей:</b>',
            reply_markup=await kb.district_select_users_kb(state=state),
            parse_mode='html',
        )
        await callback.answer()
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data.startswith('select_district'))
async def district_selection_answer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора района"""
    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    try:
        district_users, updated_districts = await selection_message_handler(
            callback=callback, state=state, key='district_users'
        )
        try:
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=await kb.district_select_users_kb(state=state))
                await callback.answer(f'Район: {district_users if district_users in updated_districts else "сброшен"}')
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text='Обновите выбор района',
                    reply_markup=await kb.district_select_users_kb(state=state),
                )
        except TelegramBadRequest as e:
            if 'message is not modified' not in str(e):
                logger.error(f'❗Failed to update message: {e}')
                await callback.answer('❌ Ошибка обновления. Попробуйте ещё раз!', show_alert=True)
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data == 'done_district_select')
async def district_select_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик завершения выбора района"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    await state.set_state(MassSendMessage.target_users)
    try:
        await callback.message.answer(
            '<b>Выберите цель пользователей:</b>',
            reply_markup=await kb.target_select_users_kb(state=state),
            parse_mode='html',
        )
        await callback.answer()
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data.startswith('select_target'))
async def target_selection_answer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора цели"""
    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    try:
        target_users, updated_targets = await selection_message_handler(
            callback=callback, state=state, key='target_users'
        )
        try:
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=await kb.target_select_users_kb(state=state))
                await callback.answer(f'Цель: {target_users if target_users in updated_targets else "сброшена"}')
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text='Обновите выбор цели',
                    reply_markup=await kb.target_select_users_kb(state=state),
                )
        except TelegramBadRequest as e:
            if 'message is not modified' not in str(e):
                logger.error(f'❗Failed to update message: {e}')
                await callback.answer('❌ Ошибка обновления. Попробуйте ещё раз!', show_alert=True)
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data == 'done_target_select')
async def target_select_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик завершения выбора цели"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    await state.set_state(MassSendMessage.gender_users)
    try:
        await callback.message.answer(
            '<b>Введите пол пользователей:</b>',
            reply_markup=await kb.gender_select_users_kb(state=state),
            parse_mode='html',
        )
        await callback.answer()
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data.startswith('select_gender'))
async def gender_selection_answer(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора пола"""
    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    try:
        gender_users, updated_genders = await selection_message_handler(
            callback=callback, state=state, key='gender_users'
        )
        try:
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=await kb.gender_select_users_kb(state=state))
                await callback.answer(f'Пол: {gender_users if gender_users in updated_genders else "сброшен"}')
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text='Обновите выбор пола',
                    reply_markup=await kb.gender_select_users_kb(state=state),
                )
        except TelegramBadRequest as e:
            if 'message is not modified' not in str(e):
                logger.error(f'❗Failed to update message: {e}')
                await callback.answer('❌ Ошибка обновления. Попробуйте ещё раз!', show_alert=True)
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_admin.callback_query(F.data == 'mass_send_all')
async def mass_send_all_flag(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return
    """Установка флага mass_send_all"""
    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    is_full_mailing = await state.update_data(mass_send_all=True)
    logger.info(f'➡️ User {callback.from_user.id} set mass_send_all flag to {is_full_mailing}')

    users = await req_admin.get_all_users_tg_id()
    logger.info(f'➡️ All users: {users}')
    if not users:
        await callback.answer('❌ Нет пользователей для отправки!', show_alert=True)
        return
    await state.update_data(selected_users=users)

    # Просто показываем количество пользователей
    await callback.message.answer(
        f'Всего пользователей: 👥 {len(users)}',
        reply_markup=await kb.add_send_message_kb(),
        parse_mode='html',
    )
    await callback.answer()


@router_admin.callback_query(F.data == 'done_gender_select')
async def gender_select_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик поиска пользователей и вывода их на экран"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    users = await req_admin.get_users_for_mass_send(state=state)
    if not users:
        await callback.answer('❌ Нет пользователей для отправки!', show_alert=True)
        return

    # Разбиваем список пользователей на части по 50
    chunk_size = 50
    user_chunks = [users[i : i + chunk_size] for i in range(0, len(users), chunk_size)]
    users = [user[0] for chunk in user_chunks for user in chunk]
    logger.info(f'✅ Users saved: {users}')
    await state.update_data(selected_users=users)

    # Отправляем первую часть с информацией о количестве пользователей
    first_chunk = user_chunks[0]
    response = [f'{username[1]}' for username in first_chunk]

    await callback.message.answer('Список пользователей для рассылки:\n' + ', '.join(response))
    await callback.answer()

    # Если есть еще части - отправляем их отдельными сообщениями
    for chunk in user_chunks[1:]:
        chunk_message = ', '.join(f'{username[1]}' for username in chunk)
        await callback.message.answer(chunk_message)
        await callback.answer()

    await callback.message.answer(
        f'👥 Найдено {len(users)} пользователей по фильтрам для рассылки\n'
        'Нажмите кнопку чтобы написать сообщение для рассылки:',
        reply_markup=await kb.add_send_message_kb(),
    )


@router_admin.callback_query(F.data.in_(['cancel_message', 'cancel_mailing']))
async def cancel_message_send(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик отмены рассылки"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        'Отменено ❌',
    )
    await callback.answer()


@router_admin.callback_query(F.data.in_(['add_message', 'edit_mailing']))
async def add_message_send_mass(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик добавления сообщения для рассылки и редактирования рассылки"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    data = await state.get_data()
    selected_users = data.get('selected_users', [])
    is_full_mailing = data.get('is_full_mailing')

    await state.clear()

    if selected_users:
        await state.update_data(selected_users=selected_users)
        await state.update_data(is_full_mailing=is_full_mailing)

    await state.set_state(MassSendMessage.message_text)
    await callback.message.answer(
        """
        <b>Введите медиаданные и/или текст:</b>
Когда соберете рассылку нажмите кнопку <b>Готово</b>
        """,
        parse_mode='html',
    )
    await callback.answer()


@router_admin.message(MassSendMessage.message_text)
async def process_message_text(message: Message, state: FSMContext) -> None:
    """Обработчик текста сообщения"""
    if not message.from_user or not message.text:
        return

    if not await is_admin(message.from_user.id):
        await message.answer('❌ Недостаточно прав!', show_alert=True)
        return

    text_data = await state.update_data(message_text=message.text)
    logger.info(f'✅ Updated message content: {text_data}')
    await state.set_state(MassSendMessage.media_upload)
    await message.answer(
        'Текст сохранен. Добавьте медиафайлы для рассылки или нажмите кнопку Готово.',
        reply_markup=await kb.done_mailing_kb(),
        parse_mode='html',
    )


@router_admin.message(MassSendMessage.media_upload, F.media_group_id)
async def process_media_group(message: Message, state: FSMContext) -> None:
    """Обработчик загрузки медиафайлов"""
    if not message.from_user or not message.media_group_id:
        return

    if not await is_admin(message.from_user.id):
        await message.answer('❌ Недостаточно прав!', show_alert=True)
        return

    group_id = message.media_group_id
    current_msg_id = message.message_id

    # Инициализация данных группы
    if group_id not in media_groups:
        media_groups[group_id] = {'max_message_id': current_msg_id, 'media_count': 0, 'notified': False}

    # Обновляем максимальный message_id
    if current_msg_id > media_groups[group_id]['max_message_id']:
        media_groups[group_id]['max_message_id'] = current_msg_id

    # Обработка медиа
    media = await process_single_media(message)
    if not media:
        return

    # Обновляем состояние
    data = await state.get_data()
    media_list = data.get('media_upload', [])
    media_list.append(media)
    await state.update_data(media_upload=media_list)

    media_groups[group_id]['media_count'] += 1

    # Если это сообщение с максимальным ID - оно последнее в группе
    if current_msg_id == media_groups[group_id]['max_message_id']:
        await asyncio.sleep(1)

        # Двойная проверка, что message_id не изменился
        if current_msg_id == media_groups[group_id]['max_message_id']:
            await message.answer(
                f'Медиагруппа из {media_groups[group_id]["media_count"]} файлов сохранено 💾',
                reply_markup=await kb.done_mailing_kb(),
                parse_mode='html',
            )
            media_groups[group_id]['notified'] = True
            # Очищаем данные группы через 5 минут
            asyncio.create_task(clean_media_group(group_id, delay=300))


async def clean_media_group(group_id: str, delay: int = 300) -> None:
    await asyncio.sleep(delay)
    if group_id in media_groups:
        del media_groups[group_id]


@router_admin.message(MassSendMessage.media_upload, F.photo | F.video | F.document)
async def process_single_media_upload(message: Message, state: FSMContext) -> None:
    """Обработчик загрузки одного медиафайла"""
    if not message.from_user or not message.text:
        return

    if not await is_admin(message.from_user.id):
        await message.answer('❌ Недостаточно прав!', show_alert=True)
        return

    data = await state.get_data()
    media_list: list[dict[str, Any]] = data.get('media_upload', [])

    media = await process_single_media(message)
    if media:
        media_list.append(media)
        media_list_data = await state.update_data(media_upload=media_list)
        logger.info(f'✅ Updated media list single file: {media_list_data}')
        await asyncio.sleep(1)
        await message.answer(
            f'Медиафайл добавлен. Всего: {len(media_list)}',
            reply_markup=await kb.done_mailing_kb(),
            parse_mode='html',
        )


@router_admin.callback_query(MassSendMessage.media_upload, F.data == 'done_mailing')
async def finish_media_upload(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик окончания загрузки медиафайлов"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    data = await state.get_data()
    media_list = data.get('media_upload', [])
    text = data.get('message_text')
    logger.info(f'➡️ Finish media upload: text: {text}, media_list: {media_list}')

    if not text and not media_list:
        await callback.message.answer(
            'Вы не добавили ни текста, ни медиафайлов. Пожалуйста, добавьте что-то для рассылки.'
        )
        await callback.answer()
        return

    # Отправляем превью
    if media_list:
        # Если медиа один - отправляем как одиночный файл
        if len(media_list) == 1:
            media = media_list[0]
            if media['type'] == 'photo':
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=media['file_id'],
                    caption=media.get('caption', ''),
                    parse_mode='HTML',
                )
            elif media['type'] == 'video':
                await bot.send_video(
                    chat_id=callback.message.chat.id,
                    video=media['file_id'],
                    caption=media.get('caption', ''),
                    parse_mode='HTML',
                )
            elif media['type'] == 'document':
                await bot.send_document(
                    chat_id=callback.message.chat.id,
                    document=media['file_id'],
                    caption=media.get('caption', ''),
                    parse_mode='HTML',
                )
        else:
            # Если медиа несколько - отправляем как альбом
            media_group: list[InputMediaType] = []
            for media in media_list:
                if media['type'] == 'photo':
                    media_group.append(
                        InputMediaPhoto(media=media['file_id'], caption=media.get('caption', ''), parse_mode='HTML')
                    )
                elif media['type'] == 'video':
                    media_group.append(
                        InputMediaVideo(media=media['file_id'], caption=media.get('caption', ''), parse_mode='HTML')
                    )
                elif media['type'] == 'document':
                    media_group.append(
                        InputMediaDocument(media=media['file_id'], caption=media.get('caption', ''), parse_mode='HTML')
                    )

            await bot.send_media_group(chat_id=callback.message.chat.id, media=media_group)

    if text:
        await callback.message.answer(f'{text}', parse_mode='HTML')

    await callback.message.answer('Превью рассылки:', reply_markup=await kb.start_mailing_kb())
    await callback.answer()

    await state.set_state(MassSendMessage.preview)


@router_admin.callback_query(F.data == 'start_mailing')
async def start_mailing(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик начала массовой рассылки"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    if not await is_admin(callback.from_user.id):
        await callback.answer('❌ Недостаточно прав!', show_alert=True)
        return

    if not await validate_callback(callback):
        return

    try:
        await callback.answer('⏳ Рассылка началась', show_alert=True)

        data = await state.get_data()
        users = data.get('selected_users', [])
        text: Any = data.get('message_text')
        media_list = data.get('media_upload', [])
        logger.info(f'*** ➡️ Start mailing: users: {users}, text: {text}, media_list: {media_list}')

        if not await validate_content(text, media_list, callback):
            return

        total = len(users)
        progress_msg = await callback.message.answer(f'⏳ Начало рассылки... 0/{total}')

        asyncio.create_task(process_mailing_with_report(users, text, media_list, bot, progress_msg, callback.message))

    except Exception as e:
        logger.error(f'❗️Error in start_mailing: {e}')
        await callback.message.answer('❌ Произошла ошибка при рассылке')
    finally:
        await state.clear()
        await callback.answer()
