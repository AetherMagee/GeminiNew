from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from loguru import logger

import db
from main import bot


async def is_allowed_to_alter_memory(message: Message) -> bool:
    if message.from_user.id == message.chat.id:
        return True

    permission_mode = await db.get_chat_parameter(message.chat.id, "memory_alter_permission")
    if permission_mode == "owner":
        allowed_statuses = ["creator"]
    elif permission_mode == "admins":
        allowed_statuses = ["administrator", "creator"]
    else:
        allowed_statuses = ["member", "administrator", "creator"]

    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in allowed_statuses:
            return False
    except TelegramBadRequest:
        logger.warning("No admin rights, assuming sufficient permissions.")
        if permission_mode in ["owner", "admins"]:
            await message.reply("⚠️ <b>Бот не является администратором, поэтому не может проверить этого "
                                "пользователя на наличие прав для изменения памяти бота.</b>")
            return False
        return True
