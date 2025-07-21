import logging

from aiogram import F, Router
from aiogram.types import Message

import src.bot.keyboards.builders as kb


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_admin = Router()


@router_admin.message(F.text == '🪪')
async def show_admin_menu(message: Message) -> None:
    await message.answer(
        '<b>➖➖  Меню администратора  ➖➖</b>', reply_markup=await kb.get_admin_menu_kb(), parse_mode='html'
    )
