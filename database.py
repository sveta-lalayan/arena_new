"""
БД под ARENA: профиль, баллы, история игр, достижения, словарь ошибок,
данные для ежедневного пуша, история уровня, разбор Храма (3 слоя).
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id      INTEGER PRIMARY KEY,
    username         TEXT,
    first_name       TEXT,
    total_points     INTEGER NOT NULL DEFAULT 0,
    first_battle_done INTEGER NOT NULL DEFAULT 0,
    push_personality TEXT,
    push_topics      TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER NOT NULL,
    personality         TEXT NOT NULL,
    language            TEXT NOT NULL,
    level               TEXT NOT NULL,
    topic               TEXT NOT NULL,
    rounds_completed    INTEGER NOT NULL DEFAULT 0,
    argumentation_score INTEGER,
    vocabulary_score    INTEGER,
    grammar_score       INTEGER,
    fluency_score       INTEGER,
    points_earned       INTEGER NOT NULL DEFAULT 0,
    strength            TEXT,
    growth              TEXT,
    growth_plan         TEXT,
    created_at          TEXT NOT NULL,
    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
);

CREATE TABLE IF NOT EXISTS achievements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    badge_key     TEXT NOT NULL,
    unlocked_at   TEXT NOT NULL,
    UNIQUE (telegram_id, badge_key)
);

CREATE TABLE IF NOT EXISTS vocabulary_mistakes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    wrong         TEXT NOT NULL,
    correct       TEXT NOT NULL,
    times_seen    INTEGER NOT NULL DEFAULT 1,
    learned       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    UNIQUE (telegram_id, wrong)
);

CREATE TABLE IF NOT EXISTS user_level_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    level         TEXT NOT NULL,
    source        TEXT NOT NULL,
    session_id    INTEGER,
    created_at    TEXT NOT NULL
);

-- 3-слойный разбор Храма (LANGUAGE + COMMUNICATION + BEHAVIOUR).
-- Хранится отдельной записью, чтобы не терялся, даже если бой не состоялся.
CREATE TABLE IF NOT EXISTS arena_analyses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id      INTEGER NOT NULL,
    language_metrics TEXT,
    communication    TEXT,
    hidden_metrics   TEXT,
    grammar_weak     TEXT,
    vocabulary_weak  TEXT,
    behaviour        TEXT,
    weakest_skill    TEXT,
    strongest_skill  TEXT,
    arena_rank       TEXT,
    interests        TEXT,
    main_topic       TEXT,
    level            TEXT,
    created_at       TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        for col, ddl in [
            ("first_battle_done", "ALTER TABLE users ADD COLUMN first_battle_done INTEGER NOT NULL DEFAULT 0"),
            ("push_personality", "ALTER TABLE users ADD COLUMN push_personality TEXT"),
            ("push_topics", "ALTER TABLE users ADD COLUMN push_topics TEXT"),
        ]:
            if col not in existing_cols:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass

        existing_session_cols = {row["name"] for row in conn.execute("PRAGMA table_info(game_sessions)")}
        for col, ddl in [
            ("strength", "ALTER TABLE game_sessions ADD COLUMN strength TEXT"),
            ("growth", "ALTER TABLE game_sessions ADD COLUMN growth TEXT"),
            ("growth_plan", "ALTER TABLE game_sessions ADD COLUMN growth_plan TEXT"),
        ]:
            if col not in existing_session_cols:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_user(telegram_id: int, username: str | None, first_name: str | None) -> sqlite3.Row:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET username = ?, first_name = ?, updated_at = ? WHERE telegram_id = ?",
                (username, first_name, _now(), telegram_id),
            )
            return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()

        now = _now()
        conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, total_points, first_battle_done, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, 0, ?, ?)",
            (telegram_id, username, first_name, now, now),
        )
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def has_completed_first_battle(telegram_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT first_battle_done FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return bool(row and row["first_battle_done"])


def mark_first_battle_done(telegram_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET first_battle_done = 1, updated_at = ? WHERE telegram_id = ?",
            (_now(), telegram_id),
        )


def set_push_profile(telegram_id: int, personality: str, topics: list):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET push_personality = ?, push_topics = ?, updated_at = ? WHERE telegram_id = ?",
            (personality, json.dumps(topics, ensure_ascii=False), _now(), telegram_id),
        )


def get_all_push_profiles() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT telegram_id, push_personality, push_topics, first_name FROM users "
            "WHERE push_personality IS NOT NULL"
        ).fetchall()
    result = []
    for row in rows:
        topics = json.loads(row["push_topics"]) if row["push_topics"] else []
        result.append({
            "telegram_id": row["telegram_id"],
            "personality": row["push_personality"],
            "topics": topics,
            "first_name": row["first_name"] or "",
        })
    return result


def add_points(telegram_id: int, points: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET total_points = total_points + ?, updated_at = ? WHERE telegram_id = ?",
            (points, _now(), telegram_id),
        )


def save_game_session(
        telegram_id: int, personality: str, language: str, level: str, topic: str,
        rounds_completed: int, scores: dict, points_earned: int,
        strength: str = "", growth: str = "", growth_plan: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO game_sessions
               (telegram_id, personality, language, level, topic, rounds_completed,
                argumentation_score, vocabulary_score, grammar_score, fluency_score,
                points_earned, strength, growth, growth_plan, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id, personality, language, level, topic, rounds_completed,
                scores.get("argumentation"), scores.get("vocabulary"),
                scores.get("grammar"), scores.get("fluency"),
                points_earned, strength, growth, growth_plan, _now(),
            ),
        )
        return cur.lastrowid


def get_user_stats(telegram_id: int) -> dict:
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        sessions = conn.execute(
            "SELECT * FROM game_sessions WHERE telegram_id = ? ORDER BY created_at DESC", (telegram_id,)
        ).fetchall()
        achievements = conn.execute(
            "SELECT badge_key FROM achievements WHERE telegram_id = ?", (telegram_id,)
        ).fetchall()

    total_points = user["total_points"] if user else 0
    games_played = len(sessions)
    unique_personalities = {s["personality"] for s in sessions}
    avg_score = None
    if sessions:
        scored = [
            s for s in sessions
            if s["argumentation_score"] is not None and s["grammar_score"] is not None
               and s["vocabulary_score"] is not None and s["fluency_score"] is not None
        ]
        if scored:
            avg_score = round(
                sum(
                    (s["argumentation_score"] + s["vocabulary_score"] + s["grammar_score"] + s["fluency_score"]) / 4
                    for s in scored
                ) / len(scored)
            )

    latest = sessions[0] if sessions else None

    return {
        "total_points": total_points,
        "games_played": games_played,
        "unique_personalities": unique_personalities,
        "avg_score": avg_score,
        "achievements": [a["badge_key"] for a in achievements],
        "last_sessions": sessions[:5],
        "latest_strength": latest["strength"] if latest else "",
        "latest_growth": latest["growth"] if latest else "",
        "latest_growth_plan": latest["growth_plan"] if latest else "",
    }


def unlock_achievement(telegram_id: int, badge_key: str) -> bool:
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO achievements (telegram_id, badge_key, unlocked_at) VALUES (?, ?, ?)",
                (telegram_id, badge_key, _now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


# ---------- Словарь слов для заучивания ----------

def add_vocabulary_mistakes(telegram_id: int, mistakes: list[dict]):
    if not mistakes:
        return
    with get_conn() as conn:
        for m in mistakes:
            existing = conn.execute(
                "SELECT id, times_seen FROM vocabulary_mistakes WHERE telegram_id = ? AND wrong = ?",
                (telegram_id, m["wrong"]),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE vocabulary_mistakes SET times_seen = times_seen + 1 WHERE id = ?",
                    (existing["id"],),
                )
            else:
                conn.execute(
                    "INSERT INTO vocabulary_mistakes (telegram_id, wrong, correct, times_seen, learned, created_at) "
                    "VALUES (?, ?, ?, 1, 0, ?)",
                    (telegram_id, m["wrong"], m["correct"], _now()),
                )


def get_vocabulary_to_learn(telegram_id: int, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT wrong, correct, times_seen FROM vocabulary_mistakes "
            "WHERE telegram_id = ? AND learned = 0 ORDER BY times_seen DESC LIMIT ?",
            (telegram_id, limit),
        ).fetchall()
    return [{"wrong": r["wrong"], "correct": r["correct"], "times_seen": r["times_seen"]} for r in rows]


# ---------- История уровня и мягкая адаптация ----------

def add_level_snapshot(telegram_id: int, level: str, source: str, session_id: int | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_level_history (telegram_id, level, source, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (telegram_id, level, source, session_id, _now()),
        )


def get_current_level(telegram_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT level FROM user_level_history WHERE telegram_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()
    return row["level"] if row else None


def get_recent_avg_scores(telegram_id: int, n: int = 3) -> float | None:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT argumentation_score, vocabulary_score, grammar_score, fluency_score "
            "FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
            (telegram_id, n),
        ).fetchall()
    if not rows:
        return None
    vals = []
    for r in rows:
        s = [r["argumentation_score"], r["vocabulary_score"], r["grammar_score"], r["fluency_score"]]
        s = [v for v in s if v is not None]
        if s:
            vals.append(sum(s) / len(s))
    return sum(vals) / len(vals) if vals else None


# ---------- 3-слойный разбор Храма ----------

def save_arena_analysis(telegram_id: int, analysis: dict):
    """Сохраняет разбор Храма (LANGUAGE + COMMUNICATION + BEHAVIOUR)."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO arena_analyses
               (telegram_id, language_metrics, communication, hidden_metrics,
                grammar_weak, vocabulary_weak, behaviour, weakest_skill,
                strongest_skill, arena_rank, interests, main_topic, level, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id,
                json.dumps(analysis.get("language", {}), ensure_ascii=False),
                json.dumps(analysis.get("communication", {}), ensure_ascii=False),
                json.dumps(analysis.get("hidden", {}), ensure_ascii=False),
                json.dumps(analysis.get("grammar_weak_areas", []), ensure_ascii=False),
                json.dumps(analysis.get("vocabulary_weak_areas", []), ensure_ascii=False),
                analysis.get("behaviour", ""),
                analysis.get("weakest_skill", ""),
                analysis.get("strongest_skill", ""),
                json.dumps(analysis.get("arena_rank", {}), ensure_ascii=False),
                json.dumps(analysis.get("interests", []), ensure_ascii=False),
                analysis.get("main_topic", ""),
                analysis.get("estimated_level", ""),
                _now(),
            ),
        )


def get_latest_arena_analysis(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM arena_analyses WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "language": json.loads(row["language_metrics"] or "{}"),
        "communication": json.loads(row["communication"] or "{}"),
        "hidden": json.loads(row["hidden_metrics"] or "{}"),
        "grammar_weak_areas": json.loads(row["grammar_weak"] or "[]"),
        "vocabulary_weak_areas": json.loads(row["vocabulary_weak"] or "[]"),
        "behaviour": row["behaviour"] or "",
        "weakest_skill": row["weakest_skill"] or "",
        "strongest_skill": row["strongest_skill"] or "",
        "arena_rank": json.loads(row["arena_rank"] or "{}"),
        "interests": json.loads(row["interests"] or "[]"),
        "main_topic": row["main_topic"] or "",
        "estimated_level": row["level"] or "",
    }