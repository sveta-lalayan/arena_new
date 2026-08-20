import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import BOT_TOKEN
import database as db
from handlers import start, profile, arena
from handlers import intro

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("play", arena.play_entry))
    app.add_handler(CommandHandler("profile", profile.profile_command))
    app.add_handler(CommandHandler("achievements", profile.achievements_command))
    app.add_handler(CommandHandler("stop", arena.stop_command))

    # Главное меню (инлайн-кнопки)
    app.add_handler(CallbackQueryHandler(start.show_main_menu, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(arena.play_entry, pattern="^menu_play$"))
    app.add_handler(CallbackQueryHandler(profile.profile_callback, pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(profile.achievements_callback, pattern="^menu_achievements$"))

    # Игровой поток
    app.add_handler(CallbackQueryHandler(arena.select_language, pattern="^debate_lang_"))
    app.add_handler(CallbackQueryHandler(arena.select_level, pattern="^debate_level_"))
    app.add_handler(CallbackQueryHandler(arena.select_personality, pattern="^debate_personality_"))
    app.add_handler(CallbackQueryHandler(arena.start_arena, pattern="^debate_start$"))
    app.add_handler(CallbackQueryHandler(arena.continue_yes, pattern="^continue_yes$"))
    app.add_handler(CallbackQueryHandler(arena.continue_no, pattern="^continue_no$"))

    # Вступительный диалог с гидом (новая механика)
    app.add_handler(CommandHandler("guide", intro.intro_entry))
    app.add_handler(CallbackQueryHandler(intro.intro_entry, pattern="^menu_intro$"))
    app.add_handler(CallbackQueryHandler(intro.select_language, pattern="^intro_lang_"))
    app.add_handler(CallbackQueryHandler(intro.select_level, pattern="^intro_level_"))
    app.add_handler(CallbackQueryHandler(intro.meet_character, pattern="^intro_meet_character$"))

    # 🔥 НОВЫЙ ОБРАБОТЧИК: Текст для вступительного диалога с гидом (ДО арены)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, intro.handle_intro_response))

    # Обычный текст (тема игры / ответ в диалоге) — один диспетчер по состоянию
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, arena.handle_text))

    logger.info("Arena 2.0 запущен")
    app.run_polling()


if __name__ == "__main__":
    main()