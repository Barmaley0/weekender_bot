import logging
import os

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from dotenv import load_dotenv

import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb

from src.bot.fsm.user_states import PeopleSearch, UserData
from src.bot.utils.helpers import show_user_profile, start_events_list


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


@router_user.message(F.text.startswith('@'), StateFilter(PeopleSearch.waiting_for_username))
async def get_username(message: Message, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if message.text is None:
        await message.answer('❌ Пожалуйста, введите @username')
        return
    try:
        username = message.text.lstrip('@').strip()
        if not username:
            await message.answer('❌ Пожалуйста, введите @username')
            return

        logger.info(f'Username was entered: {username}')

        user = await req_user.get_user_by_username(username=username)
        if not user:
            await message.answer('❌ Пользователь не найден')
            return

        logger.info(f'Found user: {user}')

        await show_user_profile(message=message, tg_id=user.tg_id, username=user.username)

    except Exception as e:
        logger.error(f'Error in get_username handler: {e}')
        await message.answer('❌ При обработке данных произошла ошибка. Попробуйте ещё раз!')


@router_user.message(F.text == '🎉 Начнём 🎉')
async def get_year(message: Message, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if not message.from_user:
        return

    await start_events_list(user_id=message.from_user.id, message=message, state=state)


@router_user.message(UserData.year)
async def get_status(message: Message, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
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
<b>Выбери свой пол:</b>
            """,
            reply_markup=await kb.gender_kb(state=state),
            parse_mode='html',
        )


@router_user.message(UserData.profession)
async def get_profession(message: Message, state: FSMContext) -> None:
    logger.info(f'Current state: {await state.get_state()}, Data: {await state.get_data()}')
    if message.text is None or message.text.isdigit():
        await message.answer('❌ Пожалуйста, введите текст')
        return

    data = await state.update_data(profession=message.text)
    if not data.get('profession'):
        await message.answer('❌ Пожалуйста, укажите свою профессию', show_alert=True)
        return

    await state.set_state(UserData.about)

    if isinstance(message, Message):
        await message.answer(
            """
Напиши о себе, чем увлекаешься, какие есть хобби и вообще, что любишь делать в свободное время?
            """,
            parse_mode='html',
        )


@router_user.message(UserData.about)
async def get_about(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer('❌ Пожалуйста, введите текст')
        return

    data = await state.update_data(about=message.text)
    if not data.get('about'):
        await message.answer('❌ Пожалуйста, укажите о себе', show_alert=True)
        return

    await state.set_state(UserData.interests)

    if isinstance(message, Message):
        await message.answer(
            """
<b>Теперь укажи интересы:</b>
            """,
            reply_markup=await kb.interests_kb(state=state),
            parse_mode='html',
        )


@router_user.message(F.text == 'Чаты')
async def show_chats(message: Message) -> None:
    await message.answer(
        '<b>➖➖  Меню чатов ➖➖</b>',
        reply_markup=await kb.get_chats_kb(),
        parse_mode='html',
    )


@router_user.message(F.text == 'Мероприятия')
async def show_events(message: Message) -> None:
    await message.answer(
        '<b>➖➖  Меню мероприятий  ➖➖</b>',
        reply_markup=await kb.get_events_kb(),
        parse_mode='html',
    )


@router_user.message(F.text == 'Резиденты')
async def show_residents_menu(message: Message) -> None:
    await message.answer(
        '<b>➖➖  Меню резидентов  ➖➖</b>',
        reply_markup=await kb.get_residents_menu_kb(),
        parse_mode='html',
    )


@router_user.message(F.text == 'Баллы')
async def show_points_user(message: Message) -> None:
    if message.from_user is None:
        await message.answer('Произошла ошибка.')
        return
    points = await req_user.get_user_points(message.from_user.id)

    if isinstance(message, Message):
        await message.answer(
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

    if isinstance(message, Message):
        try:
            await message.answer_photo(
                file_id,
            )

            await message.answer(
                """
    🎯 Механика обмена баллов
1. 1 балл = 1 руб.
2. Баллами можно оплачивать до 50% от стоимости мероприятия;
3. Баллы сгорают через 3 месяца.
                """,
                parse_mode='html',
            )

        except Exception as e:
            logger.error(f'Error in show_points_user: {e}', exc_info=True)
            await message.answer('❌ Произошла ошибка. Попробуйте ещё раз.')
