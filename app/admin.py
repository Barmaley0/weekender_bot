from aiogram import Bot, F, Router
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import app.database.requests as req

from app.states import EventLetter


router_admin = Router()


class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.from_user is not None:
            return await req.is_admin(message.from_user.id)
        return False


@router_admin.callback_query(AdminFilter(), F.data.startswith("answer_"))
async def reply_to_user(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if callback.data is None:
        await callback.answer("Произошла ошибка")
        return

    try:
        user_id = callback.data.split("_")[1]
        admins = await req.get_all_admin()

        for admin_id in admins:
            try:
                await bot.send_message(
                    admin_id,
                    f"Администратор @{callback.from_user.username} взял запрос в обработку.",
                )
            except Exception as e:
                print(f"Ошибка при отправке уведомления администраторам {admin_id}: {e}")

        await callback.answer("Вы взяли запрос в обработку")
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            await state.set_state(EventLetter.message)
            await state.update_data(user_id=user_id)
            await callback.message.answer("Введите сообщение для пользователя:")
    except Exception as e:
        print(f"Oшибка в reply_to_user {e}")
        await callback.answer("Произошла ошибка")


@router_admin.message(AdminFilter(), Command("send_eventletter"))
async def send_event_letter(message: Message, state: FSMContext) -> None:
    await message.answer("Введите ID пользователя, которому хотите отправть сообщение:")
    await state.set_state(EventLetter.user_id)


@router_admin.message(AdminFilter(), EventLetter.user_id)
async def get_user_id(message: Message, state: FSMContext) -> None:
    if message.text is None or not message.text.isdigit():
        await message.answer("ID пользователя должен быть числом. Попробуйте ещё раз:")
        return

    await state.update_data(user_id=int(message.text))
    await message.answer("Введите сообщение для пользователя:")
    await state.set_state(EventLetter.message)


@router_admin.message(AdminFilter(), EventLetter.message)
async def send_message_to_user(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text is None:
        await message.answer("Сообщение не может быть пустым.")
        return

    data = await state.get_data()
    user_id = data["user_id"]

    if not user_id:
        await message.answer("ID пользователя не найден. Попробуйте ещё раз.")
        await state.clear()
        return

    try:
        await bot.send_message(chat_id=user_id, text=message.text)
        await message.answer("Сообщение отправлено пользователю.")
    except Exception as e:
        await message.answer(f"Произошла ошибка при отправке сообщения: {e}")

    await state.clear()
