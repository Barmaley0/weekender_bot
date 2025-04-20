from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import app.database.requests as req
import app.keyboards as kb

from app.states import DateUser


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


@router_user.callback_query(F.data.startswith("category_"))
async def status_marital(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is not None:
        year_category = callback.data.split("_")[1]
        await state.update_data(year=year_category)
        await state.set_state(DateUser.status)
        await callback.answer("Вы выбрали возрастную категорию")
    else:
        await state.update_data(year=None)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Выберите семейное положение.",
            reply_markup=await kb.marital_status(),
        )


@router_user.callback_query(F.data.startswith("status_"))
async def status_save(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is not None:
        status_marital = callback.data.split("_")[1]
        await state.update_data(status=status_marital)
        data = await state.get_data()
        if data["year"] is not None and data["status"] is not None:
            await req.set_user_data_save(callback.from_user.id, data["year"], data["status"])
            await callback.answer("Фильтр сохранен. Получите подборку мероприятий для вас.")
    else:
        await state.update_data(status=None)
        data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"""Возрастная категория: {data["year"]}
Семейное положение: {data["status"]}
        Создаем подборку......
            """,
        )
    await state.clear()
