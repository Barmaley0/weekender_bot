from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

import app.keyboards as kb
import app.database.requests as req


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
async def years_category(message: Message) -> None:
    await message.answer(
        "Введите данные для поиска мероприятия. Выберите возрастную категорию",
        reply_markup=kb.years_category,
    )


@router_user.callback_query(F.data == "18-24")
async def category_18_24(callback: CallbackQuery) -> None:
    await callback.message.answer("Вы выбрали возрастную категорию 18-24")
