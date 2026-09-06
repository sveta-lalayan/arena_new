import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import BOT_TOKEN
import database as db
from handlers import start, profile, arena, intro

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Хранилище таймеров
arena_timers = {}


def start_arena_timer(context, user_id, chat_id, minutes=2):
    stop_arena_timer(context, user_id)
    seconds = minutes * 60
    job = context.job_queue.run_once(
        arena_timeout,
        seconds,
        data={"user_id": user_id, "chat_id": chat_id},
        name=f"arena_timer_{user_id}"
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
    data = context.job.data
    user_id = data["user_id"]
    chat_id = data["chat_id"]

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⏰ Время вышло! Битва завершена."
        )
    except Exception:
        pass

    if user_id in arena_timers:
        del arena_timers[user_id]


def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # --- Команды ---
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("play", arena.play_entry))
    app.add_handler(CommandHandler("profile", profile.profile_command))
    app.add_handler(CommandHandler("achievements", profile.achievements_command))
    app.add_handler(CommandHandler("stop", arena.stop_command))

    # --- Главное меню ---
    app.add_handler(CallbackQueryHandler(start.show_main_menu, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(arena.play_entry, pattern="^menu_play$"))
    app.add_handler(CallbackQueryHandler(profile.profile_callback, pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(profile.achievements_callback, pattern="^menu_achievements$"))

    # --- ARENA First Encounter ---
    app.add_handler(CommandHandler("arena", intro.enter_arena_menu))
    app.add_handler(CallbackQueryHandler(intro.enter_arena_menu, pattern="^menu_enter_arena$"))
    app.add_handler(CallbackQueryHandler(intro.select_language, pattern="^fe_lang_"))
    app.add_handler(CallbackQueryHandler(intro.start_battle, pattern="^fe_start_battle$"))

    # --- Игровой поток ---
    app.add_handler(CallbackQueryHandler(arena.select_language, pattern="^debate_lang_"))
    app.add_handler(CallbackQueryHandler(arena.select_level, pattern="^debate_level_"))
    app.add_handler(CallbackQueryHandler(arena.select_personality, pattern="^debate_personality_"))
    app.add_handler(CallbackQueryHandler(arena.start_arena, pattern="^debate_start$"))
    app.add_handler(CallbackQueryHandler(arena.continue_yes, pattern="^continue_yes$"))
    app.add_handler(CallbackQueryHandler(arena.continue_no, pattern="^continue_no$"))

    # --- После боя ---
    app.add_handler(CallbackQueryHandler(arena.rematch, pattern="^rematch_"))
    app.add_handler(CallbackQueryHandler(arena.freetalk, pattern="^freetalk_"))

    # --- Обработка текста ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, arena.handle_text))

    logger.info("Arena 2.0 запущен")
    app.run_polling()


if __name__ == "__main__":
    main()