import asyncio
import base64
import os
import traceback
from typing import List, Union

import google.generativeai as genai
import puremagic
from aiogram.types import Message
from asyncpg import Record
from google.generativeai.types import File
from loguru import logger
from PIL import Image

import db
from main import bot
from utils import ReturnValueThread
from ..media import get_file_id_from_chain

cache_path = os.getenv('CACHE_PATH')


async def _download_if_necessary(file_id: str):
    if not os.path.exists(cache_path + file_id):
        logger.debug(f"Downloading {file_id}")
        await bot.download(file_id, cache_path + file_id)


async def get_other_media(message: Message, gemini_token: str, all_messages: List[Record]) -> list:
    uploaded_media = []

    file_id = await get_file_id_from_chain(
        message.message_id,
        all_messages,
        "other",
        int(await db.get_chat_parameter(message.chat.id, "media_context_max_depth"))
    )
    if file_id:
        await _download_if_necessary(file_id)

        mime_type = puremagic.from_file(cache_path + file_id, mime=True)
        if mime_type == "application/octet-stream":
            mime_type = "application/pdf"

        logger.debug(f"Uploading {file_id} of type {mime_type} on token {gemini_token}")

        genai.configure(api_key=gemini_token)
        upload_thread = ReturnValueThread(target=genai.upload_file, kwargs={
            "path": cache_path + file_id,
            "display_name": f"Media file by {message.from_user.id}",
            "mime_type": mime_type
        })
        upload_thread.start()
        while upload_thread.is_alive():
            await asyncio.sleep(0.25)
        upload_result: File = upload_thread.result

        waited = 0
        while upload_result.state == "PROCESSING" and waited < 12:  # Wait for a max of 3 seconds
            await asyncio.sleep(0.25)
            waited += 1

        uploaded_media.append(upload_result)

    return uploaded_media


async def get_photo(message: Message, all_messages: List[Record], mode: str = "pillow") -> Union[Image, bytes]:
    photo_file_id = await get_file_id_from_chain(
        message.message_id,
        all_messages,
        "photo",
        int(await db.get_chat_parameter(message.chat.id, "media_context_max_depth"))
    )

    if photo_file_id:
        logger.debug(f"Loading an image with mode {mode}")
        await _download_if_necessary(photo_file_id)
        if mode == "pillow":
            return Image.open(cache_path + photo_file_id)
        elif mode == "base64":
            with open(cache_path + photo_file_id, "rb") as f:
                try:
                    result = base64.b64encode(f.read()).decode("utf-8")
                except Exception as exc:
                    traceback.print_exc()
            return result
