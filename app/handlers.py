import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, MaybeInaccessibleMessage, Message

import app.database.requests as req
import app.keyboards as kb

from app.states import DateUser


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


async def safe_delete_message(message: MaybeInaccessibleMessage) -> bool:
    if not isinstance(message, Message):
        return False
    try:
        await message.delete()
        return True
    except TelegramBadRequest as e:
        if 'message to delete not found' not in str(e):
            try:
                await message.edit_reply_markup(reply_markup=None)
                return True
            except TelegramBadRequest:
                logger.error('Cloud not remove reply markup')
        return False
    except Exception as e:
        logger.error(f'Unexpected error deleting message: {e}')
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
            reply_markup=await kb.get_main_keyboard(),
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
            reply_markup=await kb.get_main_keyboard(),
            parse_mode='html',
        )


@router_user.message(F.text == '🎉 Начнём 🎉')
async def years_category(message: Message, state: FSMContext) -> None:
    await state.set_state(DateUser.year)
    await message.answer(
        """
<b>Давай чуть ближе познакомимся</b>
Сколько тебе лет? 
Это нужно, чтобы подкинуть тебе подходящие форматы — у нас для каждого возраста свои точки притяжения.
        """,
        reply_markup=await kb.categories_years(),
        parse_mode='html',
    )


@router_user.callback_query(F.data.startswith('category_'))
async def status_marital(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        return

    year_category = callback.data.split('_')[1]
    await state.update_data(year=year_category)
    await state.set_state(DateUser.status)
    await callback.answer('Вы выбрали возрастную категорию')

    await safe_delete_message(callback.message)

    if isinstance(callback.message, Message):
        await callback.message.answer(
            """
<b>Спасибо! Чтобы лучше подобрать для тебя формат, подскажи, пожалуйста:</b>
Какой у тебя семейный статус?
            """,
            reply_markup=await kb.marital_status(),
            parse_mode='html',
        )


@router_user.callback_query(F.data.startswith('status_'))
async def status_save(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if callback.data is None or callback.message is None:
        return

    try:
        status_marital = callback.data.split('_')[1]
        await state.update_data(status=status_marital)
        data = await state.get_data()

        if data['year'] is not None and data['status'] is not None:
            await req.set_user_data_save(callback.from_user.id, data['year'], data['status'])
            await callback.answer('Фильтр сохранен. Получите подборку мероприятий для вас.')

        await safe_delete_message(callback.message)

        if isinstance(callback.message, Message):
            await callback.message.answer(
                """
<b>Класс, спасибо!</b>
Теперь мы знаем тебя чуть лучше — самое время подобрать что-то подходящее.

Не просто событие, а твоё. Где можно быть собой, встретиться по-настоящему и, возможно, удивиться, как это было нужно.

Готовим подборку. Это займёт какое-то время.
            """,
                parse_mode='html',
            )
            events = await req.get_event_for_user(data['year'], data['status'])
            logger.info(f'Found events: {events}')
            await send_events_list(callback.message, callback, events, bot)
    except Exception as e:
        logger.error(f'Error in status_save: {e}')
        await callback.answer('Произошла ошибка. Попробуйте ещё раз.')
    finally:
        await state.clear()


@router_user.message(F.text == 'Меню 🗄️')
async def question(message: Message) -> None:
    await message.answer(
        '<b>➖➖ Меню пользователя ➖➖</b>',
        reply_markup=await kb.get_menu_keyboars(),
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
