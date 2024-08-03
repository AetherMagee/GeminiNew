import os

from aiogram.enums import ParseMode
from aiogram.types import Message
from loguru import logger

import api.google
import db
from utils import get_message_text, no_markdown

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def handle_normal_message(message: Message) -> None:
    if message.chat.id == -1002031488332:
        return

    requirement_pass = False
    for requirement in [message.text, message.caption, message.video, message.document, message.sticker,
                        message.photo, message.voice, message.audio, message.video_note]:
        if requirement:
            requirement_pass = True
            break
    if not requirement_pass:
        return

    text = await get_message_text(message)

    if text.startswith("/"):
        return

    await db.save_aiogram_message(message)

    if (message.reply_to_message and message.reply_to_message.from_user.id == bot_id) \
            or f"@{bot_username}" in text \
            or message.chat.id == message.from_user.id:

        forced = await get_message_text(message, "after_forced")
        if forced:
            await message.reply(forced)
            await db.save_our_message(message, forced)
            return

        output = await api.google.generate_response(message)
        try:
            await message.reply(output, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            try:
                output = await no_markdown(output)
                await message.reply(output)
                await db.save_system_message(
                    message.chat.id,
                    "Your previous message was not accepted by the endpoint due to bad formatting. The user sees your "
                    "message WITHOUT your formatting. Do better next time. Keep the formatting rules in mind.")
            except Exception:
                await message.reply("❌ <b>Telegram не принимает ответ бота.</b>")
