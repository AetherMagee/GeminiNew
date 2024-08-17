import os

from aiogram import html
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from loguru import logger

import api
import api.openai
import db
from api.google import ERROR_MESSAGES
from utils import get_message_text
from .commands.shared import is_allowed_to_alter_memory

bot_id = int(os.getenv("TELEGRAM_TOKEN").split(":")[0])
bot_username = os.getenv("BOT_USERNAME")


async def meets_endpoint_requirements(message: Message, endpoint: str) -> bool:
    endpoint_requirements = {
        "google": [message.text, message.caption, message.video, message.document, message.sticker,
                   message.photo, message.voice, message.audio, message.video_note],
        "openai": [message.text, message.caption, message.photo]
    }

    if endpoint in endpoint_requirements.keys():
        return any(endpoint_requirements[endpoint])
    else:
        raise ValueError(f"Unknown endpoint: {endpoint}")


async def should_generate_response(message: Message) -> bool:
    if message.reply_to_message and message.reply_to_message.from_user.id == bot_id:  # If replying to us
        return True

    if f"@{bot_username}" in await get_message_text(message):  # If mentioned
        return True

    if message.chat.id == message.from_user.id:  # If in DMs
        return True

    return False


async def check_token_limit(message: Message) -> bool:
    token_limit = await db.get_chat_parameter(message.chat.id, "token_limit")
    if token_limit:
        current_tokens = await api.openai.count_tokens(message.chat.id)
        if current_tokens > token_limit:
            token_action = await db.get_chat_parameter(message.chat.id, "token_limit_action")
            if token_action == "warn":
                await message.reply(f"⚠️ <b>Токенов больше, чем лимит</b> <i>({current_tokens} > {token_limit})</i>")
            elif token_action == "block":
                await message.reply(f"❌ <b>Запрос заблокирован: Токенов больше, чем лимит</b> "
                                    f"<i>({current_tokens} > {token_limit})</i>")
                return True
    return False


async def handle_forced_response(message: Message) -> bool:
    forced_response = await get_message_text(message, "after_forced")
    if forced_response:
        if await is_allowed_to_alter_memory(message):
            our_message = await message.reply(forced_response)
            await db.save_our_message(message, forced_response, our_message.message_id)
        else:
            await message.reply("❌ <b>У вас нет доступа к этой команде.</b>")
        return True
    return False


async def handle_response(message: Message, output: str) -> None:
    try:
        our_message = await message.reply(output, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
        try:
            our_message = await message.reply(html.quote(output))
            await db.save_system_message(
                message.chat.id,
                "Your previous message was not accepted by the endpoint due to bad formatting. The user sees your "
                "message WITHOUT your formatting. Do better next time. Keep the formatting rules in mind.")
        except TelegramBadRequest:
            our_message = await message.reply(f"❌ <b>Telegram не принимает ответ "
                                              f"бота.</b> <i>({len(output)} символов)</i>")
    finally:
        if output.startswith("❌"):
            output = ERROR_MESSAGES["system_failure"]
        await db.save_our_message(message, output, our_message.message_id)


async def handle_new_message(message: Message) -> None:
    endpoint = await db.get_chat_parameter(message.chat.id, "endpoint")

    if not await meets_endpoint_requirements(message, endpoint):
        return

    await db.save_aiogram_message(message)

    if not await should_generate_response(message):
        return

    if await check_token_limit(message):
        return

    if await handle_forced_response(message):
        return

    output = await api.generate_response(message, endpoint)

    await handle_response(message, output)


async def handle_message_edit(message: Message) -> None:
    await db.replace_message(message.chat.id, message.message_id, message.text)
