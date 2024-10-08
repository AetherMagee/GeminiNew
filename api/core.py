import traceback

from aiogram.types import Message
from loguru import logger

import api.google
import api.openai
import db


async def generate_response(message: Message, endpoint: str) -> str:
    if endpoint == "google":
        return await api.google.generate_response(message)
    elif endpoint == "openai":
        try:
            out = await api.openai.generate_response(message)
        except Exception as e:
            traceback.print_exc()
            logger.error(e)
            out = "❌ *Произошел сбой эндпоинта OpenAI.*"

        auto_fallback_allowed = await db.get_chat_parameter(message.chat.id, "o_auto_fallback")
        if out.startswith("❌") and auto_fallback_allowed:
            logger.debug(f"Falling back to Google...")
            crash_warning = await message.reply(
                f"⚠️ <b>Эндпоинт OpenAI дал сбой, запрос был направлен в Gemini API.</b>")
            out = await api.google.generate_response(message)
            await crash_warning.delete()
        return out
    else:
        raise ValueError("what.")
