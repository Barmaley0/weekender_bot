import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import src.bot.db.repositories.support_repository as req_support
import src.bot.keyboards.builders as kb

from src.bot.db.repositories.admin_repository import is_admin
from src.bot.fsm.admin_states import AdminChatState


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router_admin = Router()


@router_admin.message(F.text == '🪪')
async def show_admin_menu(message: Message) -> None:
    await message.answer(
        '<b>➖➖  Меню администратора  ➖➖</b>', reply_markup=await kb.get_admin_menu_kb(), parse_mode='html'
    )


@router_admin.message(AdminChatState.waiting_for_reply)
async def process_admin_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработка введенного ответа администратора"""
    if not message.text or not message.from_user:
        await message.answer('❌ Ошибка: не удалось обработать ответ')
        return

    if message.bot is None:
        logger.error('❗Bot instance is not available')
        await message.answer('❌ Ошибка сервера')
        return

    if not await is_admin(message.from_user.id):
        logger.info(f'❗User {message.from_user.id} is not admin!')
        await message.answer('❌ Недостаточно прав!', show_alert=True)
        return
    data = await state.get_data()
    ticket_id = data.get('current_ticket_id')

    if not ticket_id:
        await message.answer('❌ Ошибка: не удалось обработать ответ')
        await state.clear()
        return

    ticket = await req_support.get_ticket_by_id(ticket_id)
    logger.info(f'➡️ Admin {message.from_user.id} wants to send a message to {ticket.id}')
    if not ticket or not ticket.is_active:
        await message.answer('❌ Тикет не найден или уже закрыт.')
        await state.clear()
        return

    try:
        # Сохраняем сообщение в БД
        await req_support.add_message_to_ticket(ticket_id=ticket_id, text=message.text, is_from_user=False)

        # Отправляем сообщение пользователю
        await message.bot.send_message(
            chat_id=ticket.user.tg_id,
            text=f'🟣 Weekender:\n{message.text}',
            disable_notification=False,
        )

        await message.answer('✅ Ответ отправлен пользователю')
    except Exception as e:
        logger.error(f'Ошибка при отправке ответа: {e}')
        await message.answer('❌ Не удалось отправить ответ')
    finally:
        await state.clear()
