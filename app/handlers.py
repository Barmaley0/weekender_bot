import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, MaybeInaccessibleMessage, Message

import app.database.requests as req
import app.keyboards as kb

from app.states import UserData


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


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


async def send_events_list(message: Message, callback: CallbackQuery, events: list, bot: Bot) -> None:
    if callback.message is None:
        return
    chat_id = callback.message.chat.id
    logger.info(f'chat_id: {chat_id}')

    async def show_typing() -> None:
        await bot.send_chat_action(chat_id=chat_id, action='typing')

    if not events:
        await show_typing()
        await asyncio.sleep(1)
        await message.answer('⏳ К сожалению, сейчас нет подходящих мероприятий. Мы сообщим вам, когда появятся новые!')
        return

    for event in events:
        await show_typing()
        await asyncio.sleep(1)
        await message.answer(f'🎉 Вот мероприятие, которое может вам понравиться:\n{event.url}')


@router_user.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is not None:
        await req.set_user(
            message.from_user.id,
            message.from_user.first_name,
            message.from_user.username,
        )
        await message.answer(
            f"""
<b>Привет! {message.from_user.first_name} ты в тёплом месте 🌴🌞</b>
Тут мы помогаем находить события, после которых хочется жить чуть ярче, смеяться чуть громче и обниматься чуть крепче.

Расскажи немного о себе — и я подберу для тебя что-то по вкусу.
От вечеринок до уютных арт-лекций.

В общем, добро пожаловать. Чувствуй себя как дома (но с музыкой получше). 🎧
            """,
            reply_markup=await kb.get_main_kb(),
            parse_mode='html',
        )
    else:
        await message.answer(
            """
<b>Привет! Ты в тёплом месте 🌴🌞</b>
Тут мы помогаем находить события, после которых хочется жить чуть ярче, смеяться чуть громче и обниматься чуть крепче.

Расскажи немного о себе — и я подберу для тебя что-то по вкусу.
От вечеринок до уютных арт-лекций.

В общем, добро пожаловать. Чувствуй себя как дома (но с музыкой получше). 🎧
            """,
            reply_markup=await kb.get_main_kb(),
            parse_mode='html',
        )


@router_user.message(F.text == '🎉 Начнём 🎉')
async def get_year(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.from_user.id is None:
        return
    user_data = await req.get_user_data(message.from_user.id)

    await state.set_data(
        {
            'year': user_data.get('year'),
            'status': user_data.get('status'),
            'district': user_data.get('district'),
            'interests': user_data.get('interests', []),
        }
    )

    await state.set_state(UserData.year)
    await message.answer(
        """
<b>Давай чуть ближе познакомимся.</b>
Сколько тебе лет? Ответь на вопрос сообщением. 
Это нужно, чтобы подкинуть тебе подходящие форматы — у нас для каждого возраста свои точки притяжения.
        """,
        parse_mode='html',
    )
    # await asyncio.sleep(10)
    # await safe_delete_message(bot_message)


@router_user.message(UserData.year)
async def get_status(message: Message, state: FSMContext) -> None:
    if message.text is None or message.text.isalpha():
        await message.answer('❌ Пожалуйста, введите число цифрами')
        # await asyncio.sleep(5)
        # await safe_delete_message(bot_message)
        return

    age = int(message.text)

    if age < 18 or age > 60:
        await message.answer('❌ Пожалуйста, введите возраст от 18 до 60 лет')
        # await asyncio.sleep(5)
        # await safe_delete_message(bot_message)
        return

    await state.update_data(year=age)
    await state.set_state(UserData.status)

    if isinstance(message, Message):
        await message.answer(
            """
<b>Спасибо! Чтобы лучше подобрать для тебя формат, подскажи, пожалуйста:</b>
Какой у тебя семейный статус?
            """,
            reply_markup=await kb.marital_status_kb(state=state),
            parse_mode='html',
        )


@router_user.callback_query(F.data.startswith('status_'))
async def get_district(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    if isinstance(callback.message, Message):
        try:
            status_marital = callback.data.split('_')[1]
            data = await state.get_data()

            current_status = data.get('status')
            new_status = None if current_status == status_marital else status_marital
            await state.update_data(status=new_status)

            await callback.message.edit_reply_markup(reply_markup=await kb.marital_status_kb(state=state))

            await callback.answer(f'Статус: {status_marital if new_status else "сброшен"}')

            # await safe_delete_message(callback.message)

            if new_status:
                await state.set_state(UserData.district)
                await callback.message.answer(
                    """
<b>Отлично! Теперь давай уточним локацию:</b>
В каком округе Москвы ты живешь?
(Выбери из списка или укажи свой)
                    """,
                    reply_markup=await kb.district_kb(state=state),
                    parse_mode='html',
                )
        except Exception as e:
            logger.error(e)
            await callback.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.callback_query(F.data.startswith('district_'))
async def get_interests(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    if isinstance(callback.message, Message):
        try:
            district_name = callback.data.split('_')[1]
            data = await state.get_data()

            current_district = data.get('district')
            new_district = None if current_district == district_name else district_name
            await state.update_data(district=new_district)

            await callback.message.edit_reply_markup(reply_markup=await kb.district_kb(state=state))
            await callback.answer(f'Район: {district_name if new_district else "сброшет"}')

            # await safe_delete_message(callback.message)

            if new_district:
                await state.set_state(UserData.interests)
                await callback.message.answer(
                    """
<b>Почти готово! Последний шаг — расскажи, что тебе интересно.</b>
Выбери от 3 вариантов, которые тебе откликаются:
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

        required_fields = ['year', 'status', 'district']
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
            await req.set_user_data_save(
                tg_id=callback.from_user.id,
                year=data['year'],
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

        # await safe_delete_message(callback.message)

        if isinstance(callback.message, Message):
            message = await callback.message.answer(
                """
<b>Класс, спасибо!</b>
Теперь мы знаем тебя чуть лучше — самое время подобрать что-то подходящее.

Не просто событие, а твоё. Где можно быть собой, встретиться по-настоящему и, возможно, удивиться, как это было нужно.

Готовим подборку. Это займёт какое-то время.
            """,
                parse_mode='html',
            )
            try:
                events = await req.get_event_for_user(data['year'], data['status'])
                logger.info(f'Found events: {events}')
                await send_events_list(message, callback, events, bot)
            except Exception as e:
                logger.error(f'Error in send_events_list: {e}', exc_info=True)
                await callback.answer('❌ Произошла ошибка при отправке событий. Попробуйте ещё раз.')

    except Exception as e:
        logger.error(f'Error in status_save: {e}', exc_info=True)
        await callback.answer('❌ Произошла ошибка. Попробуйте ещё раз.')
    finally:
        await state.clear()


@router_user.message(F.text == 'Меню 🗄️')
async def question(message: Message) -> None:
    await message.answer(
        '<b>➖➖ Меню пользователя ➖➖</b>',
        reply_markup=await kb.get_menu_kb(),
        parse_mode='html',
    )


@router_user.callback_query(F.data.startswith('check_'))
async def show_points_user(callback: CallbackQuery) -> None:
    if callback.data is None:
        await callback.answer('Произошла ошибка.')
        return

    points = await req.get_user_points(callback.from_user.id)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"""
<b>У вас 🔖 {points} баллов!</b>

Посещайте мероприятия, чтобы зарабатывать больше баллов и открывать новые возможности.
Чем активнее вы участвуете, тем больше баллов начисляется на ваш счет.

Вы можете тратить баллы на посещение новых мероприятий. Не упустите шанс увеличить свой баланс.
Следите за обновлениями, чтобы не пропустить выгодные предложения!
            """,
            parse_mode='html',
        )
        await callback.answer()
