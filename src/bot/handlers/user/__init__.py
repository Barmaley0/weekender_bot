from aiogram import Router

from .callbacks import router_user as callback_router
from .commands import router_user as command_router
from .messages import router_user as message_router


router_user = Router()
router_user.include_router(callback_router)
router_user.include_router(command_router)
router_user.include_router(message_router)

__all__ = ['router_user']
