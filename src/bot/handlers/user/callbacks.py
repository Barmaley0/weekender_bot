import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import src.bot.db.repositories.event_repository as req_event
import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb

from src.bot.fsm.user_states import PeopleSearch, UserData
from src.bot.utils.helpers import (
    data_get_update,
    refresh_profile_message,
    safe_delete_message,
    send_events_list,
    show_people_results,
    show_profile_with_photos,
    start_events_list,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


# --- Хендлеры для Events ---
@router_user.callback_query(F.data.startswith('events'))
async def repeat_recommendations(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Повторяем список ивентов по фильтрам"""
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    data = await state.get_data()
    shown_events = data.get('shown_events', [])  # Список уже показанных ID
    logger.info(f'Shown events: {shown_events}')

    try:
        # Получаем рекомендации, исключая показанные
        events = await req_event.get_recommended_events_new(
            tg_id=callback.from_user.id, limit=3, exclude_ids=shown_events
        )
        await callback.answer()

        if not events:
            await callback.message.answer(
                """
    ✨ Вы уже посмотрели все доступные мероприятия!
Попробуйте изменить фильтры или загляните позже. ✨
                """
            )
            await callback.answer()
            return

        # Обновляем список показанных ID
        new_shown_events = shown_events + [event.id for event in events]
        await state.update_data(shown_events=new_shown_events)
        logger.info(f'Updated shown events: {new_shown_events}')

        await send_events_list(callback, events, bot)
    except Exception as e:
        logger.error(f'Error in repeat_recommendations: {e}', exc_info=True)
        await callback.answer('❌ Произошла ошибка. Попробуйте позже.')


@router_user.callback_query(F.data == 'edit_events')
async def edit_events(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование интересов для поиска ивентов"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    try:
        user_data = await req_user.get_user_data(callback.from_user.id)
        if not user_data:
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
            return

        await state.set_state(UserData.interests)
        await state.update_data(
            year=user_data.get('year'),
            gender=user_data.get('gender'),
            status=user_data.get('status'),
            target=user_data.get('target'),
            district=user_data.get('district'),
            profession=user_data.get('profession'),
            about=user_data.get('about'),
            interests=user_data.get('interests', []),
            shown_events=user_data.get('shown_events', []),
            edit_mode='only_interests',
        )

        await callback.message.answer(
            'Обновите интересы:',
            reply_markup=await kb.interests_kb(state=state),
        )
        await callback.answer()
    except Exception as e:
        logger.error(f'Error in edit_events: {e}')
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


# TODO: оптимизировать в общую логику toggle_like and toggle_friend
# --- Хендлеры для лайков ---
@router_user.callback_query(F.data.startswith('like_toggle_'))
async def toggle_like(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает нажатие кнопки Лайк для отношений"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    callback_list = callback.data.split('_')
    to_user_id = int(callback_list[-1])
    like_tag = callback_list[0]
    data = await state.get_data()
    liked_ids = data.get('liked_profile_ids', [])
    reciprocated_ids = data.get('reciprocated_profile_ids', [])

    if to_user_id in liked_ids:
        liked_ids.remove(to_user_id)
        if to_user_id in reciprocated_ids:
            reciprocated_ids.remove(to_user_id)
        await callback.answer('Лайк убран')
        await req_user.delete_like_and_friend_from_db(
            from_tg_id=callback.from_user.id,
            to_tg_id=to_user_id,
            action_type=like_tag,
        )
    else:
        liked_ids.append(to_user_id)
        await callback.answer('Лайк поставлен!')
        await req_user.add_like_and_friend_to_db(
            from_tg_id=callback.from_user.id,
            to_tg_id=to_user_id,
            action_type=like_tag,
            state=state,
            bot=bot,
        )

        data = await state.get_data()
        reciprocated_ids = data.get('reciprocated_profile_ids', [])

    await state.update_data({'liked_profile_ids': liked_ids, 'reciprocated_profile_ids': reciprocated_ids})
    await refresh_profile_message(callback=callback, state=state)


@router_user.callback_query(F.data.startswith('friend_toggle_'))
async def toggle_friend(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает нажатие кнопки Лайк для дружбы"""
    if not callback.from_user or not callback.data or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    callback_list = callback.data.split('_')
    to_user_id = int(callback_list[-1])
    friend_tag = callback_list[0]
    data = await state.get_data()
    friend_ids = data.get('friend_profile_ids', [])
    reciprocated_ids = data.get('reciprocated_profile_ids', [])
    logger.info(
        f'*** to_user_id: {to_user_id}, friend_tag: {friend_tag}, callback.from_user.id: {callback.from_user.id}'
    )

    if to_user_id in friend_ids:
        friend_ids.remove(to_user_id)
        if to_user_id in reciprocated_ids:
            reciprocated_ids.remove(to_user_id)
        await callback.answer('Лайк убран')
        await req_user.delete_like_and_friend_from_db(
            from_tg_id=callback.from_user.id,
            to_tg_id=to_user_id,
            action_type=friend_tag,
        )
    else:
        friend_ids.append(to_user_id)
        await callback.answer('Лайк поставлен!')
        await req_user.add_like_and_friend_to_db(
            from_tg_id=callback.from_user.id,
            to_tg_id=to_user_id,
            action_type=friend_tag,
            state=state,
            bot=bot,
        )

    await state.update_data({'friend_profile_ids': friend_ids})
    await refresh_profile_message(callback=callback, state=state)


# --- Хендлеры для профиля ---
@router_user.callback_query(F.data.startswith('profile'))
async def get_profile(callback: CallbackQuery) -> None:
    """Показать профиль с фотографиями"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        return
    await show_profile_with_photos(callback=callback)


@router_user.callback_query(F.data == 'edit_profile')
async def edit_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактировать профиль"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    await callback.answer()
    await start_events_list(
        user_id=callback.from_user.id,
        message=callback.message,
        state=state,
    )


# --- Хендлеры для поиска пользователей ---
@router_user.callback_query(F.data == 'find_user')
async def find_user(callback: CallbackQuery, state: FSMContext) -> None:
    """Поиск пользователя по username"""
    if not callback.from_user or not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    await callback.message.answer(
        'Введите @username пользователя, которого хотите найти:',
    )
    await state.set_state(PeopleSearch.waiting_for_username)
    await callback.answer()


@router_user.callback_query(F.data == 'find_people')
async def find_people(callback: CallbackQuery, state: FSMContext) -> None:
    """Поиск людей по возрасту, полу, дружба/отношения и интересам"""
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    try:
        await req_user.load_user_like_and_friend(callback.from_user.id, state=state)
        data = await state.get_data()
        if 'shown_people_ids' not in data:
            await state.update_data(shown_people_ids=[])
        if 'liked_profile_ids' not in data:
            await state.update_data(liked_profile_ids=[])
        if 'friend_profile_ids' not in data:
            await state.update_data(friend_profile_ids=[])
        if 'reciprocated_profile_ids' not in data:
            await state.update_data(reciprocated_profile_ids=[])

        await state.set_state(PeopleSearch.age_range)
        await callback.message.answer(
            """
Выберите возрастной диапазон:
            """,
            reply_markup=await kb.age_range_kb(state=state),
        )
        await callback.answer()

    except Exception as e:
        logger.error(f'Error in find_people: {e}', exc_info=True)
        await callback.answer('❌ Произошла ошибка. Попробуйте позже.')


@router_user.callback_query(F.data.startswith('age_range_'))
async def get_age_range(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')

    if callback.data is None or callback.message is None:
        await callback.answer('❌ Ошибка: неверные данные')
        return

    try:
        age_range = callback.data.split('_')[-1]  # age_range_18-25 -> 18-25
        data = await state.get_data()
        logger.info(f'Current age ranges: {data.get("age_ranges", [])}')

        current_ranges = data.get('age_ranges', [])
        if isinstance(current_ranges, str):
            current_ranges = [current_ranges] if current_ranges else []

        # Обновляем список выбранных диапазонов
        updated_ranges = (
            [item for item in current_ranges if item != age_range]
            if age_range in current_ranges
            else [*current_ranges, age_range]
        )

        await state.update_data(age_ranges=updated_ranges)
        updated_data = await state.get_data()
        logger.info(f'Updated age ranges: {updated_data}')

        try:
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=await kb.age_range_kb(state=state))
                await callback.answer(f'Диапазон: {age_range if age_range in updated_ranges else "сброшен"}')
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text='Обновите выбор возраста',
                    reply_markup=await kb.age_range_kb(state=state),
                )
        except TelegramBadRequest as e:
            if 'message is not modified' not in str(e):
                logger.error(f'Failed to update message: {e}')
                await callback.answer('❌ Ошибка обновления. Попробуйте ещё раз!', show_alert=True)
    except Exception as e:
        logger.error(f'Error in get_age_range: {e}', exc_info=True)
        await callback.answer('❌ Ошибка выбора возраста. Попробуйте ещё раз!')


@router_user.callback_query(F.data == 'age_done')
async def age_done(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    try:
        data = await state.get_data()
        if not data.get('age_ranges'):
            await callback.answer('❌ Выберите хотя бы один возрастной диапазон!', show_alert=True)
            return

        await state.set_state(PeopleSearch.shown_people_ids)
        await callback.message.answer(
            """
            Подождите, идет поиск...
            """,
        )

        chat_id = callback.message.chat.id

        async def show_typing() -> None:
            await bot.send_chat_action(chat_id=chat_id, action='typing')

        await show_typing()
        await asyncio.sleep(2)

        await show_people_results(callback, state)
        await callback.answer()

    except Exception as e:
        logger.error(f'Error in age_done: {e}', exc_info=True)
        await callback.answer('❌ Произошла ошибка. Попробуйте позже.')


@router_user.callback_query(F.data == 'show_more_people')
async def show_more_people(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Показывает следующую порцию пользователей"""
    if not callback.message:
        await callback.answer('❌ Ошибка: сообщение не найдено')
        return

    try:
        await req_user.load_user_like_and_friend(callback.from_user.id, state=state)
        data = await state.get_data()
        if 'shown_people_ids' not in data:
            await state.update_data(shown_people_ids=[])
        if 'liked_profile_ids' not in data:
            await state.update_data(liked_profile_ids=[])
        if 'friend_profile_ids' not in data:
            await state.update_data(friend_profile_ids=[])
        if 'reciprocated_profile_ids' not in data:
            await state.update_data(reciprocated_profile_ids=[])
        chat_id = callback.message.chat.id

        async def show_typing() -> None:
            await bot.send_chat_action(chat_id=chat_id, action='typing')

        await show_typing()
        await asyncio.sleep(2)
        await show_people_results(callback, state)
        await callback.answer()
    except Exception as e:
        logger.error(f'Error in show_more_people: {e}', exc_info=True)
        await callback.answer('❌ Ошибка при загрузке')


# --- Хендлеры основной анкеты ---
@router_user.callback_query(F.data.startswith('gender_'))
async def get_gender(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if isinstance(callback.message, Message):
        try:
            result = await data_get_update(callback, state, 'gender')

            if result is None:
                return

            gender, new_gender = result

            await state.update_data(gender=new_gender)

            try:
                await callback.message.edit_reply_markup(reply_markup=await kb.gender_kb(state=state))
            except Exception as e:
                logger.error(f'Ошибка обновления кнопки пола: {e}')
                await callback.answer('❌ Ошибка обновленя кнопки.')

            await callback.answer(f'Пол: {gender if new_gender else "сброшен"}')

            if new_gender:
                await state.set_state(UserData.status)
                await callback.message.answer(
                    """
<b>💘 А как у тебя на личном фронте?</b>
Выбери, как тебе ближе:
— В отношениях, мне и так хорошо
— В поиске — открыта/открыт для новых знакомств
                    """,
                    reply_markup=await kb.marital_status_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('status_'))
async def get_district(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if isinstance(callback.message, Message):
        try:
            result = await data_get_update(callback, state, 'status')

            if result is None:
                return

            status_marital, new_status = result

            await state.update_data(status=new_status)

            await callback.message.edit_reply_markup(reply_markup=await kb.marital_status_kb(state=state))

            await callback.answer(f'Статус: {status_marital if new_status else "сброшен"}')

            if new_status:
                await state.set_state(UserData.target)
                await callback.message.answer(
                    """
<b>А что ты хочешь найти с нами?</b>
— Новых друзей 
— Отношения
                    """,
                    reply_markup=await kb.target_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('target_'))
async def get_target(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if isinstance(callback.message, Message):
        try:
            result = await data_get_update(callback, state, 'target')

            if result is None:
                return

            target_name, new_target = result

            await state.update_data(target=new_target)

            await callback.message.edit_reply_markup(reply_markup=await kb.target_kb(state=state))

            await callback.answer(f'Цель: {target_name if new_target else "сброшена"}')

            if new_target:
                await state.set_state(UserData.district)
                await callback.message.answer(
                    """
<b>Отлично! Теперь давай уточним гео:</b>
В каком районе Москвы ты живешь?
                    """,
                    reply_markup=await kb.district_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('district_'))
async def get_interests(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if isinstance(callback.message, Message):
        try:
            result = await data_get_update(callback, state, 'district')

            if result is None:
                return

            district_name, new_district = result

            await state.update_data(district=new_district)

            await callback.message.edit_reply_markup(reply_markup=await kb.district_kb(state=state))

            await callback.answer(f'Район: {district_name if new_district else "сброшет"}')

            if new_district:
                await state.set_state(UserData.profession)
                await callback.message.answer(
                    """
<b>Расскажи, кем ты работаешь?</b>
                    """,
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('interests_') & (F.data != 'interests_done'))
async def get_save(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if callback.data is None or callback.message is None:
        await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')
        return

    try:
        interests = callback.data.split('_')[1]
        data = await state.get_data()
        logger.info(f'Updated district -> interests: {data}')

        current_interests = data.get('interests', [])
        if isinstance(current_interests, str):
            current_interests = [current_interests] if current_interests else []

        updated_interests = (
            [item for item in current_interests if item != interests]
            if interests in current_interests
            else [*current_interests, interests]
        )

        await state.update_data(interests=updated_interests)

        updated_data = await state.get_data()
        logger.info(f'Updated interests: {updated_data}')

        try:
            if isinstance(callback.message, Message):
                await callback.message.edit_reply_markup(reply_markup=await kb.interests_kb(state=state))
                await callback.answer(f'Интерес: {interests if interests in updated_interests else "сброшен"}')
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text='Обновите выбор интересов',
                    reply_markup=await kb.interests_kb(state=state),
                )
        except TelegramBadRequest as e:
            if 'message is not modified' not in str(e):
                logger.error(f'Failed to update message: {e}')
                await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!', show_alert=True)
    except Exception as e:
        logger.error(e)
        await callback.answer('❌ Ошбика выбора интереса. Попробуйте ещё раз!')


@router_user.callback_query(F.data == 'interests_done')
async def save_data(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    try:
        if not callback.message or not isinstance(callback.message, Message):
            logger.error('callback.message is None')
            await callback.answer('❌ Ошибка сообщение не найдено', show_alert=True)
            return

        data = await state.get_data()
        logger.info(f'Current state data: {data}')

        if not data['interests']:
            logger.error('No interests selected')
            await callback.answer('❌ Выберите хотя бы один интерес!', show_alert=True)
            return

        logger.info(f'Saving user data: {data}')

        try:
            if data.get('edit_mode') == 'only_interests':
                await req_user.update_only_interests(
                    tg_id=callback.from_user.id,
                    interests=data['interests'],
                )
                action = 'Интересы обновлены успешно!'
            else:
                await req_user.set_user_data_save(
                    tg_id=callback.from_user.id,
                    year=data['year'],
                    gender=data['gender'],
                    status=data['status'],
                    target=data['target'],
                    district=data['district'],
                    profession=data['profession'],
                    about=data['about'],
                    interests=data['interests'],
                )
                action = 'Спасибо! Теперь точно будет классный мэтч, погнали 💜'
                description = """
Немного о меню:
⭐️ Резиденты — твой профиль и поиск людей
⭐️ Мероприятия — подборка событий под твои интересы
⭐️ Баллы — копи скидки на билеты
⭐️ Чат — онлайн общение и поиск компании
                """

                logger.info('Data saved successfully')
        except Exception as e:
            logger.error(f'Failed to save data: {e}')
            await callback.answer('❌ При сохранении данных произошла ошибка. Попробуйте ещё раз!', show_alert=True)
            return

        is_user_data_exists = await req_user.user_data_exists(callback.from_user.id)
        logger.info(f'Is user data exists: {is_user_data_exists}')

        await safe_delete_message(callback.message)
        await callback.message.answer(
            f'{action} \n{description}',
            reply_markup=await kb.get_main_kb(user_data_exists=is_user_data_exists),
        )

        ia_user_data = await req_user.get_user(callback.from_user.id)
        logger.info(f'IA user data: {ia_user_data}')

    except Exception as e:
        logger.error(f'Error in status_save: {e}', exc_info=True)
        await callback.answer('❌ Произошла ошибка. Попробуйте ещё раз.')
    finally:
        data = await state.get_data()
        shown_events = data.get('shown_events', [])
        await state.clear()
        await state.update_data(shown_events=shown_events)
        logger.info(f'Updated shown events in state save: {shown_events}')
