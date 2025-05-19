from aiogram import Router
from aiogram.filters import Filter
from aiogram.types import Message

import app.database.requests as req


router_admin = Router()


class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is not None:
            return await req.is_admin(message.from_user.id)
        return False
