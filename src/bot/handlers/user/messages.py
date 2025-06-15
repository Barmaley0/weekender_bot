import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import src.bot.db.repositories.event_repository as req_event
import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb

from src.bot.fsm.user_states import UserData
from src.bot.utils.helpers import send_events_list


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


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
    user_data = await req_user.get_user_data(message.from_user.id)

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


@router_user.message(F.text == 'Меню 🗄️')
async def question(message: Message) -> None:
    await message.answer(
        '<b>➖➖ Меню пользователя ➖➖</b>',
        reply_markup=await kb.get_menu_kb(),
        parse_mode='html',
    )


@router_user.message(F.text == '🔄️Повторить подборку')
async def repeat_recommendations(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    shown_events = data.get('shown_events', [])  # Список уже показанных ID
    logger.info(f'Shown events: {shown_events}')

    try:
        # Получаем рекомендации, исключая показанные
        events = await req_event.get_recommended_events_new(
            tg_id=message.from_user.id, limit=3, exclude_ids=shown_events
        )

        if not events:
            await message.answer("""
            ✨ Вы уже посмотрели все доступные мероприятия!
        Попробуйте изменить фильтры или загляните позже. ✨
            """)
            return

        # Обновляем список показанных ID
        new_shown_events = shown_events + [event.id for event in events]
        await state.update_data(shown_events=new_shown_events)
        logger.info(f'Updated shown events: {new_shown_events}')

        await send_events_list(message, events, bot)
    except Exception as e:
        logger.error(f'Error in repeat_recommendations: {e}', exc_info=True)
        await message.answer('❌ Произошла ошибка. Попробуйте позже.')
