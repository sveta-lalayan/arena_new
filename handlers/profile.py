"""
handlers/profile.py — MY ARENA, MY ARSENAL, LANGUAGE PROFILE, достижения.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import gamification
import i18n
from config import LANGUAGE_DISPLAY, LANGUAGE_FLAGS
from game_data import (
    BADGES, PERSONALITIES, SKILL_TO_PERSONALITY,
    COMMUNICATION_SKILLS, CRITERIA_LABELS_RU,
)
from handlers.ui import send_or_edit, esc


def _label_lang(iso: str) -> str:
    return f"{LANGUAGE_FLAGS.get(iso, '')} {LANGUAGE_DISPLAY.get(iso, iso)}".strip()


def _back_keyboard(il: str, back_cb: str = "back_to_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data=back_cb)],
    ])


# ==================================================================
# MY ARENA
# ==================================================================

def _pick_current_challenge(user_id: int) -> tuple[str, str]:
    criteria = db.get_criteria(user_id)
    communication = {k: v for k, v in criteria.items() if k in COMMUNICATION_SKILLS}
    if communication:
        weakest = min(communication, key=communication.get)
        return weakest, CRITERIA_LABELS_RU.get(weakest, weakest)

    analysis = db.get_latest_arena_analysis(user_id) or {}
    weakest = analysis.get("weakest_skill") or "clarity"
    return weakest, CRITERIA_LABELS_RU.get(weakest, weakest)


def _pick_strength(user_id: int) -> str:
    criteria = db.get_criteria(user_id)
    if not criteria:
        return ""
    strongest = max(criteria, key=criteria.get)
    return CRITERIA_LABELS_RU.get(strongest, strongest)


def _challenge_hint(skill_key: str, il: str) -> str:
    person_key = SKILL_TO_PERSONALITY.get(skill_key)
    if not person_key or person_key not in PERSONALITIES:
        return ""
    person = PERSONALITIES[person_key]
    if il == "ru":
        return f"Следующий оппонент — {person['short_name']}: он(а) давит именно на это."
    return f"Next opponent — {person['short_name']}: they will press exactly on this."


def _build_my_arena_text(user_id: int, first_name: str, il: str) -> str:
    stats = db.get_user_stats(user_id)
    il_code = db.get_interface_language(user_id)
    ll_code = db.get_learning_language(user_id)
    cefr = db.get_current_level(user_id) or "—"

    lines = [f"🏛 <b>{esc(i18n.t(il, 'MY_ARENA.TITLE'))}</b>"]

    lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.PROFILE'))}</b>")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.NAME'))}: <b>{esc(first_name or '')}</b>")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.INTERFACE_LANGUAGE'))}: {esc(_label_lang(il_code))}")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.LEARNING_LANGUAGE'))}: {esc(_label_lang(ll_code))}")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.LEVEL'))}: <b>{esc(cefr)}</b>")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.BATTLES'))}: {stats['games_played']}")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.VICTORIES'))}: {stats['wins']}")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.CHARACTERS'))}: "
                 f"{len(stats['unique_personalities'])} / {len(PERSONALITIES)}")

    interests = db.get_interests(user_id)
    if interests:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.WHAT_ARENA_KNOWS'))}</b>")
        for t in interests[:6]:
            lines.append(f"  • {esc(t)}")

    skill_key, skill_human = _pick_current_challenge(user_id)
    lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.CURRENT_CHALLENGE'))}</b>")
    lines.append(f"  <b>{esc(skill_human.upper())}</b>")
    hint = _challenge_hint(skill_key, il)
    if hint:
        lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.HOW_WE_TRAIN'))}: {esc(hint)}")

    strength = _pick_strength(user_id)
    if strength:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.YOUR_STRENGTH'))}</b>")
        lines.append(f"  ✅ {esc(strength)}")

    sessions = stats.get("last_sessions", [])[:5]
    if sessions:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.BATTLE_HISTORY'))}</b>")
        for s in sessions:
            person_key = s["personality"] if "personality" in s.keys() else ""
            person = PERSONALITIES.get(person_key, {})
            name = person.get("short_name", person_key)
            won = bool(s["won"]) if "won" in s.keys() else False
            state = "🏆" if won else "💀"
            topic = s["topic"] if "topic" in s.keys() else ""
            lines.append(f"  {state} {esc(name)} — {esc(topic or '—')}")

    return "\n".join(lines)


async def my_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    user = update.effective_user

    text = _build_my_arena_text(user_id, user.first_name or "", il)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Language Profile", callback_data="menu_language_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])
    await send_or_edit(update, text, reply_markup=kb, parse_mode="HTML")


# ==================================================================
# MY ARSENAL
# ==================================================================

def _build_arsenal_text(user_id: int, il: str) -> str:
    weapons = db.get_weapons(user_id)
    lines = [f"🧰 <b>{esc(i18n.t(il, 'ARSENAL.TITLE'))}</b>"]

    if weapons:
        for w in weapons[:15]:
            tier_mark = "⚔️" * min(3, max(1, w.get("tier", 1)))
            lines.append(f"\n{tier_mark} <b>{esc(w['name'].upper())}</b>")
            if w.get("what_it_does"):
                lines.append(f"<i>{esc(w['what_it_does'])}</i>")
        return "\n".join(lines)

    items = db.get_arsenal(user_id)
    if not items:
        lines.append(f"\n{esc(i18n.t(il, 'ARSENAL.EMPTY'))}")
        return "\n".join(lines)

    for it in items[:15]:
        label = it.get("label") or it.get("content", "")
        if not label:
            continue
        lines.append(f"\n⚔️ <b>{esc(label.upper())}</b>")
        if it.get("description"):
            lines.append(f"<i>{esc(it['description'])}</i>")
        if it.get("language_upgrade"):
            lines.append(f"🗣 {esc(it['language_upgrade'])}")
        if it.get("soft_skill"):
            lines.append(esc(it["soft_skill"]))

    return "\n".join(lines)


async def my_arsenal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    text = _build_arsenal_text(user_id, il)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])
    await send_or_edit(update, text, reply_markup=kb, parse_mode="HTML")


# ==================================================================
# LANGUAGE PROFILE
# ==================================================================

_LABEL_EMOJI = {
    "strong": "🟢",
    "improving": "🟢",
    "developing": "🟡",
    "emerging": "🟡",
    "inconsistent": "🟠",
    "needs_attention": "🔴",
}


def _dim_line(name: str, data: dict) -> str:
    label = (data.get("label") or "").lower()
    icon = _LABEL_EMOJI.get(label, "⚪")
    pretty = name.replace("_", " ")
    return f"  {icon} {esc(pretty)}: <b>{esc(label.upper() or '—')}</b>"


async def my_language_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)

    lang = db.get_language_profile(user_id)
    comm = db.get_communication_profile(user_id)

    lines = ["🧠 <b>LANGUAGE PROFILE</b>"]

    if not lang and not comm:
        lines.append(
            "\nNot enough data yet. ARENA updates this once every 24 hours "
            "based on your battles and free conversations."
        )
    else:
        if lang:
            lines.append("\n<b>LANGUAGE</b>")
            for dim, data in lang.items():
                lines.append(_dim_line(dim, data))
        if comm:
            lines.append("\n<b>COMMUNICATION</b>")
            for dim, data in comm.items():
                lines.append(_dim_line(dim, data))

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])
    await send_or_edit(update, "\n".join(lines), reply_markup=kb, parse_mode="HTML")


# ==================================================================
# ДОСТИЖЕНИЯ
# ==================================================================

def _build_achievements_text(user_id: int, il: str) -> str:
    stats = db.get_user_stats(user_id)
    unlocked = set(stats["achievements"])
    lines = [f"🏆 <b>{esc(i18n.t(il, 'MENU.ACHIEVEMENTS'))}</b>", ""]
    for key, badge in BADGES.items():
        mark = "✅" if key in unlocked else "⬜"
        lines.append(f"{mark} {esc(badge['name'])} — {esc(badge['description'])}")
    return "\n".join(lines)


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    text = _build_achievements_text(user_id, il)
    await update.message.reply_text(text,
                                    reply_markup=_back_keyboard(il),
                                    parse_mode="HTML")


async def achievements_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    text = _build_achievements_text(user_id, il)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])
    await send_or_edit(update, text, reply_markup=kb, parse_mode="HTML")


# ==================================================================
# /profile — алиас на my_arena
# ==================================================================

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_arena(update, context)


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_arena(update, context)