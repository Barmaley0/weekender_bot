from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

import app.keyboards as kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user is not None:
        await message.answer(
            f"Привет! {message.from_user.first_name}",
            reply_markup=kb.main,
        )
    else:
        await message.answer("Привет!")
