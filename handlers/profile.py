"""
handlers/profile.py — MY ARENA, MY ARSENAL, достижения.
"""
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import i18n
from config import LANGUAGE_DISPLAY, LANGUAGE_FLAGS, CHANNEL_URL
from game_data import (
    BADGES, PERSONALITIES, ARSENAL_TOOLS, CRITERIA_LABELS_RU,
)
from handlers.ui import send_or_edit, esc, progress_bar


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
    patterns = db.get_patterns(user_id, ("confirmed", "improving"))
    growth = [p for p in patterns if p["kind"] == "growth"]
    if growth:
        cat = growth[0]["category"]
        return cat, CRITERIA_LABELS_RU.get(cat, cat)

    last = db.get_last_session(user_id)
    if last and last["debrief"].get("next_target"):
        cat = last["debrief"]["next_target"]
        return cat, CRITERIA_LABELS_RU.get(cat, cat)

    criteria = db.get_criteria(user_id)
    from game_data import COMMUNICATION_SKILLS
    comm = {k: v for k, v in criteria.items() if k in COMMUNICATION_SKILLS}
    if comm:
        weakest = min(comm, key=comm.get)
        return weakest, CRITERIA_LABELS_RU.get(weakest, weakest)

    analysis = db.get_latest_arena_analysis(user_id) or {}
    weakest = analysis.get("weakest_skill") or "clarity"
    return weakest, CRITERIA_LABELS_RU.get(weakest, weakest)


def _build_my_arena_text(user_id: int, first_name: str, il: str) -> str:
    stats = db.get_user_stats(user_id)
    il_code = db.get_interface_language(user_id)
    ll_code = db.get_learning_language(user_id)
    cefr = db.get_current_level(user_id) or "—"

    lines = [f"🏛 <b>{esc(i18n.t(il, 'MY_ARENA.TITLE'))}</b>"]

    lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.PROFILE'))}</b>")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.NAME'))}: <b>{esc(first_name or '')}</b>")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.LEARNING_LANGUAGE'))}: {esc(_label_lang(ll_code))}")
    lines.append(f"  {esc(i18n.t(il, 'MY_ARENA.LEVEL'))}: <b>{esc(cefr)}</b>")
    lines.append(
        f"  {esc(i18n.t(il, 'MY_ARENA.BATTLES'))}: {stats['games_played']} · "
        f"{esc(i18n.t(il, 'MY_ARENA.VICTORIES'))}: {stats['wins']}"
    )

    patterns = db.get_patterns(user_id, ("confirmed", "improving"))
    strengths = [p for p in patterns if p["kind"] == "strength"]
    if strengths:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.WHAT_IVE_SEEN'))}</b>")
        for p in strengths[:3]:
            lines.append(f"  ✅ {esc(i18n.t(il, 'PATTERNS.' + p['pattern_id']))}")

    skill_key, skill_human = _pick_current_challenge(user_id)
    focus_line = f"<b>{esc(skill_human.upper())}</b>"
    last = db.get_last_session(user_id)
    if last and last["debrief"].get("cost"):
        focus_line += f"\n  <i>{esc(last['debrief']['cost'])}</i>"
    lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.TESTING_NOW'))}</b>")
    lines.append(f"  {focus_line}")

    clusters = db.get_interest_clusters(user_id, limit=6)
    real_interests = [c for c in clusters if c["count"] >= 2]
    if real_interests:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.WHAT_ARENA_KNOWS'))}</b>")
        for c in real_interests[:4]:
            ex = c["examples"][-1] if c["examples"] else ""
            if ex:
                lines.append(f"  • <b>{esc(c['cluster'])}</b> — «{esc(ex)}»")
            else:
                lines.append(f"  • {esc(c['cluster'])}")

    tool_key = db.get_last_unlocked_tool(user_id)
    if tool_key:
        name = i18n.t(il, f"TOOLS.{tool_key}.NAME")
        emoji = next((t["emoji"] for t in ARSENAL_TOOLS if t["key"] == tool_key), "⚔️")
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.CURRENT_WEAPON'))}</b>")
        lines.append(f"  {emoji} <b>{esc(name.upper())}</b>")

    sessions = stats.get("last_sessions", [])[:5]
    if sessions:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.BATTLE_HISTORY'))}</b>")
        for s in sessions:
            person_key = s["personality"]
            person = PERSONALITIES.get(person_key, {})
            name = person.get("short_name", person_key)
            won = bool(s["won"])
            state = "🏆" if won else "💀"
            try:
                debrief = json.loads(s["debrief_json"]) if s["debrief_json"] else {}
            except (ValueError, TypeError):
                debrief = {}
            line = s["mission"] or debrief.get("win_move") or s["topic"] or "—"
            lines.append(f'  {state} <b>{esc(name)}</b> — «{esc(line)}»')

    return "\n".join(lines)


async def my_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    user = update.effective_user

    text = _build_my_arena_text(user_id, user.first_name or "", il)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])
    await send_or_edit(update, text, reply_markup=kb, parse_mode="HTML")


my_language_profile = my_arena


# ==================================================================
# MY ARSENAL
# ==================================================================

def _build_arsenal_text(user_id: int, il: str) -> str:
    unlocked = db.get_unlocked_tools(user_id)
    total = len(ARSENAL_TOOLS)
    lines = [f"🧰 <b>{esc(i18n.t(il, 'ARSENAL.TITLE'))}</b>"]

    bar = progress_bar(len(unlocked), total)
    lines.append(f"\n{bar}  <b>{len(unlocked)}/{total}</b>")

    phrases = db.get_grammar_phrases(user_id, limit=40)

    if not unlocked and not phrases:
        lines.append(f"\n<i>{esc(i18n.t(il, 'ARSENAL.EMPTY'))}</i>")
        lines.append(f"\n📣 <i>{esc(i18n.t(il, 'ARSENAL.CHANNEL_HINT'))}</i>")
        return "\n".join(lines)

    # Фразы под цели (из debrief grammar_for_goal)
    if phrases:
        by_goal: dict[str, list[str]] = {}
        for p in phrases:
            by_goal.setdefault(p["goal"], []).append(p["phrase"])
        lines.append(f"\n📐 <b>{esc(i18n.t(il, 'ARSENAL.PHRASES_SECTION'))}</b>")
        for goal, plist in list(by_goal.items())[:4]:
            goal_label = i18n.t(il, f"CRITERIA.{goal}") if goal else goal
            lines.append(f"\n<b>{esc(goal_label.upper())}</b>")
            for p in plist[:4]:
                lines.append(f"  • «{esc(p)}»")

    # 8 фиксированных приёмов — только заработанные
    for tool in ARSENAL_TOOLS:
        key, emoji = tool["key"], tool["emoji"]
        if key not in unlocked:
            continue
        name = i18n.t(il, f"TOOLS.{key}.NAME")
        desc = i18n.t(il, f"TOOLS.{key}.DESC")
        example = i18n.t(il, f"TOOLS.{key}.EXAMPLE")
        lines.append(f"\n{emoji} <b>{esc(name)}</b>")
        lines.append(f"<i>{esc(desc)}</i>")
        lines.append(f"💬 {esc(example)}")

    remaining = total - len(unlocked)
    if remaining > 0:
        lines.append(f"\n✨ <i>{esc(i18n.t(il, 'ARSENAL.MORE_TO_EARN', n=remaining))}</i>")

    lines.append(f"\n📣 <i>{esc(i18n.t(il, 'ARSENAL.CHANNEL_HINT'))}</i>")
    return "\n".join(lines)


async def my_arsenal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    text = _build_arsenal_text(user_id, il)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "ARSENAL.CHANNEL_BUTTON"), url=CHANNEL_URL)],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])
    await send_or_edit(update, text, reply_markup=kb, parse_mode="HTML")


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


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_arena(update, context)


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_arena(update, context)