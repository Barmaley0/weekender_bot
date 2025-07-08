import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

import src.bot.db.repositories.user_repository as req_user

from src.bot.utils.texts import get_text_command_start


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_user = Router()


@router_user.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not message.from_user or not message.bot:
        return

    try:
        profile_photo_ids = list()

        try:
            user_photos = await message.bot.get_user_profile_photos(user_id=message.from_user.id, limit=10)
            logger.info(f'Found {user_photos.total_count} profile photos for user {message.from_user.id}')

            if user_photos and user_photos.total_count > 0:
                profile_photo_ids = [photo[-1].file_id for photo in user_photos.photos]
                logger.info(f'Found {len(profile_photo_ids)} profile photos for user {message.from_user.id}')
        except Exception as e:
            logger.error(f'Failed to get profile photos for user {message.from_user.id}: {e}')

        await req_user.save_first_user(
            tg_id=message.from_user.id,
            first_name=message.from_user.first_name,
            username=message.from_user.username,
        )

        if profile_photo_ids:
            await req_user.save_user_photos(tg_id=message.from_user.id, photo_ids=profile_photo_ids)
    except Exception as e:
        logger.error(f'Failed to save user data: {e}')
        await message.answer('❌ Произошла ошибка. Попробуйте позже.')

    await get_text_command_start(message)
