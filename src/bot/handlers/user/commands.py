import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


@router_user.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user:
        await req_user.save_first_user(
            message.from_user.id,
            message.from_user.first_name,
            message.from_user.username,
        )

        try:
            is_user_data = await req_user.user_data_exists(message.from_user.id)

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
