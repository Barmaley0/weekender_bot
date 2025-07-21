from aiogram import Router

from .callbacks import router_admin as callback_router

# from .commands import router_admin as command_router
from .messages import router_admin as message_router


router_admin = Router()
router_admin.include_router(callback_router)
# router_admin.include_router(command_router)
router_admin.include_router(message_router)

__all__ = ['router_admin']
