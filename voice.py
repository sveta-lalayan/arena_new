"""
voice.py — распознавание (Whisper) и озвучка (TTS) для ARENA.

Если пользователь пишет голосом — персонажи отвечают голосом (голос зависит от персонажа).
Любые ошибки OpenAI глушим: бот не падает, просто продолжает текстом.
"""
import asyncio
import io
import logging

import ai as ai_layer
from config import OPENAI_TRANSCRIBE_MODEL, OPENAI_TTS_MODEL
from game_data import VOICE_BY_PERSONALITY, LANG_TO_ISO
import database as db

logger = logging.getLogger(__name__)


async def get_pending_text(update, context) -> str:
    """Текст сообщения: голосовое → транскрибируем, иначе обычный текст."""
    msg = update.message
    if msg.voice is not None or msg.audio is not None:
        context.user_data["last_input_was_voice"] = True
        text = await _transcribe(msg.voice or msg.audio, update.effective_user.id)
        return (text or "").strip()
    context.user_data["last_input_was_voice"] = False
    return (msg.text or "").strip()


async def _transcribe(file_obj, user_id: int) -> str | None:
    client = ai_layer._get_client()
    if client is None:
        return None
    try:
        tg_file = await file_obj.get_file()
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)
        buf.name = "voice.ogg"
        kwargs = {"model": OPENAI_TRANSCRIBE_MODEL, "file": buf}
        language = db.get_user_language(user_id)
        if language in LANG_TO_ISO:
            kwargs["language"] = LANG_TO_ISO[language]
        resp = await asyncio.to_thread(client.audio.transcriptions.create, **kwargs)
        return resp.text
    except Exception:
        logger.exception("Ошибка распознавания речи")
        return None


def _tts_bytes(client, voice_name: str, text: str) -> bytes:
    resp = client.audio.speech.create(
        model=OPENAI_TTS_MODEL, voice=voice_name, input=text[:1000]
    )
    return resp.read()


async def maybe_reply_voice(update, context, text: str, personality: str):
    """Отвечаем голосом, только если пользователь сам писал голосом."""
    if not context.user_data.get("last_input_was_voice"):
        return
    client = ai_layer._get_client()
    if client is None or not text:
        return
    try:
        voice_name = VOICE_BY_PERSONALITY.get(personality, "onyx")
        data = await asyncio.to_thread(_tts_bytes, client, voice_name, text)
        buf = io.BytesIO(data)
        buf.seek(0)
        buf.name = "reply.ogg"
        await update.message.reply_voice(voice=buf)
    except Exception:
        logger.exception("Ошибка TTS")


async def handle_voice_message(update, context):
    """Все голосовые/аудио идут тем же маршрутом, что и текст."""
    context.user_data["last_input_was_voice"] = True
    from handlers import arena
    await arena.handle_text(update, context)
