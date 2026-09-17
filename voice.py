"""
Голосовая поддержка ARENA.

Два независимых механизма:
1. Приём голосовых сообщений от пользователя — распознаются через OpenAI
   Whisper (ai.transcribe_audio) и передаются в ОБЫЧНЫЙ текстовый флоу бота
   (handlers.arena.handle_text), поэтому работают везде, где раньше нужно
   было печатать: 8 раундов Храма, ввод темы, ответ в бою, свободный разговор.
2. Голосовые ответы персонажей — если последнее сообщение пользователя было
   голосовым, реплика персонажа дополнительно озвучивается через OpenAI TTS
   (ai.synthesize_speech) и отправляется как voice-сообщение, каждый
   персонаж — своим голосом (game_data.VOICE_BY_PERSONALITY).

Модуль специально не импортирует handlers.arena на верхнем уровне —
handlers/arena.py импортирует voice.py, поэтому обратный импорт делаем
лениво (внутри функции), чтобы не получить циклический импорт при старте.
"""
import os
import asyncio
import logging
import tempfile

import ai

logger = logging.getLogger(__name__)


async def handle_voice_message(update, context):
    """
    Единая точка входа для любого voice-сообщения от пользователя,
    независимо от того, на каком шаге игры он сейчас находится.
    """
    from handlers import arena  # ленивый импорт — см. docstring модуля

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    tg_file = await context.bot.get_file(voice.file_id)
    local_path = os.path.join(
        tempfile.gettempdir(), f"arena_voice_{update.effective_user.id}_{voice.file_unique_id}.oga"
    )
    await tg_file.download_to_drive(local_path)

    language = context.user_data.get("language") or context.user_data.get("fe_language")

    try:
        text = await asyncio.to_thread(ai.transcribe_audio, local_path, language)
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass

    if not text:
        await update.message.reply_text("❌ Не расслышал(а) голосовое. Можешь написать текстом?")
        return

    # Помечаем ход как голосовой — дальше по флоу (arena._continue_round,
    # intro.handle_fe_response) это читается через last_input_was_voice,
    # чтобы ответить персонажу тоже голосом.
    context.user_data["last_input_was_voice"] = True
    context.user_data["_pending_text"] = text

    await arena.handle_text(update, context)


def get_pending_text(update, context) -> str:
    """
    Достаёт текст текущего хода: либо распознанный из голосового
    (см. handle_voice_message), либо обычный текст сообщения. Использовать
    в начале любого обработчика, который раньше читал update.message.text
    напрямую.
    """
    pending = context.user_data.pop("_pending_text", None)
    if pending is not None:
        return pending.strip()
    return (update.message.text or "").strip()


async def maybe_reply_voice(update, context, text: str, personality: str | None = None):
    """
    Если последний ход пользователя был голосовым — озвучивает реплику
    персонажа (или Храма, если personality не передан) и отправляет как
    voice-сообщение В ДОПОЛНЕНИЕ к обычному тексту. Никак не влияет на
    обычный (текстовый) флоу — просто ничего не делает, если условие не
    выполнено.
    """
    if not text or not context.user_data.get("last_input_was_voice"):
        return

    audio_path = await asyncio.to_thread(ai.synthesize_speech, text, personality)
    if not audio_path:
        return

    try:
        with open(audio_path, "rb") as f:
            await update.message.reply_voice(voice=f)
    except Exception as e:
        logger.warning(f"Не удалось отправить голосовой ответ: {e}")
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass