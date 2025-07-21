import logging

from aiogram.types import Message

import src.bot.db.repositories.admin_repository as req_admin
import src.bot.db.repositories.user_repository as req_user
import src.bot.keyboards.builders as kb


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_text_command_start(message: Message) -> None:
    if not message.from_user:
        return

    try:
        is_user_data = await req_user.user_data_exists(message.from_user.id)
        is_user_admin = await req_admin.is_admin(message.from_user.id)

        if is_user_data:
            await message.answer(
                f"""
<b>Привет, {f'{message.from_user.first_name}' if message.from_user.first_name else ''}! Ты в уютном пространстве Weekender.</b>
Здесь люди находят мероприятия и своих людей рядом — для дружбы, поддержки, флирта или просто классных выходных вместе. 
💌 Заполни короткую анкету — и мы подберём тебе: — события, где можно быть собой — новых знакомых, с которыми ты на одной волне — возможность стать частью топового комьюнити.

‼️ При отсутствии фото аватарки и username бот будет работать некорректно. Посмотри настройки конфиденциальности. Измените это при необходимости.  

Всё просто: ты рассказываешь немного о себе — а мы подбираем тебе эмоции ✨ Ну что, начнём?
                """,
                reply_markup=await kb.get_main_kb(user_data_exists=is_user_data, is_admin=is_user_admin),
                parse_mode='html',
            )
        else:
            await message.answer(
                f"""
<b>Привет, {f'{message.from_user.first_name}' if message.from_user.first_name else ''}! Ты в уютном пространстве Weekender.</b>
Здесь люди находят мероприятия и своих людей рядом — для дружбы, поддержки, флирта или просто классных выходных вместе. 
💌 Заполни короткую анкету — и мы подберём тебе: — события, где можно быть собой — новых знакомых, с которыми ты на одной волне — возможность стать частью топового комьюнити.

‼️ При отсутствии фото аватарки и username бот будет работать некорректно. Посмотри настройки конфиденциальности. Измените это при необходимости.  

Всё просто: ты рассказываешь немного о себе — а мы подбираем тебе эмоции ✨ Ну что, начнём?
                """,
                reply_markup=await kb.get_main_kb(user_data_exists=is_user_data, is_admin=is_user_admin),
                parse_mode='html',
            )
    except Exception as e:
        logger.error(f'Errof checking user data: {e}')
