import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    JobQueue
)

from config import BOT_TOKEN
import database as db
from handlers import start, profile, arena, intro

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ========== ФУНКЦИИ ТАЙМЕРА ДЛЯ ARENA 2.0 ==========

async def arena_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическое завершение арены по таймауту (2 минуты для теста)"""
    try:
        user_id = context.job.data.get("user_id")
        chat_id = context.job.data.get("chat_id")

        if not user_id or not chat_id:
            print("❌ Таймаут: нет user_id или chat_id")
            return

        # Проверяем, активна ли игра
        if not context.user_data.get('awaiting_response', False):
            print(f"⏭️ Игра пользователя {user_id} уже завершена")
            return

        print(f"⏰ Таймаут! Игра пользователя {user_id} завершена через 2 минуты")

        await context.bot.send_message(
            chat_id=chat_id,
            text="⏰ <b>ВРЕМЯ ВЫШЛО!</b>\n\nИгра автоматически завершена через 2 минуты.\n\n📊 Считаю результаты...",
            parse_mode='HTML'
        )

        # Останавливаем игру
        context.user_data.pop('awaiting_response', None)

        # Создаём FakeUpdate для finish_arena
        class FakeUpdate:
            def __init__(self, user_id, chat_id, bot):
                self.effective_user = type('User', (), {'id': user_id, 'first_name': 'Участник'})()
                self.effective_chat = type('Chat', (), {'id': chat_id})()
                self.callback_query = None
                self.message = type('Message', (), {
                    'reply_text': lambda self, text, **kwargs: context.bot.send_message(chat_id=chat_id, text=text,
                                                                                        **kwargs)
                })()
                self.bot = bot

        fake_update = FakeUpdate(user_id, chat_id, context.bot)

        # Завершаем игру через arena.py
        await arena.finish_arena(fake_update, context, via_callback=False)

        # Удаляем Job
        jobs = context.job_queue.get_jobs_by_name(f"arena_timeout_{user_id}")
        for job in jobs:
            job.schedule_removal()

    except Exception as e:
        print(f"❌ Ошибка в arena_timeout: {e}")
        import traceback
        traceback.print_exc()


def start_arena_timer(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, minutes: int = 2):
    """Запускает таймер для арены"""
    if context.job_queue:
        # Удаляем старый таймер если был
        old_jobs = context.job_queue.get_jobs_by_name(f"arena_timeout_{user_id}")
        for job in old_jobs:
            job.schedule_removal()

        # Создаём новый таймер
        context.job_queue.run_once(
            arena_timeout,
            minutes * 60,
            data={"user_id": user_id, "chat_id": chat_id},
            name=f"arena_timeout_{user_id}"
        )
        print(f"⏰ Таймер запущен для пользователя {user_id} на {minutes} минут(ы)")
        return True
    return False


def stop_arena_timer(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Останавливает таймер арены"""
    if context.job_queue:
        jobs = context.job_queue.get_jobs_by_name(f"arena_timeout_{user_id}")
        for job in jobs:
            job.schedule_removal()
        print(f"⏰ Таймер удалён для пользователя {user_id}")
        return True
    return False


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========

def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # --- Команды ---
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("play", arena.play_entry))
    app.add_handler(CommandHandler("profile", profile.profile_command))
    app.add_handler(CommandHandler("achievements", profile.achievements_command))
    app.add_handler(CommandHandler("stop", arena.stop_command))
    app.add_handler(CommandHandler("arena", intro.enter_arena_menu))

    # --- Главное меню ---
    app.add_handler(CallbackQueryHandler(start.show_main_menu, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(arena.play_entry, pattern="^menu_play$"))
    app.add_handler(CallbackQueryHandler(profile.profile_callback, pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(profile.achievements_callback, pattern="^menu_achievements$"))

    # --- ARENA First Encounter ---
    app.add_handler(CallbackQueryHandler(intro.enter_arena_menu, pattern="^menu_enter_arena$"))
    app.add_handler(CallbackQueryHandler(intro.select_language, pattern="^fe_lang_"))
    app.add_handler(CallbackQueryHandler(intro.enter_battle, pattern="^fe_enter_battle$"))

    # --- Игровой поток (Arena 2.0) ---
    app.add_handler(CallbackQueryHandler(arena.select_language, pattern="^debate_lang_"))
    app.add_handler(CallbackQueryHandler(arena.select_level, pattern="^debate_level_"))
    app.add_handler(CallbackQueryHandler(arena.select_personality, pattern="^debate_personality_"))
    app.add_handler(CallbackQueryHandler(arena.start_arena, pattern="^debate_start$"))
    app.add_handler(CallbackQueryHandler(arena.continue_yes, pattern="^continue_yes$"))
    app.add_handler(CallbackQueryHandler(arena.continue_no, pattern="^continue_no$"))

    # --- Обработка текста ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, intro.handle_fe_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, arena.handle_text))

    # --- ARENA First Encounter (дополнительные) ---
    app.add_handler(CallbackQueryHandler(intro.enter_arena_menu, pattern="^menu_enter_arena$"))
    app.add_handler(CallbackQueryHandler(intro.select_language, pattern="^fe_lang_"))
    app.add_handler(CallbackQueryHandler(intro.enter_battle, pattern="^fe_enter_battle$"))
    app.add_handler(CallbackQueryHandler(intro.start_battle, pattern="^fe_start_battle$"))

    logger.info("Arena 2.0 запущен")
    app.run_polling()


if __name__ == "__main__":
    main()