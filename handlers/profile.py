"""
handlers/profile.py — MY ARENA, MY ARSENAL, достижения.

MY ARENA — живой файл ARENA о человеке:
  • CURRENT READ, ARENA SIGNALS, UNDER PRESSURE, CURRENT WEAPON,
    UNSOLVED, WHAT ARENA KNOWS, EVOLUTION.

MY ARSENAL — что человек реально научился делать:
  • 8 приёмов со статусами DISCOVERED → PRACTISING → ACQUIRED → STRONG → MASTERED;
  • фразы под коммуникационные цели со статусами и счётчиками.
"""
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import i18n
from config import LANGUAGE_DISPLAY, LANGUAGE_FLAGS, CHANNEL_URL
from game_data import (
    BADGES, PERSONALITIES, ARSENAL_TOOLS, CRITERIA_LABELS_RU, ARENA_SIGNALS,
    ARSENAL_STATUS_ORDER, ARSENAL_STATUS_EMOJI,
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

def _signal_label(il: str, pid: str) -> tuple[str, str]:
    name = i18n.t(il, f"SIGNALS.{pid}.NAME")
    if name == f"SIGNALS.{pid}.NAME":
        name = pid.upper()
    brief = i18n.t(il, f"SIGNALS.{pid}.BRIEF")
    if brief == f"SIGNALS.{pid}.BRIEF":
        brief = ARENA_SIGNALS.get(pid, {}).get("brief", "")
    return name, brief


def _build_my_arena_text(user_id: int, first_name: str, il: str) -> str:
    stats = db.get_user_stats(user_id)
    cefr = db.get_current_level(user_id) or "—"

    lines = [f"🏛 <b>{esc(i18n.t(il, 'MY_ARENA.TITLE'))}</b>"]

    cr = db.get_current_read(user_id)
    if cr and cr.get("read_text"):
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.CURRENT_READ'))}</b>")
        lines.append(f"{esc(cr['read_text'])}")
        if stats["games_played"]:
            lines.append(
                f"<i>{esc(i18n.t(il, 'MY_ARENA.BASED_ON', n=stats['games_played']))}</i>"
            )

    patterns = db.get_patterns(user_id, ("confirmed", "emerging", "improving"))
    signals = [p for p in patterns if p["pattern_id"] in ARENA_SIGNALS]
    if signals:
        signals.sort(key=lambda p: (
            ARENA_SIGNALS[p["pattern_id"]].get("kind") != "strength",
            p["status"] != "improving",
            -p["evidence_count"],
        ))
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.SIGNALS'))}</b>")
        for p in signals[:4]:
            meta = ARENA_SIGNALS.get(p["pattern_id"], {})
            kind = meta.get("kind", "pattern")
            if kind == "strength":
                mark = "✅"
            elif p["status"] == "improving":
                mark = "↗"
            else:
                mark = "🔄"
            name, brief = _signal_label(il, p["pattern_id"])
            lines.append(f"  {mark} <b>{esc(name)}</b>")
            if brief:
                lines.append(f"     <i>{esc(brief)}</i>")

    up = db.get_under_pressure(user_id)
    if up and up.get("trajectory"):
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.UNDER_PRESSURE'))}</b>")
        lines.append(f"  <i>{esc(up['trajectory'])}</i>")

    tool_key = db.get_last_unlocked_tool(user_id)
    if tool_key:
        name = i18n.t(il, f"TOOLS.{tool_key}.NAME")
        emoji = next((t["emoji"] for t in ARSENAL_TOOLS if t["key"] == tool_key), "⚔️")
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.CURRENT_WEAPON'))}</b>")
        lines.append(f"  {emoji} <b>{esc(name.upper())}</b>")

    unsolved = db.get_unsolved(user_id, limit=3)
    if unsolved:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.UNSOLVED'))}</b>")
        for q in unsolved:
            lines.append(f"  ? <i>{esc(q['question'])}</i>")

    clusters = db.get_interest_clusters(user_id, limit=6)
    real_interests = [c for c in clusters if c["count"] >= 2]
    professional = db.get_professional_context(user_id)
    if real_interests or professional:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.WHAT_ARENA_KNOWS'))}</b>")
        if real_interests:
            topics_line = " · ".join(c["cluster"] for c in real_interests[:4])
            lines.append(f"  {esc(topics_line)}")
        if professional:
            lines.append(
                f"  <i>{esc(i18n.t(il, 'MY_ARENA.CONTEXT'))}: {esc(professional)}</i>"
            )

    sessions = list(stats.get("last_sessions", []))
    if len(sessions) >= 3:
        lines.append(f"\n<b>{esc(i18n.t(il, 'MY_ARENA.EVOLUTION'))}</b>")
        picks = [sessions[i] for i in range(len(sessions) - 1, -1, -3)][:4]
        picks.reverse()
        total = len(sessions)
        for idx, s in enumerate(picks):
            battle_no = total - (idx * 3)
            try:
                debrief = json.loads(s["debrief_json"]) if s["debrief_json"] else {}
            except (ValueError, TypeError):
                debrief = {}
            line = (
                (debrief.get("arena_read") or {}).get("skill_now")
                or s["mission"]
                or s["topic"]
                or ""
            )
            if not line:
                continue
            lines.append(
                f"  <b>{esc(i18n.t(il, 'MY_ARENA.BATTLE_N', n=battle_no))}</b> — {esc(line[:140])}"
            )

    lines.append(
        f"\n<i>{esc(first_name or '')} · {esc(cefr)} · "
        f"{esc(i18n.t(il, 'MY_ARENA.BATTLES'))}: {stats['games_played']} · "
        f"{esc(i18n.t(il, 'MY_ARENA.VICTORIES'))}: {stats['wins']}</i>"
    )
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
# MY ARSENAL — что человек научился делать
# ==================================================================

def _status_label(il: str, status: str) -> str:
    label = i18n.t(il, f"ARSENAL.STATUS.{status}")
    if label == f"ARSENAL.STATUS.{status}":
        return status
    return label


def _build_arsenal_text(user_id: int, il: str) -> str:
    stats = db.get_all_tool_stats(user_id)
    phrases = db.get_grammar_phrases_with_stats(user_id, limit=60)
    total_tools = len(ARSENAL_TOOLS)

    # Сводка по статусам приёмов
    statuses = {s: 0 for s in ARSENAL_STATUS_ORDER}
    for t in stats.values():
        if t.get("uses", 0) > 0:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1

    lines = [f"🧰 <b>{esc(i18n.t(il, 'ARSENAL.TITLE'))}</b>"]

    mastered = statuses.get("mastered", 0) + statuses.get("strong", 0)
    bar = progress_bar(mastered, total_tools)
    lines.append(f"\n{bar}  <b>{mastered}/{total_tools}</b>")

    status_bits = []
    for s in ARSENAL_STATUS_ORDER:
        n = statuses.get(s, 0)
        if n:
            emoji = ARSENAL_STATUS_EMOJI[s]
            label = _status_label(il, s)
            status_bits.append(f"{emoji} {n} {label}")
    if status_bits:
        lines.append("  " + " · ".join(status_bits))

    if not stats and not phrases:
        lines.append(f"\n<i>{esc(i18n.t(il, 'ARSENAL.EMPTY'))}</i>")
        lines.append(f"\n📣 <i>{esc(i18n.t(il, 'ARSENAL.CHANNEL_HINT'))}</i>")
        return "\n".join(lines)

    # Приёмы
    for tool in ARSENAL_TOOLS:
        key, emoji = tool["key"], tool["emoji"]
        t = stats.get(key)
        if not t or t.get("uses", 0) == 0:
            continue
        status = t["status"]
        status_emoji = ARSENAL_STATUS_EMOJI.get(status, "🔍")
        status_label = _status_label(il, status)
        name = i18n.t(il, f"TOOLS.{key}.NAME")
        desc = i18n.t(il, f"TOOLS.{key}.DESC")
        example = i18n.t(il, f"TOOLS.{key}.EXAMPLE")

        lines.append(f"\n{emoji} <b>{esc(name.upper())}</b>  {status_emoji} <i>{esc(status_label)}</i>")
        lines.append(f"<i>{esc(desc)}</i>")
        lines.append(f"💬 {esc(example)}")
        lines.append(
            f"   <i>{esc(i18n.t(il, 'ARSENAL.USED_N_TIMES', n=t['uses'], w=t['wins']))}</i>"
        )

    # Фразы под цели
    if phrases:
        by_goal: dict[str, list[dict]] = {}
        for p in phrases:
            by_goal.setdefault(p["goal"], []).append(p)
        lines.append(f"\n📐 <b>{esc(i18n.t(il, 'ARSENAL.PHRASES_SECTION'))}</b>")
        for goal, plist in list(by_goal.items())[:4]:
            goal_label = i18n.t(il, f"CRITERIA.{goal}") if goal else goal
            lines.append(f"\n<b>{esc(goal_label.upper())}</b>")
            for p in plist[:4]:
                status_emoji = ARSENAL_STATUS_EMOJI.get(p["status"], "🔍")
                suffix = f" <i>×{p['uses']}</i>" if p["uses"] else ""
                lines.append(f"  {status_emoji} «{esc(p['phrase'])}»{suffix}")

    remaining = total_tools - len([t for t in stats.values() if t.get("uses", 0) > 0])
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