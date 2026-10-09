"""
personalization.py — единый слой Personalization Memory + выбор ежедневного напоминания.
"""
import logging
import random
from datetime import datetime, timezone

import ai
import database as db
from game_data import (
    ARSENAL_TOOL_DEFS, COMMUNICATION_SKILLS, PERSONALITIES, SKILL_TO_PERSONALITY,
    ARENA_SIGNALS,
)

logger = logging.getLogger(__name__)

TOPIC_TAXONOMY = [
    "Technology & AI",
    "Business & entrepreneurship",
    "Leadership & career",
    "Money & economy",
    "Travel & places",
    "Culture & media",
    "Language & communication",
    "Psychology & relationships",
    "Health & lifestyle",
    "Society & politics",
    "Science & education",
    "Food, sport & hobbies",
]

PATTERN_CATALOG = {
    "repeats_claim": {
        "kind": "growth", "category": "argumentation",
        "brief": "When challenged, repeats the same claim instead of adding a new reason, example or angle."},
    "claims_without_evidence": {
        "kind": "growth", "category": "evidence",
        "brief": "States strong claims without an example, number or source."},
    "agrees_too_quickly": {
        "kind": "growth", "category": "control",
        "brief": "Gives in or agrees too quickly when pushed, instead of holding or redirecting."},
    "imprecise_vocabulary": {
        "kind": "growth", "category": "vocabulary",
        "brief": "Uses general or approximate words where a more precise word would carry the idea better."},
    "develops_argument": {
        "kind": "strength", "category": "argumentation", "counter_of": "repeats_claim",
        "brief": "When challenged, adds a NEW reason, example or angle instead of repeating the claim."},
    "backs_claims_with_evidence": {
        "kind": "strength", "category": "evidence", "counter_of": "claims_without_evidence",
        "brief": "Backs claims with a concrete example, number or source."},
    "holds_position": {
        "kind": "strength", "category": "control", "counter_of": "agrees_too_quickly",
        "brief": "Holds or smartly redirects the position under pressure instead of giving in."},
    "uses_precise_vocabulary": {
        "kind": "strength", "category": "vocabulary", "counter_of": "imprecise_vocabulary",
        "brief": "Chooses precise, specific words for the idea."},
    "states_position_clearly": {
        "kind": "strength", "category": "clarity",
        "brief": "States own position clearly and directly."},
    "tells_vivid_stories": {
        "kind": "strength", "category": "fluency",
        "brief": "Tells vivid, concrete, memorable stories or anecdotes."},
    "adapts_argument": {
        "kind": "strength", "category": "adaptability",
        "brief": "Changes the angle or tone of an argument to fit the other person."},
    "has_professional_context": {
        "kind": "strength", "category": "clarity",
        "brief": "Has a clear professional context they keep referring to."},
    "states_goals": {
        "kind": "strength", "category": "clarity",
        "brief": "Openly states what they want to get better at."},
    "avoids_topic": {
        "kind": "growth", "category": "adaptability",
        "brief": "Steps away from or redirects a topic they clearly don't want to discuss."},
}

ALL_PATTERNS = {**PATTERN_CATALOG, **ARENA_SIGNALS}

MIN_LINES_FOR_PATTERNS = 3


def record_session(user_id: int, source: str, user_lines: list[str], language: str) -> dict:
    lines = [l.strip() for l in (user_lines or []) if isinstance(l, str) and len(l.strip()) >= 3]
    if not lines:
        return {"topics": 0, "patterns": 0, "goals": 0}

    signals = ai.extract_signals(lines, language, source, TOPIC_TAXONOMY, ALL_PATTERNS)
    topics = signals.get("topics") or []
    patterns = signals.get("patterns") or []

    if topics:
        db.record_interest_clusters(user_id, topics)

    applied = 0
    if len(lines) >= MIN_LINES_FOR_PATTERNS:
        for p in patterns:
            meta = ALL_PATTERNS[p["id"]]
            category = meta.get("category", "communication")
            db.observe_pattern(
                user_id, p["id"], category, meta["kind"],
                p.get("example", ""), meta.get("counter_of"),
                display_name=p["id"],
            )
            applied += 1

    if signals.get("professional_context"):
        db.set_professional_context(user_id, signals["professional_context"])

    for g in signals.get("goals") or []:
        db.add_goal(user_id, g)

    for a in signals.get("avoids") or []:
        db.add_avoids(user_id, a)

    return {"topics": len(topics), "patterns": applied,
            "goals": len(signals.get("goals") or [])}


REMINDER_TYPES = (
    "interest_hook", "challenge_hook", "arsenal_hook", "debrief_hook",
    "continuation", "provocative_question", "battle_invitation", "language_hook",
    "goal_hook", "context_hook",
)

_WEIGHTS = {
    "continuation": 3, "debrief_hook": 3, "arsenal_hook": 2, "interest_hook": 2,
    "challenge_hook": 2, "language_hook": 2, "provocative_question": 1, "battle_invitation": 1,
    "goal_hook": 3, "context_hook": 2,
}
NO_REPEAT_LAST_TYPES = 3
REF_WINDOW = 7


def _days_ago(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt).days)


def _when(days: int | None) -> str:
    if days is None:
        return ""
    return f" (days ago: {days})"


def _pick_focus(user_id: int, patterns: list[dict], last: dict | None) -> str:
    growth = [p for p in patterns if p["kind"] == "growth" and p["status"] in ("confirmed", "improving")]
    if growth:
        return growth[0]["category"]

    if last and last["debrief"].get("next_target") and (_days_ago(last["created_at"]) or 0) <= 14:
        return last["debrief"]["next_target"]

    criteria = db.get_criteria(user_id)
    comm = {k: v for k, v in criteria.items() if k in COMMUNICATION_SKILLS}
    if comm:
        return min(comm, key=comm.get)
    return ""


def build_context(user_id: int) -> dict:
    last = db.get_last_session(user_id)
    patterns = db.get_patterns(user_id, ("emerging", "confirmed", "improving"))
    focus = _pick_focus(user_id, patterns, last)
    return {
        "level": db.get_current_level(user_id) or "B1",
        "clusters": db.get_interest_clusters(user_id),
        "patterns": patterns,
        "tools": sorted(db.get_unlocked_tools(user_id)),
        "last_battle": last,
        "last_freetalk": db.get_last_freetalk(user_id),
        "focus": focus,
        "professional_context": db.get_professional_context(user_id),
        "goals": db.get_goals(user_id),
        "avoids": db.get_avoids(user_id),
    }


def select_reminder(user_id: int, rng: random.Random | None = None) -> dict | None:
    rng = rng or random
    ctx = build_context(user_id)
    recent = db.get_recent_notifications(user_id, REF_WINDOW)

    last_types = {n["type"] for n in recent[:NO_REPEAT_LAST_TYPES]}
    used_interest = {(n["referenced_interest"] or "").lower() for n in recent if n["referenced_interest"]}
    used_pattern = {n["referenced_pattern"] for n in recent if n["referenced_pattern"]}
    used_battle = {n["referenced_battle"] for n in recent if n["referenced_battle"]}
    used_tool = {n["referenced_arsenal_item"] for n in recent if n["referenced_arsenal_item"]}

    last = ctx["last_battle"]
    cand: dict[str, dict] = {}

    fresh_clusters = [c for c in ctx["clusters"] if c["cluster"].lower() not in used_interest and c["examples"]]
    if fresh_clusters:
        c = fresh_clusters[0]
        ex = c["examples"][-1]
        d = _days_ago(c["last_seen_at"])
        recurring = c["count"] >= 2
        facts = [f"Interest area: {c['cluster']}{' (they keep coming back to it)' if recurring else ''}.",
                 f"What they actually talked about: \"{ex}\"{_when(d)}."]
        cand["interest_hook"] = {"facts": facts, "interest": c["cluster"], "topic": ex}
        c2 = fresh_clusters[1] if len(fresh_clusters) > 1 else c
        ex2 = c2["examples"][-1]
        cand["provocative_question"] = {
            "facts": [f"Interest area: {c2['cluster']}.", f"What they talked about: \"{ex2}\"."],
            "interest": c2["cluster"], "topic": ex2}

    ft = ctx["last_freetalk"]
    options = []
    if ft and (_days_ago(ft["created_at"]) or 99) <= 3:
        options.append((ft["created_at"], ft["topic"], None, "free conversation"))
    if last and last["topic"] and (_days_ago(last["created_at"]) or 99) <= 3 and last["id"] not in used_battle:
        options.append((last["created_at"], last["topic"], last["id"], "battle"))
    if options:
        options.sort(key=lambda o: o[0], reverse=True)
        created, topic, battle_id, kind = options[0]
        if topic.lower() not in used_interest:
            cand["continuation"] = {
                "facts": [f"Recent {kind} topic: \"{topic}\"{_when(_days_ago(created))}."],
                "topic": topic, "battle": battle_id, "interest": topic}

    if last and last["id"] not in used_battle and (_days_ago(last["created_at"]) or 99) <= 7:
        dj = last["debrief"]
        if dj.get("cost"):
            opp = PERSONALITIES.get(last["personality"], {}).get("short_name", "the opponent")
            facts = [f"Last battle: against {opp} on \"{last['topic']}\"{_when(_days_ago(last['created_at']))}.",
                     f"What held them back there: {dj['cost']}"]
            if dj.get("next_target"):
                facts.append(f"Their next target skill: {dj['next_target']}.")
            cand["debrief_hook"] = {"facts": facts, "battle": last["id"], "topic": last["topic"]}

    for key in ctx["tools"]:
        if key not in used_tool and key in ARSENAL_TOOL_DEFS:
            cand["arsenal_hook"] = {
                "facts": [f"A move they have genuinely earned: \"{key.replace('_', ' ')}\" — "
                          f"{ARSENAL_TOOL_DEFS[key]}"],
                "arsenal": key}
            break

    if ctx["focus"]:
        facts = [f"Their current training focus: {ctx['focus']}."]
        ref = None
        for p in ctx["patterns"]:
            if (p["kind"] == "growth" and p["category"] == ctx["focus"]
                    and p["status"] in ("confirmed", "improving") and p["pattern_id"] not in used_pattern):
                facts.append(f"Confirmed over several conversations: {ALL_PATTERNS[p['pattern_id']]['brief']}")
                ref = p["pattern_id"]
                break
        cand["challenge_hook"] = {"facts": facts, "pattern": ref}

    if last and last["id"] not in used_battle and (_days_ago(last["created_at"]) or 99) <= 10:
        up = last["debrief"].get("language_upgrade") or last["debrief"].get("steal_it")
        if isinstance(up, dict) and up.get("said") and up.get("better"):
            cand["language_hook"] = {
                "facts": [f"In their last battle they said: \"{up['said']}\".",
                          f"A sharper version: \"{up['better']}\"."],
                "battle": last["id"]}
    if "language_hook" not in cand:
        for p in ctx["patterns"]:
            if (p["kind"] == "growth" and p["category"] not in COMMUNICATION_SKILLS
                    and p["pattern_id"] not in used_pattern):
                cand["language_hook"] = {
                    "facts": [f"Language gap seen across conversations: {ALL_PATTERNS[p['pattern_id']]['brief']}"],
                    "pattern": p["pattern_id"]}
                break

    if ctx["focus"] in SKILL_TO_PERSONALITY and (ctx["clusters"] or (last and last["topic"])):
        pk = SKILL_TO_PERSONALITY[ctx["focus"]]
        topic = (fresh_clusters[0]["examples"][-1] if fresh_clusters
                 else (last["topic"] if last else ""))
        if topic:
            cand["battle_invitation"] = {
                "facts": [f"Opponent waiting for them: {PERSONALITIES[pk]['short_name']} "
                          f"({PERSONALITIES[pk]['role']}).",
                          f"A topic they care about: \"{topic}\"."],
                "topic": topic, "interest": topic}

    if ctx["goals"]:
        goal = ctx["goals"][0]
        cand["goal_hook"] = {
            "facts": [f"They said they want to: {goal}."],
            "topic": "",
        }

    if ctx["professional_context"] and ctx["clusters"]:
        c = ctx["clusters"][0]
        ex = c["examples"][-1] if c["examples"] else c["cluster"]
        cand["context_hook"] = {
            "facts": [f"Their professional context: {ctx['professional_context']}.",
                      f"A topic they've engaged with: \"{ex}\"."],
            "interest": c["cluster"],
            "topic": ex,
        }

    if not cand:
        return None

    eligible = [t for t in cand if t not in last_types] or [t for t in cand if t != (recent[0]["type"] if recent else "")]
    if not eligible:
        return None
    ntype = rng.choices(eligible, weights=[_WEIGHTS[t] for t in eligible], k=1)[0]
    pick = cand[ntype]
    return {
        "type": ntype,
        "facts": pick["facts"],
        "topic": pick.get("topic", ""),
        "level": ctx["level"],
        "refs": {
            "interest": pick.get("interest"),
            "pattern": pick.get("pattern"),
            "battle": pick.get("battle"),
            "arsenal": pick.get("arsenal"),
        },
    }