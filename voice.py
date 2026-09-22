"""
voice.py — распознавание (Whisper) и озвучка (TTS) для ARENA.

Правила:
  • Whisper получает language-подсказку из learning_language (не из interface).
  • Голос персонажа берётся из VOICE_BY_PERSONALITY (game_data).
  • Голос Храма — TEMPLE_VOICE.
  • Голосовые и текстовые ходы идут по одному и тому же маршруту:
    voice.handle_voice_message → arena.handle_text.
  • Любые ошибки OpenAI глушим: бот не падает, просто продолжает текстом.
"""
import asyncio
import io
import logging

import ai as ai_layer
import database as db
from config import (
    OPENAI_TRANSCRIBE_MODEL,
    OPENAI_TTS_MODEL,
    ISO_TO_LANG_KEY,
    LANG_KEY_TO_ISO,
)
from game_data import VOICE_BY_PERSONALITY, TEMPLE_VOICE, LANG_TO_ISO

logger = logging.getLogger(__name__)


# ==================================================================
# ВХОД: любой голос/аудио → текст → общий текстовый роутер
# ==================================================================

async def handle_voice_message(update, context):
    """Все голосовые/аудио идут тем же путём, что и обычный текст."""
    context.user_data["last_input_was_voice"] = True
    from handlers import arena
    await arena.handle_text(update, context)


async def get_pending_text(update, context) -> str:
    """
    Текст текущего хода:
      • голосовое/аудио → Whisper;
      • обычный текст → update.message.text.
    """
    msg = update.message
    if msg.voice is not None or msg.audio is not None:
        context.user_data["last_input_was_voice"] = True
        text = await _transcribe(msg.voice or msg.audio, update.effective_user.id, context)
        return (text or "").strip()

    context.user_data["last_input_was_voice"] = False
    return (msg.text or "").strip()


# ==================================================================
# WHISPER
# ==================================================================

def _whisper_lang_code(user_id: int, context) -> str | None:
    """
    language для Whisper — из learning_language пользователя.
    Приоритет: user_data (fresh) → БД → None.
    """
    ud = context.user_data or {}
    iso = ud.get("language_iso") or ud.get("fe_language")
    if not iso:
        iso = db.get_learning_language(user_id)
    if not iso:
        return None
    # ISO (en/ru/…) → английское имя языка (english/russian/…) → ISO-2 для Whisper
    lang_key = ISO_TO_LANG_KEY.get(iso, "english")
    return LANG_TO_ISO.get(lang_key)


async def _transcribe(file_obj, user_id: int, context) -> str | None:
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
        iso2 = _whisper_lang_code(user_id, context)
        if iso2:
            kwargs["language"] = iso2

        resp = await asyncio.to_thread(client.audio.transcriptions.create, **kwargs)
        return resp.text
    except Exception:
        logger.exception("Ошибка распознавания речи")
        return None


# ==================================================================
# TTS: ответ голосом, если пользователь писал голосом
# ==================================================================

def _tts_bytes(client, voice_name: str, text: str) -> bytes:
    resp = client.audio.speech.create(
        model=OPENAI_TTS_MODEL, voice=voice_name, input=text[:1000]
    )
    return resp.read()


def _pick_voice(personality: str) -> str:
    if personality == "_temple":
        return TEMPLE_VOICE
    return VOICE_BY_PERSONALITY.get(personality, "onyx")


async def maybe_reply_voice(update, context, text: str, personality: str | None = None):
    """
    Отвечаем голосом, ТОЛЬКО если последний ход пользователя был голосовым.
    personality='_temple' → голос Храма.
    """
    if not context.user_data.get("last_input_was_voice"):
        return
    if not text:
        return

    client = ai_layer._get_client()
    if client is None:
        return

    try:
        voice_name = _pick_voice(personality or "_temple")
        data = await asyncio.to_thread(_tts_bytes, client, voice_name, text)
        buf = io.BytesIO(data)
        buf.seek(0)
        buf.name = "reply.ogg"
        await update.message.reply_voice(voice=buf)
    except Exception:
        logger.exception("Ошибка TTS")