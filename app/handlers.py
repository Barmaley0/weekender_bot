from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

import app.keyboards as kb
import app.database.requests as req
from app.states import DateUser
from aiogram.fsm.context import FSMContext


router_user = Router()


@router_user.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is not None:
        await req.set_user(message.from_user.id, message.from_user.first_name, message.from_user.username)
        await message.answer(
            f"Привет! {message.from_user.first_name}",
            reply_markup=kb.main,
        )
    else:
        await message.answer("Привет!")


@router_user.message(F.text == "🎉Подобрать мероприятие🎉")
async def years_category(message: Message, state: FSMContext) -> None:
    await state.set_state(DateUser.year)
    await message.answer(
        "Введите данные для поиска мероприятия. Выберите возрастную категорию.",
        reply_markup=await kb.categories_years(),
    )


@router_user.callback_query(F.data.startswith('category_'))
async def status_marital(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(year=callback.data)
    await state.set_state(DateUser.status)
    await callback.answer("Вы выбрали возрастную категорию")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Выберите семейное положение.",
            reply_markup=await kb.marital_status(),
        )


@router_user.callback_query(DateUser.status)
async def status_save(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(status=callback.data)
    data = await state.get_data()
    await callback.answer('Фильтр сохранен. Получите подборку мероприятий для вас.')
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f'Возрастная категория: {data["year"]}\nСемейное положение: {data["status"]}',
        )
    await state.clear()
