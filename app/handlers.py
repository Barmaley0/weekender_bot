import asyncio
import logging

from typing import Optional

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


@router_user.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user:
        await req.set_user(
            message.from_user.id,
            message.from_user.first_name,
            message.from_user.username,
        )

        try:
            is_user_data = await req.user_data_exists(message.from_user.id)

            await message.answer(
                f"""
<b>Привет, {f'{message.from_user.first_name}' if message.from_user.first_name else ''}! Ты в тёплом месте 🌴</b>
Тут мы помогаем находить события, после которых хочется жить чуть ярче, смеяться чуть громче и обниматься чуть крепче.

От вечеринок до уютных арт-лекций — расскажи немного о себе и я подберу тебе что-то по вкусу.

🎁 Чем активнее ты — тем больше баллов получаешь. Потом можешь использовать их, чтобы получить скидку, апнуться до уровня "Гуру вайба" или даже стать нашим амбассадором и получать приятные бонусы.

💜 А ещё у нас есть чат @weekender_chat, где можно найти друзей, договориться пойти вместе на событие и просто быть собой. Потому что в компании — всегда легче дышится. Подпишись на чат и получи приветственные 100 баллов.

Чувствуй себя как дома. Здесь тебя ждут.
            """,
                reply_markup=await kb.get_main_kb(user_data_exists=is_user_data),
                parse_mode='html',
            )
        except Exception as e:
            logger.error(f'Errof checking user data: {e}')


@router_user.message(F.photo)
async def photo(message: Message) -> None:
    try:
        if not message.photo:
            await message.answer('❌ фото не обнаружено!')
            return
        file_id_s = message.photo[-1].file_id
        await message.answer_photo(
            file_id_s,
            caption='Вот твоя фотка',
        )
        await message.answer(f'id фотки: {file_id_s}')
    except Exception as e:
        logger.error(f'Error in photo handler: {e}')
        await message.answer('❌ При обработке фото произошла ошибка. Попробуйте ещё раз!')


@router_user.message(F.text.in_(['🎉 Начнём 🎉', '🔀Изменить подборку']))
async def get_year(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.from_user.id is None:
        return
    user_data = await req.get_user_data(message.from_user.id)

    await state.set_data(
        {
            'year': user_data.get('year'),
            'gender': user_data.get('gender'),
            'status': user_data.get('status'),
            'district': user_data.get('district'),
            'interests': user_data.get('interests', []),
            'shown_events': user_data.get('shown_events', []),
        }
    )

    await state.update_data(shown_events=[])
    await state.set_state(UserData.year)
    await message.answer(
        """
<b>Давай чуть ближе познакомимся.</b>
Сколько тебе лет? 
Это нужно, чтобы подкинуть тебе подходящие форматы.
        """,
        parse_mode='html',
    )


@router_user.message(UserData.year)
async def get_status(message: Message, state: FSMContext) -> None:
    if message.text is None or message.text.isalpha():
        await message.answer('❌ Пожалуйста, введите число цифрами')
        return

    if not message.text.isdigit() and not message.text.isnumeric():
        await message.answer('❌ Пожалуйста, введите число цифрами')
        return

    age = int(message.text)

    if age < 18 or age > 60:
        await message.answer('❌ Пожалуйста, введите возраст от 18 до 60 лет')
        return

    data = await state.update_data(year=age)
    if not data.get('year'):
        await message.answer('❌ Пожалуйста, укажите свой возраст', show_alert=True)
        return
    await state.set_state(UserData.gender)

    if isinstance(message, Message):
        await message.answer(
            """
<b>Теперь укажи пол:</b>
            """,
            reply_markup=await kb.gender_kb(state=state),
            parse_mode='html',
        )


@router_user.callback_query(F.data.startswith('gender_'))
async def get_gender(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    if isinstance(callback.message, Message):
        try:
            gender = callback.data.split('_')[1]
            data = await state.get_data()

            current_gender = data.get('gender')
            new_gender = None if current_gender == gender else gender
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
            await req.set_user_data_save(
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

        ia_user_data = await req.get_user(callback.from_user.id)
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
                user = await req.get_user(callback.from_user.id)
                if not user:
                    raise ValueError('User not found')

                events = await req.get_recommended_events(tg_id=callback.from_user.id, limit=3)
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
Твой баланс: {points} баллов! 🎉

Каждый балл — это сэкономленные деньги! Копи больше и оплачивай до 50% стоимости любого билета в Weekender.

Совет: активничай в чате @weekender_chat, зови друзей и делись впечатлениями — баллы сами прибегут к тебе! 🚀

Для конвертации баллов напиши нам в поддержку @weekender_main
            """
        )

    # file_id_local = 'AgACAgIAAxkBAAINjmgvg4lmVL30AQoeuUUxbCOwJDXzAAKm8DEbEbh4SdXXtBL6heUeAQADAgADeQADNgQ'
    file_id = 'AgACAgIAAxkBAAIEvWg28Q7DqYKRGRYI3lJLei_8NnXvAAKN8zEb2I25SZGgKqeEEXsZAQADAgADeQADNgQ'

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


@router_user.message(F.text == '🔄️Повторить подборку')
async def repeat_recommendations(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    shown_events = data.get('shown_events', [])  # Список уже показанных ID

    try:
        # Получаем рекомендации, исключая показанные
        events = await req.get_recommended_events_new(tg_id=message.from_user.id, limit=3, exclude_ids=shown_events)

        if not events:
            await message.answer("""
            ✨ Вы уже посмотрели все доступные мероприятия!
    Попробуйте изменить фильтры или загляните позже🕑. ✨
            """)
            return

        # Обновляем список показанных ID
        new_shown_events = shown_events + [event.id for event in events]
        await state.update_data(shown_events=new_shown_events)

        await send_events_list(message, events, bot)
    except Exception as e:
        logger.error(f'Error in repeat_recommendations: {e}', exc_info=True)
        await message.answer('❌ Произошла ошибка. Попробуйте позже.')
