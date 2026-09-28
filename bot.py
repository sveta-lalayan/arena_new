"""
bot.py — точка входа ARENA: роутинг, таймер боя, ежедневные пуши,
ежедневное обновление Language Profile.
"""
import asyncio
import logging
from datetime import datetime, timezone, time as dt_time
from datetime import timedelta

from telegram import (
    BotCommand,
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
    data = context.job.data
    user_id = data["user_id"]
    chat_id = data["chat_id"]
    arena_timers.pop(user_id, None)

    ud = context.application.user_data.get(user_id) or {}
    if not ud.get("dialogue") or ud.get("battle_type") != "battle":
        return

    try:
        await arena.finish_arena_by_timeout(context, user_id, chat_id)
    except Exception:
        logger.exception("Авто-итоги после таймаута не удались")
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
        except Exception:
            pass

        try:
            il = p.get("interface_language") or "en"
            learning_iso = p.get("learning_language") or "en"
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
# ЕЖЕДНЕВНОЕ ОБНОВЛЕНИЕ LANGUAGE PROFILE
# ==================================================================

async def daily_language_profile_update(context):
    """
    Раз в сутки (на 1 час позже пушей) Арена пересматривает весь материал
    за прошедшие 24 часа и обновляет языковой / коммуникационный профиль.
    """
    profiles = await asyncio.to_thread(db.get_all_push_profiles)

    for p in profiles:
        user_id = p["telegram_id"]
        try:
            last = await asyncio.to_thread(db.get_last_language_update_at, user_id)
            if last:
                try:
                    age = datetime.now(timezone.utc) - datetime.fromisoformat(last)
                    if age < timedelta(hours=20):
                        continue
                except ValueError:
                    pass

            battles = await asyncio.to_thread(db.get_recent_battle_messages, user_id, 5)
            freetalks = await asyncio.to_thread(db.get_recent_freetalk_messages, user_id, 3)

            if not battles and not freetalks:
                continue

            learning_iso = p.get("learning_language") or "en"
            from config import ISO_TO_LANG_KEY
            learning_key = ISO_TO_LANG_KEY.get(learning_iso, "english")

            result = await asyncio.to_thread(
                ai.update_language_profile_from_sessions,
                user_id, learning_key, battles, freetalks,
            )

            for dim, label in (result.get("language") or {}).items():
                await asyncio.to_thread(db.upsert_language_dimension, user_id, dim, label)
            for dim, label in (result.get("communication") or {}).items():
                await asyncio.to_thread(db.upsert_communication_dimension, user_id, dim, label)

            if result.get("summary"):
                await asyncio.to_thread(
                    db.add_language_profile_update,
                    user_id, result["summary"], result.get("insight", ""),
                )
        except Exception as e:
            logger.warning("Language profile update failed для %s: %s", user_id, e)


# ==================================================================
# ЗАПУСК
# ==================================================================

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Пуш — в DAILY_PUSH_HOUR
    app.job_queue.run_daily(send_daily_pushes, time=dt_time(hour=DAILY_PUSH_HOUR, minute=0))
    # Language Profile — на час позже
    app.job_queue.run_daily(
        daily_language_profile_update,
        time=dt_time(hour=(DAILY_PUSH_HOUR + 1) % 24, minute=0),
    )

    # --- Команды ---
    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("arena", intro.enter_arena_menu))
    app.add_handler(CommandHandler("profile", profile.profile_command))
    app.add_handler(CommandHandler("achievements", profile.achievements_command))

    # --- Меню ---
    app.add_handler(CallbackQueryHandler(start.show_main_menu,  pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(profile.my_arena,      pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(profile.my_language_profile, pattern="^menu_language_profile$"))
    app.add_handler(CallbackQueryHandler(profile.my_arsenal,    pattern="^menu_arsenal$"))
    app.add_handler(CallbackQueryHandler(profile.achievements_callback, pattern="^menu_achievements$"))
    app.add_handler(CallbackQueryHandler(settings.settings_menu, pattern="^menu_settings$"))

    # --- Настройки ---
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

    # --- Arsenal ---
    app.add_handler(CallbackQueryHandler(arena.arsenal_add_pending, pattern="^arsenal_add_pending$"))

    # --- Текст / голос ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, arena.handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice.handle_voice_message))

    logger.info("ARENA запущена")
    app.run_polling()


if __name__ == "__main__":
    main()