"""
discovery.py — фоновый движок ARENA Discovery.

Раз в 2 часа проходит по активным пользователям, смотрит на свежие evidence
из Temple / Free Talk / Battle и — если есть что-то достойное внимания —
отправляет ОДНУ короткую нотификацию.

Правила:
  • evidence-first: discovery рождается из реальных цитат.
  • Cooldown 3 часа, максимум 2 в день.
  • Ротация kind — не повторяем последний отправленный тип.
  • Тихая работа — тоже валидный результат.
"""
import asyncio
import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import ai
import database as db
import i18n
from config import ISO_TO_LANG_KEY

logger = logging.getLogger(__name__)

COOLDOWN_HOURS = 3
MAX_PER_DAY = 2


def _hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600


async def run_discovery_cycle(context) -> None:
    """Один полный проход по всем пользователям."""
    try:
        profiles = await asyncio.to_thread(db.get_all_push_profiles)
    except Exception:
        logger.exception("discovery: get_all_push_profiles упал")
        return

    for p in profiles:
        user_id = p["telegram_id"]
        try:
            await _process_user(context, user_id, p)
        except Exception:
            logger.exception("discovery: обработка %s упала", user_id)


async def _process_user(context, user_id: int, profile: dict) -> None:
    state = await asyncio.to_thread(db.get_notification_state, user_id)
    today = datetime.now(timezone.utc).date().isoformat()

    if state.get("last_sent_at"):
        h = _hours_since(state["last_sent_at"])
        if h is not None and h < COOLDOWN_HOURS:
            return
    if state.get("last_day") == today and (state.get("sent_today_count") or 0) >= MAX_PER_DAY:
        return

    evidence = await asyncio.to_thread(db.get_recent_evidence, user_id, 48, 40)
    if not evidence:
        return

    patterns = await asyncio.to_thread(
        db.get_patterns, user_id, ("confirmed", "improving", "emerging"))
    cr = await asyncio.to_thread(db.get_current_read, user_id)
    unsolved = await asyncio.to_thread(db.get_unsolved, user_id, 5)
    interests = await asyncio.to_thread(db.get_interest_clusters, user_id, 5)

    current_read_text = (cr or {}).get("read_text", "")
    unsolved_questions = [q["question"] for q in unsolved]
    interest_labels = [c["cluster"] for c in interests]

    recent_notifs = await asyncio.to_thread(db.get_recent_notifications, user_id, 4)
    last_kinds = [n["type"] for n in recent_notifs if n.get("type")]

    learning_iso = profile.get("learning_language") or "en"
    language = ISO_TO_LANG_KEY.get(learning_iso, "english")
    level = await asyncio.to_thread(db.get_current_level, user_id) or "B1"

    result = await asyncio.to_thread(
        ai.generate_discovery,
        evidence, patterns, current_read_text, unsolved_questions,
        interest_labels, last_kinds, language, level,
    )
    if not result:
        return

    if last_kinds and last_kinds[0] == result["kind"]:
        return

    evidence_refs = [e for e in evidence if e["id"] in (result.get("evidence_ids") or [])]
    discovery_id = await asyncio.to_thread(
        db.log_discovery, user_id, result["kind"], result["headline"], result["body"],
        [{"id": e["id"], "quote": e["text_excerpt"]} for e in evidence_refs],
    )

    il = db.get_interface_language(user_id)
    text = f"<b>{result['headline']}</b>\n\n{result['body']}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"),
                              callback_data=f"open_arena_from_discovery:{discovery_id}")],
    ])
    try:
        await context.bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        logger.exception("discovery: не смог отправить %s", user_id)
        return

    await asyncio.to_thread(db.bump_notification_state, user_id, result["kind"])
    await asyncio.to_thread(db.mark_discovery_shown, discovery_id, user_id)
    await asyncio.to_thread(db.log_notification, user_id, result["kind"], result["body"])


def schedule_discovery(app, interval_hours: int = 2) -> None:
    app.job_queue.run_repeating(
        run_discovery_cycle,
        interval=interval_hours * 3600,
        first=300,
        name="discovery_cycle",
    )