"""
bot.py — точка входа ARENA: хендлеры, таймер боя, ежедневные пуши.
"""
import asyncio
import logging
from datetime import datetime, timezone, time as dt_time

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, DAILY_PUSH_HOUR, BATTLE_DURATION_MINUTES
import ai
import database as db
import voice
from handlers import start, profile, arena, intro

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

arena_timers = {}


def start_arena_timer(context, user_id, chat_id, minutes=None):
    stop_arena_timer(context, user_id)
    job = context.job_queue.run_once(
        arena_timeout,
        (minutes or BATTLE_DURATION_MINUTES) * 60,
        data={"user_id": user_id, "chat_id": chat_id},
        name=f"arena_timer_{user_id}",
    )
    arena_timers[user_id] = job


def stop_arena_timer(context, user_id):
    if user_id in arena_timers:
        try:
            arena_timers[user_id].schedule_removal()
        except Exception:
            pass
        del arena_timers[user_id]


async def arena_timeout(context):
    """Время боя вышло — Арена подводит итоги сама, без /stop."""
    data = context.job.data
    arena_timers.pop(data["user_id"], None)
    try:
        await context.bot.send_message(
            chat_id=data["chat_id"],
            text="⏰ Время вышло! Арена подводит итоги...",
        )
    except Exception:
        pass
    try:
        await arena.finish_arena_by_timeout(context, data["user_id"], data["chat_id"])
    except Exception:
        logger.exception("Авто-итоги после таймаута не удались")


async def send_daily_pushes(context):
    """
    Один пуш в день. Пропускаем тех, кому уже отправили сегодня (last_push_at)
    и тех, кто бился за последние 24 часа. Тема — из интересов человека (БД).
    """
    profiles = await asyncio.to_thread(db.get_all_push_profiles)
    today = datetime.now(timezone.utc).date()

    for p in profiles:
        if p.get("last_push_at"):
            try:
                if datetime.fromisoformat(p["last_push_at"]).date() == today:
                    continue
            except ValueError:
                pass

        try:
            if await asyncio.to_thread(db.has_battled_today, p["telegram_id"]):
                continue
            language = p.get("language") or "english"
            level = await asyncio.to_thread(db.get_current_level, p["telegram_id"]) or "B1"
            message = await asyncio.to_thread(
                ai.generate_daily_push, p["personality"], p["topics"],
                p["first_name"], language, level=level,
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚔️ Принять вызов", callback_data="daily_battle")]
            ])
            await context.bot.send_message(chat_id=p["telegram_id"], text=message, reply_markup=keyboard)
            await asyncio.to_thread(db.mark_push_sent, p["telegram_id"])
        except Exception as e:
            logger.warning(f"Пуш {p['telegram_id']}: {e}")


def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.job_queue.run_daily(send_daily_pushes, time=dt_time(hour=DAILY_PUSH_HOUR, minute=0))

    # --- Команды ---
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("arena", intro.enter_arena_menu))
    app.add_handler(CommandHandler("play", arena.play_entry))
    app.add_handler(CommandHandler("profile", profile.profile_command))
    app.add_handler(CommandHandler("achievements", profile.achievements_command))
    app.add_handler(CommandHandler("stop", arena.stop_command))

    # --- Меню ---
    app.add_handler(CallbackQueryHandler(start.show_main_menu, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(profile.profile_callback, pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(profile.achievements_callback, pattern="^menu_achievements$"))

    # --- Храм ---
    app.add_handler(CallbackQueryHandler(intro.enter_arena_menu, pattern="^menu_enter_arena$"))
    app.add_handler(CallbackQueryHandler(intro.select_language, pattern="^fe_lang_"))
    app.add_handler(CallbackQueryHandler(arena.start_battle, pattern="^fe_start_battle$"))
    app.add_handler(CallbackQueryHandler(intro.daily_battle, pattern="^daily_battle$"))

    # --- Battle ---
    app.add_handler(CallbackQueryHandler(arena.play_entry, pattern="^menu_play$"))
    app.add_handler(CallbackQueryHandler(arena.rematch, pattern="^rematch_"))
    app.add_handler(CallbackQueryHandler(arena.next_guardian, pattern="^next_guardian_"))

    # --- Free talk ---
    app.add_handler(CallbackQueryHandler(arena.freetalk, pattern="^freetalk$"))
    app.add_handler(CallbackQueryHandler(arena.freetalk_pick, pattern="^freetalk_pick_"))

    # --- Текст / голос ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, arena.handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice.handle_voice_message))

    logger.info("Arena запущена")
    app.run_polling()


if __name__ == "__main__":
    main()
