"""
bot.py — точка входа ARENA: роутинг, таймер боя, ежедневные пуши.

Правила:
  • Таймер боя — детерминированный. LLM не решает, когда закончить бой.
  • При истечении времени Арена сама вызывает arena.finish_arena_by_timeout,
    без /stop со стороны пользователя.
  • Пуш — один раз в день, на interface_language пользователя.
  • Никаких технических команд пользователю не показываем — только меню.
"""
import asyncio
import logging
from datetime import datetime, timezone, time as dt_time

from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import (
    BOT_TOKEN, DAILY_PUSH_HOUR, BATTLE_DURATION_MINUTES, is_admin,
)
import ai
import database as db
import i18n
import voice
from handlers import start, profile, arena, intro, settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

arena_timers: dict[int, object] = {}


# ==================================================================
# ТАЙМЕР БОЯ
# ==================================================================

def start_arena_timer(context, user_id: int, chat_id: int, minutes: int | None = None):
    stop_arena_timer(context, user_id)
    job = context.job_queue.run_once(
        arena_timeout,
        (minutes or BATTLE_DURATION_MINUTES) * 60,
        data={"user_id": user_id, "chat_id": chat_id},
        name=f"arena_timer_{user_id}",
    )
    arena_timers[user_id] = job


def stop_arena_timer(context, user_id: int):
    if user_id in arena_timers:
        try:
            arena_timers[user_id].schedule_removal()
        except Exception:
            pass
        del arena_timers[user_id]


async def arena_timeout(context):
    """
    Время боя вышло. Никаких кнопок «продолжить» — Арена сама подводит итог.
    """
    data = context.job.data
    user_id = data["user_id"]
    chat_id = data["chat_id"]
    arena_timers.pop(user_id, None)

    # Проверяем, идёт ли ещё бой (пользователь мог закончить раньше)
    ud = context.application.user_data.get(user_id) or {}
    if not ud.get("dialogue") or ud.get("battle_type") != "battle":
        return

    try:
        await arena.finish_arena_by_timeout(context, user_id, chat_id)
    except Exception:
        logger.exception("Авто-итоги после таймаута не удались")
        # Не оставляем пользователя в подвешенном состоянии молча: если дебриф
        # всё же не собрался, сообщаем и сбрасываем бой, чтобы не блокировать Free Talk.
        try:
            il = db.get_interface_language(user_id)
            await context.bot.send_message(chat_id, i18n.t(il, "BATTLE.TIME_UP"))
        except Exception:
            pass
        arena._reset_state(ud)


# ==================================================================
# ЕЖЕДНЕВНЫЙ ПУШ
# ==================================================================

async def send_daily_pushes(context):
    """
    Один пуш в день от персонажа — на interface_language пользователя,
    по темам из его памяти. Никаких дублей: проверяем last_push_at.
    """
    profiles = await asyncio.to_thread(db.get_all_push_profiles)
    today = datetime.now(timezone.utc).date()

    for p in profiles:
        # уже отправляли сегодня?
        if p.get("last_push_at"):
            try:
                if datetime.fromisoformat(p["last_push_at"]).date() == today:
                    continue
            except ValueError:
                pass

        # бился за последние 24 часа?
        try:
            if await asyncio.to_thread(db.has_battled_today, p["telegram_id"]):
                continue
        except Exception:
            pass

        try:
            il = p.get("interface_language") or "en"
            learning_iso = p.get("learning_language") or "en"
            # Текст пуша пишет персонаж на языке обучения. Кнопка — на языке интерфейса.
            from config import ISO_TO_LANG_KEY
            learning_key = ISO_TO_LANG_KEY.get(learning_iso, "english")

            level = await asyncio.to_thread(db.get_current_level, p["telegram_id"]) or "B1"

            message = await asyncio.to_thread(
                ai.generate_daily_push,
                p["personality"], p["topics"], p["first_name"],
                learning_key, None, level,
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(i18n.t(il, "MENU.BATTLE"), callback_data="daily_battle")],
            ])
            await context.bot.send_message(
                chat_id=p["telegram_id"], text=message, reply_markup=keyboard,
            )
            await asyncio.to_thread(db.mark_push_sent, p["telegram_id"])
        except Exception as e:
            logger.warning("Пуш %s не отправлен: %s", p["telegram_id"], e)


# ==================================================================
# КОМАНДЫ МЕНЮ TELEGRAM
# ==================================================================

async def set_user_commands(app: Application, user_id: int, il: str):
    """
    Локализованные подсказки команд для конкретного пользователя.
    Бренд ARENA не переводим.
    """
    commands = [
        BotCommand("start", "ARENA"),
    ]
    try:
        await app.bot.set_my_commands(
            commands, scope=BotCommandScopeChat(chat_id=user_id)
        )
    except Exception:
        pass


# ==================================================================
# ЗАПУСК
# ==================================================================

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Ежедневный пуш
    app.job_queue.run_daily(send_daily_pushes, time=dt_time(hour=DAILY_PUSH_HOUR, minute=0))

    # --- Команды ---
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("arena", intro.enter_arena_menu))
    app.add_handler(CommandHandler("profile", profile.profile_command))
    app.add_handler(CommandHandler("achievements", profile.achievements_command))

    # --- Меню ---
    app.add_handler(CallbackQueryHandler(start.show_main_menu,  pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(profile.my_arena,      pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(profile.my_arsenal,    pattern="^menu_arsenal$"))
    app.add_handler(CallbackQueryHandler(profile.achievements_callback, pattern="^menu_achievements$"))
    app.add_handler(CallbackQueryHandler(settings.settings_menu, pattern="^menu_settings$"))

    # --- Настройки (interface / learning) ---
    app.add_handler(CallbackQueryHandler(settings.pick_interface,  pattern="^set_pick_iface$"))
    app.add_handler(CallbackQueryHandler(settings.pick_learning,   pattern="^set_pick_learn$"))
    app.add_handler(CallbackQueryHandler(settings.set_interface_cb, pattern="^set_iface_"))
    app.add_handler(CallbackQueryHandler(settings.set_learning_cb,  pattern="^set_learn_"))

    # --- Храм ---
    app.add_handler(CallbackQueryHandler(intro.enter_arena_menu, pattern="^menu_enter_arena$"))
    app.add_handler(CallbackQueryHandler(intro.select_language,  pattern="^fe_lang_"))
    app.add_handler(CallbackQueryHandler(arena.start_battle,     pattern="^fe_start_battle$"))
    app.add_handler(CallbackQueryHandler(intro.daily_battle,     pattern="^daily_battle$"))

    # --- Battle ---
    app.add_handler(CallbackQueryHandler(arena.play_entry,       pattern="^menu_play$"))

    # --- Free Talk ---
    app.add_handler(CallbackQueryHandler(arena.freetalk,         pattern="^freetalk$"))
    app.add_handler(CallbackQueryHandler(arena.ft_select_language, pattern="^ft_lang_"))
    app.add_handler(CallbackQueryHandler(arena.freetalk_pick,    pattern="^freetalk_pick_"))

    # --- Arsenal (после дебрифа) ---
    app.add_handler(CallbackQueryHandler(arena.arsenal_add_pending, pattern="^arsenal_add_pending$"))

    # --- Текст / голос ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, arena.handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice.handle_voice_message))

    # --- Bot menu (можно задать один раз на старте для default scope) ---
    # Локализованные подсказки для конкретного пользователя проставляются
    # по мере смены interface_language (см. settings.set_interface_cb).
    from telegram import BotCommandScopeDefault
    app.bot_data["set_user_commands"] = set_user_commands

    logger.info("ARENA запущена")
    app.run_polling()


if __name__ == "__main__":
    main()