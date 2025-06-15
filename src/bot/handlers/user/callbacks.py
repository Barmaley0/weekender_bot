import logging
import os

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv

import src.bot.db.repositories.event_repository as req_event
import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb

from src.bot.fsm.user_states import UserData
from src.bot.utils.helpers import data_get_update, send_events_list


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


@router_user.callback_query(F.data.startswith('gender_'))
async def get_gender(callback: CallbackQuery, state: FSMContext) -> None:
    if isinstance(callback.message, Message):
        try:
            result = await data_get_update(callback, state, 'gender')

            if result is None:
                return

            gender, new_gender = result

            await state.update_data(gender=new_gender)

            await callback.message.edit_reply_markup(reply_markup=await kb.gender_kb(state=state))

            await callback.answer(f'Пол: {gender if new_gender else "сброшен"}')

            if new_gender:
                await state.set_state(UserData.status)
                await callback.message.answer(
                    """
<b>Спасибо! Чтобы лучше подобрать для тебя формат, подскажи:</b>
Какой у тебя семейный статус?
                    """,
                    reply_markup=await kb.marital_status_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('status_'))
async def get_district(callback: CallbackQuery, state: FSMContext) -> None:
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
                await state.set_state(UserData.district)
                await callback.message.answer(
                    """
<b>Отлично! Теперь давай уточним локацию:</b>
В каком округе Москвы ты живешь?
                    """,
                    reply_markup=await kb.district_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('district_'))
async def get_interests(callback: CallbackQuery, state: FSMContext) -> None:
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
                await state.set_state(UserData.interests)
                await callback.message.answer(
                    """
<b>Последний шаг — расскажи, что тебе интересно.</b>
Выбери от 3 вариантов, которые откликаются:
                    """,
                    reply_markup=await kb.interests_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('interests_') & (F.data != 'interests_done'))
async def get_save(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
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
    try:
        if not callback.message:
            logger.error('callback.message is None')
            await callback.answer('❌ Ошибка сообщение не найдено', show_alert=True)
            return

        data = await state.get_data()
        logger.info(f'Current state data: {data}')

        required_fields = ['year', 'gender', 'status', 'district']
        if not all(field in data for field in required_fields):
            logger.error(f'Missing required fields: {required_fields}')
            await callback.answer('❌ Нажмите снова кнопку\n\t"🎉 Начнём 🎉"!', show_alert=True)
            return

        if not data['interests']:
            logger.error('No interests selected')
            await callback.answer('❌ Выберите хотя бы один интерес!', show_alert=True)
            return

        logger.info(f'Saving user data: {data}')

        try:
            await req_user.set_user_data_save(
                tg_id=callback.from_user.id,
                year=data['year'],
                gender=data['gender'],
                status=data['status'],
                district=data['district'],
                interests=data['interests'],
            )
            logger.info('Data saved successfully')
        except Exception as e:
            logger.error(f'Failed to save data: {e}')
            await callback.answer('❌ При сохранении данных произошла ошибка. Попробуйте ещё раз!', show_alert=True)
            return

        await callback.answer('✅ Фильтр сохранен')

        ia_user_data = await req_user.get_user(callback.from_user.id)
        logger.info(f'IA user data: {ia_user_data}')

        if isinstance(callback.message, Message):
            message = await callback.message.answer(
                """
<b>Класс, спасибо!</b>
Теперь мы знаем тебя чуть лучше — самое время подобрать что-то подходящее.

Готовим подборку. Это займёт какое-то время.
            """,
                reply_markup=await kb.get_main_kb(user_data_exists=True),
                parse_mode='html',
            )
            try:
                user = await req_user.get_user(callback.from_user.id)
                if not user:
                    raise ValueError('User not found')

                events = await req_event.get_recommended_events(tg_id=callback.from_user.id, limit=3)
                logger.info(f'Found events: {events}')

                new_shown_events = [event.id for event in events]
                await state.update_data(shown_events=new_shown_events)

                await send_events_list(message, events, bot, callback)
            except Exception as e:
                logger.error(f'Error in send_events_list: {e}', exc_info=True)
                await callback.answer('❌ Произошла ошибка при отправке событий. Попробуйте ещё раз.')

    except Exception as e:
        logger.error(f'Error in status_save: {e}', exc_info=True)
        await callback.answer('❌ Произошла ошибка. Попробуйте ещё раз.')
    finally:
        data = await state.get_data()
        shown_events = data.get('shown_events', [])
        await state.clear()
        await state.update_data(shown_events=shown_events)
        logger.info(f'Updated shown events in state save: {shown_events}')


@router_user.callback_query(F.data.startswith('check_'))
async def show_points_user(callback: CallbackQuery) -> None:
    if callback.data is None:
        await callback.answer('Произошла ошибка.')
        return
    points = await req_user.get_user_points(callback.from_user.id)

    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"""
Твой баланс: {points} баллов! 🎉

Каждый балл — это сэкономленные деньги! Копи больше и оплачивай до 50% стоимости любого билета в Weekender.

Совет: активничай в чате @weekender_chat, зови друзей и делись впечатлениями — баллы сами прибегут к тебе! 🚀

Для конвертации баллов напиши нам в поддержку @weekender_main
            """
        )

    load_dotenv()
    file_id = os.getenv('POINTS_IMAGE_ID')
    if file_id is None:
        raise ValueError('error file_id')

    if isinstance(callback.message, Message):
        try:
            await callback.message.answer_photo(
                file_id,
            )

            await callback.message.answer(
                """
    🎯 Механика обмена баллов
1. 1 балл = 1 руб.
2. Баллами можно оплачивать до 50% от стоимости мероприятия;
3. Баллы сгорают через 3 месяца.
                """,
                parse_mode='html',
            )
            await callback.answer()

        except Exception as e:
            logger.error(f'Error in show_points_user: {e}', exc_info=True)
            await callback.answer('❌ Произошла ошибка. Попробуйте ещё раз.')
