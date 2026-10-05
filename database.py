"""
БД ARENA.
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from config import DB_PATH, BATTLE_COOLDOWN_HOURS
from game_data import ALL_CRITERIA, arsenal_status_for_count

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id         INTEGER PRIMARY KEY,
    username            TEXT,
    first_name          TEXT,
    interface_language  TEXT NOT NULL DEFAULT 'en',
    learning_language   TEXT NOT NULL DEFAULT 'en',
    total_points        INTEGER NOT NULL DEFAULT 0,
    first_battle_done   INTEGER NOT NULL DEFAULT 0,
    temple_done         INTEGER NOT NULL DEFAULT 0,
    push_personality    TEXT,
    push_topics         TEXT,
    last_push_topic     TEXT,
    behaviour           TEXT,
    title               TEXT,
    nemesis_defeated    INTEGER NOT NULL DEFAULT 0,
    last_push_at        TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER NOT NULL,
    personality         TEXT NOT NULL,
    language            TEXT NOT NULL,
    level               TEXT NOT NULL,
    topic               TEXT NOT NULL,
    mission             TEXT,
    rounds_completed    INTEGER NOT NULL DEFAULT 0,
    argumentation_score INTEGER,
    vocabulary_score    INTEGER,
    grammar_score       INTEGER,
    fluency_score       INTEGER,
    points_earned       INTEGER NOT NULL DEFAULT 0,
    strength            TEXT,
    growth              TEXT,
    growth_plan         TEXT,
    conviction_final    INTEGER,
    quest_done          INTEGER NOT NULL DEFAULT 0,
    won                 INTEGER NOT NULL DEFAULT 0,
    overall             INTEGER,
    result_state        TEXT,
    criteria            TEXT,
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
    recommended_personality TEXT,
    pattern          TEXT,
    pattern_evidence TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS freetalk_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    personality   TEXT NOT NULL,
    language      TEXT NOT NULL,
    level         TEXT,
    topic         TEXT,
    messages      TEXT,
    analysis      TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_criteria (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    criterion     TEXT NOT NULL,
    value         INTEGER NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (telegram_id, criterion)
);

CREATE TABLE IF NOT EXISTS user_arsenal (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    kind          TEXT NOT NULL,
    content       TEXT NOT NULL,
    source        TEXT,
    created_at    TEXT NOT NULL,
    UNIQUE (telegram_id, content)
);

CREATE TABLE IF NOT EXISTS user_arsenal_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    uses          INTEGER NOT NULL DEFAULT 0,
    wins          INTEGER NOT NULL DEFAULT 0,
    last_used_at  TEXT,
    UNIQUE (telegram_id, content)
);

CREATE TABLE IF NOT EXISTS user_weapons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    skill_area    TEXT NOT NULL,
    tier          INTEGER NOT NULL DEFAULT 1,
    name          TEXT NOT NULL,
    what_it_does  TEXT NOT NULL DEFAULT '',
    how_to_use    TEXT NOT NULL DEFAULT '[]',
    example       TEXT NOT NULL DEFAULT '',
    when_to_use   TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_tools (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    tool_key      TEXT NOT NULL,
    unlocked_at   TEXT NOT NULL,
    uses          INTEGER NOT NULL DEFAULT 0,
    wins          INTEGER NOT NULL DEFAULT 0,
    last_used_at  TEXT,
    last_source   TEXT,
    UNIQUE (telegram_id, tool_key)
);

CREATE TABLE IF NOT EXISTS user_skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    skill         TEXT NOT NULL,
    points        INTEGER NOT NULL DEFAULT 0,
    rank          INTEGER NOT NULL DEFAULT 1,
    battles       INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL,
    UNIQUE (telegram_id, skill)
);

CREATE TABLE IF NOT EXISTS user_topics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    topic         TEXT NOT NULL,
    count         INTEGER NOT NULL DEFAULT 1,
    last_seen_at  TEXT NOT NULL,
    UNIQUE (telegram_id, topic COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS user_nemesis (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id       INTEGER NOT NULL,
    nemesis_personality TEXT NOT NULL,
    last_fought_at    TEXT,
    defeated          INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    UNIQUE (telegram_id)
);

CREATE TABLE IF NOT EXISTS user_patterns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER NOT NULL,
    pattern_id          TEXT NOT NULL,
    category            TEXT NOT NULL,
    kind                TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'hypothesis',
    confidence          REAL NOT NULL DEFAULT 0,
    evidence_count      INTEGER NOT NULL DEFAULT 0,
    improve_count       INTEGER NOT NULL DEFAULT 0,
    supporting_examples TEXT NOT NULL DEFAULT '[]',
    display_name        TEXT,
    first_observed_at   TEXT NOT NULL,
    last_observed_at    TEXT NOT NULL,
    UNIQUE (telegram_id, pattern_id)
);

CREATE TABLE IF NOT EXISTS user_interest_clusters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    cluster       TEXT NOT NULL,
    count         INTEGER NOT NULL DEFAULT 1,
    examples      TEXT NOT NULL DEFAULT '[]',
    first_seen_at TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    UNIQUE (telegram_id, cluster)
);

CREATE TABLE IF NOT EXISTS user_goals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    goal          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE (telegram_id, goal)
);

CREATE TABLE IF NOT EXISTS user_avoids (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    topic         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE (telegram_id, topic)
);

CREATE TABLE IF NOT EXISTS user_current_read (
    telegram_id   INTEGER PRIMARY KEY,
    read_text     TEXT NOT NULL,
    evidence      TEXT,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_under_pressure (
    telegram_id   INTEGER PRIMARY KEY,
    trajectory    TEXT NOT NULL,
    evidence      TEXT,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_unsolved (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    question      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    resolved_at   TEXT,
    UNIQUE (telegram_id, question)
);

CREATE TABLE IF NOT EXISTS notification_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id             INTEGER NOT NULL,
    created_at              TEXT NOT NULL,
    type                    TEXT NOT NULL,
    text                    TEXT NOT NULL,
    referenced_interest     TEXT,
    referenced_pattern      TEXT,
    referenced_battle       INTEGER,
    referenced_arsenal_item TEXT,
    clicked                 INTEGER NOT NULL DEFAULT 0,
    dismissed               INTEGER NOT NULL DEFAULT 0
);

-- ==================================================================
-- DISCOVERY ENGINE
-- ==================================================================
CREATE TABLE IF NOT EXISTS user_evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER NOT NULL,
    interaction_id  TEXT NOT NULL,
    text_excerpt    TEXT NOT NULL,
    detected        TEXT,
    interpretation  TEXT,
    confidence      REAL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_discoveries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    kind          TEXT NOT NULL,
    headline      TEXT NOT NULL,
    body          TEXT NOT NULL,
    evidence      TEXT,
    shown         INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_notification_state (
    telegram_id       INTEGER PRIMARY KEY,
    last_sent_at      TEXT,
    sent_today_count  INTEGER NOT NULL DEFAULT 0,
    last_day          TEXT,
    last_type         TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)

        def _add_col(table, col, ddl):
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col not in existing:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass

        for col, ddl in [
            ("interface_language", "TEXT NOT NULL DEFAULT 'en'"),
            ("learning_language", "TEXT NOT NULL DEFAULT 'en'"),
            ("language", "TEXT"),
            ("first_battle_done", "INTEGER NOT NULL DEFAULT 0"),
            ("temple_done", "INTEGER NOT NULL DEFAULT 0"),
            ("push_personality", "TEXT"),
            ("push_topics", "TEXT"),
            ("last_push_topic", "TEXT"),
            ("behaviour", "TEXT"),
            ("title", "TEXT"),
            ("nemesis_defeated", "INTEGER NOT NULL DEFAULT 0"),
            ("last_push_at", "TEXT"),
            ("professional_context", "TEXT"),
            ("policy_accepted_at", "TEXT"),
        ]:
            _add_col("users", col, f"ALTER TABLE users ADD COLUMN {col} {ddl}")

        for col, ddl in [
            ("strength", "TEXT"),
            ("growth", "TEXT"),
            ("growth_plan", "TEXT"),
            ("conviction_final", "INTEGER"),
            ("quest_done", "INTEGER NOT NULL DEFAULT 0"),
            ("won", "INTEGER NOT NULL DEFAULT 0"),
            ("overall", "INTEGER"),
            ("criteria", "TEXT"),
            ("result_state", "TEXT"),
            ("mission", "TEXT"),
        ]:
            _add_col("game_sessions", col, f"ALTER TABLE game_sessions ADD COLUMN {col} {ddl}")

        _add_col("game_sessions", "debrief_json", "ALTER TABLE game_sessions ADD COLUMN debrief_json TEXT")

        _add_col("arena_analyses", "recommended_personality",
                 "ALTER TABLE arena_analyses ADD COLUMN recommended_personality TEXT")
        _add_col("arena_analyses", "pattern",
                 "ALTER TABLE arena_analyses ADD COLUMN pattern TEXT")
        _add_col("arena_analyses", "pattern_evidence",
                 "ALTER TABLE arena_analyses ADD COLUMN pattern_evidence TEXT")

        _add_col("user_patterns", "display_name",
                 "ALTER TABLE user_patterns ADD COLUMN display_name TEXT")

        _add_col("user_tools", "uses", "ALTER TABLE user_tools ADD COLUMN uses INTEGER NOT NULL DEFAULT 0")
        _add_col("user_tools", "wins", "ALTER TABLE user_tools ADD COLUMN wins INTEGER NOT NULL DEFAULT 0")
        _add_col("user_tools", "last_used_at", "ALTER TABLE user_tools ADD COLUMN last_used_at TEXT")
        _add_col("user_tools", "last_source", "ALTER TABLE user_tools ADD COLUMN last_source TEXT")

        try:
            conn.execute(
                "UPDATE users SET learning_language = language "
                "WHERE learning_language = 'en' AND language IS NOT NULL AND language != 'en'"
            )
        except sqlite3.OperationalError:
            pass

        conn.execute("UPDATE users SET temple_done = 1 WHERE first_battle_done = 1 AND temple_done = 0")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Users ----------

def get_or_create_user(telegram_id: int, username: str | None, first_name: str | None,
                       interface_lang: str = "en") -> sqlite3.Row:
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
            "INSERT INTO users (telegram_id, username, first_name, interface_language, learning_language, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, 'en', ?, ?)",
            (telegram_id, username, first_name, interface_lang, now, now),
        )
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def get_user(telegram_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()


def set_interface_language(telegram_id: int, lang: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET interface_language = ?, updated_at = ? WHERE telegram_id = ?",
                     (lang, _now(), telegram_id))


def set_learning_language(telegram_id: int, lang: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET learning_language = ?, updated_at = ? WHERE telegram_id = ?",
                     (lang, _now(), telegram_id))


def get_interface_language(telegram_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT interface_language FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return (row["interface_language"] if row and row["interface_language"] else "en")


def get_learning_language(telegram_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT learning_language FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return (row["learning_language"] if row and row["learning_language"] else "en")


def has_completed_first_battle(telegram_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT first_battle_done FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return bool(row and row["first_battle_done"])


def mark_first_battle_done(telegram_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET first_battle_done = 1, updated_at = ? WHERE telegram_id = ?",
                     (_now(), telegram_id))


def has_completed_temple(telegram_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT temple_done FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return bool(row and row["temple_done"])


def mark_temple_done(telegram_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET temple_done = 1, updated_at = ? WHERE telegram_id = ?",
                     (_now(), telegram_id))


def set_user_behaviour_title(telegram_id: int, behaviour: str, title: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET behaviour = ?, title = ?, updated_at = ? WHERE telegram_id = ?",
                     (behaviour, title, _now(), telegram_id))


def has_accepted_policy(telegram_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT policy_accepted_at FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return bool(row and row["policy_accepted_at"])


def accept_policy(telegram_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET policy_accepted_at = ?, updated_at = ? WHERE telegram_id = ?",
            (_now(), _now(), telegram_id),
        )


def reset_user_data(telegram_id: int):
    with get_conn() as conn:
        for table in (
            "game_sessions", "achievements", "vocabulary_mistakes", "user_level_history",
            "arena_analyses", "freetalk_sessions", "user_criteria", "user_arsenal", "user_nemesis",
            "user_weapons", "user_skills", "user_topics", "user_tools", "user_arsenal_usage",
            "user_patterns", "user_interest_clusters", "notification_log",
            "user_goals", "user_avoids",
            "user_current_read", "user_under_pressure", "user_unsolved",
            "user_evidence", "user_discoveries", "user_notification_state",
        ):
            conn.execute(f"DELETE FROM {table} WHERE telegram_id = ?", (telegram_id,))
        conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))


def get_user_first_name(telegram_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT first_name FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return row["first_name"] if row and row["first_name"] else ""


# ---------- Push / memory ----------

def set_push_profile(telegram_id: int, personality: str, topics: list):
    with get_conn() as conn:
        conn.execute("UPDATE users SET push_personality = ?, push_topics = ?, updated_at = ? WHERE telegram_id = ?",
                     (personality, json.dumps(topics, ensure_ascii=False), _now(), telegram_id))


def get_all_push_profiles() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT telegram_id, push_personality, push_topics, first_name, last_push_at, "
            "interface_language, learning_language "
            "FROM users WHERE push_personality IS NOT NULL AND temple_done = 1"
        ).fetchall()
    result = []
    for row in rows:
        topics = json.loads(row["push_topics"]) if row["push_topics"] else []
        result.append({
            "telegram_id": row["telegram_id"],
            "personality": row["push_personality"],
            "topics": topics,
            "first_name": row["first_name"] or "",
            "last_push_at": row["last_push_at"],
            "interface_language": row["interface_language"] or "en",
            "learning_language": row["learning_language"] or "en",
        })
    return result


def mark_push_sent(telegram_id: int, topic: str = ""):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_push_at = ?, last_push_topic = ? WHERE telegram_id = ?",
            (_now(), topic, telegram_id),
        )


def pop_push_topic(telegram_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_push_topic, last_push_at FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if not row or not row["last_push_topic"] or not row["last_push_at"]:
            return None
        conn.execute("UPDATE users SET last_push_topic = NULL WHERE telegram_id = ?", (telegram_id,))
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["last_push_at"])
    except ValueError:
        return None
    return row["last_push_topic"] if age < timedelta(hours=36) else None


# ---------- Interests / memory ----------

def get_interests(telegram_id: int) -> list[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT push_topics FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not row or not row["push_topics"]:
        return []
    try:
        return [t for t in json.loads(row["push_topics"]) if isinstance(t, str) and t.strip()]
    except ValueError:
        return []


def add_interests(telegram_id: int, new_topics: list[str], limit: int = 8):
    fresh = [t.strip() for t in (new_topics or []) if isinstance(t, str) and t.strip()]
    if not fresh:
        return
    merged, seen = [], set()
    for t in fresh + get_interests(telegram_id):
        if t.lower() not in seen:
            seen.add(t.lower())
            merged.append(t)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET push_topics = ?, updated_at = ? WHERE telegram_id = ?",
            (json.dumps(merged[:limit], ensure_ascii=False), _now(), telegram_id),
        )
    bump_topics(telegram_id, fresh)


def bump_topics(telegram_id: int, topics: list[str]):
    fresh = [t.strip() for t in (topics or []) if isinstance(t, str) and t.strip()]
    if not fresh:
        return
    now = _now()
    with get_conn() as conn:
        for t in fresh:
            conn.execute(
                """INSERT INTO user_topics (telegram_id, topic, count, last_seen_at)
                   VALUES (?, ?, 1, ?)
                   ON CONFLICT(telegram_id, topic) DO UPDATE SET
                       count = count + 1, last_seen_at = excluded.last_seen_at""",
                (telegram_id, t, now),
            )


def get_favorite_topics(telegram_id: int, limit: int = 5, min_count: int = 2) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT topic FROM user_topics WHERE telegram_id = ? AND count >= ? "
            "ORDER BY count DESC, last_seen_at DESC LIMIT ?",
            (telegram_id, min_count, limit),
        ).fetchall()
    return [r["topic"] for r in rows]


def get_memory(telegram_id: int) -> dict:
    interests = get_interests(telegram_id)
    favorite_topics = get_favorite_topics(telegram_id)
    with get_conn() as conn:
        ft_topics = [r["topic"] for r in conn.execute(
            "SELECT topic FROM freetalk_sessions WHERE telegram_id = ? AND topic != '' ORDER BY id DESC LIMIT 5",
            (telegram_id,))]
        battle_topics = [r["topic"] for r in conn.execute(
            "SELECT topic FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT 3", (telegram_id,))]
        last_ft = conn.execute(
            "SELECT messages FROM freetalk_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (telegram_id,)).fetchone()
    recent, seen = [], set()
    for t in ft_topics + battle_topics:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            recent.append(t)
    said = []
    if last_ft and last_ft["messages"]:
        try:
            msgs = json.loads(last_ft["messages"])
            said = [m["text"][:140] for m in msgs if m.get("speaker") == "User"][-3:]
        except (ValueError, KeyError, TypeError):
            pass
    return {
        "interests": interests,
        "favorite_topics": favorite_topics,
        "recent_topics": recent,
        "last_said": said,
    }


# ---------- Sessions ----------

def save_game_session(
        telegram_id: int, personality: str, language: str, level: str, topic: str,
        rounds_completed: int, scores: dict, points_earned: int,
        strength: str = "", growth: str = "", growth_plan: str = "",
        conviction_final: int = 0, quest_done: int = 0, won: int = 0, overall: int | None = None,
        mission: str = "", result_state: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO game_sessions
               (telegram_id, personality, language, level, topic, mission, rounds_completed,
                argumentation_score, vocabulary_score, grammar_score, fluency_score,
                points_earned, strength, growth, growth_plan, conviction_final, quest_done,
                won, overall, result_state, criteria, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id, personality, language, level, topic, mission, rounds_completed,
                scores.get("argumentation"), scores.get("vocabulary"),
                scores.get("grammar"), scores.get("fluency"),
                points_earned, strength, growth, growth_plan, conviction_final, quest_done,
                won, overall, result_state, json.dumps(scores, ensure_ascii=False), _now(),
            ),
        )
        return cur.lastrowid


def get_user_stats(telegram_id: int) -> dict:
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        sessions = conn.execute(
            "SELECT id, personality, language, level, topic, mission, won, overall, "
            "result_state, created_at, debrief_json "
            "FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC", (telegram_id,)
        ).fetchall()
        achievements = conn.execute(
            "SELECT badge_key FROM achievements WHERE telegram_id = ?", (telegram_id,)
        ).fetchall()

    total_points = user["total_points"] if user else 0
    unique_personalities = {s["personality"] for s in sessions}
    overalls = [s["overall"] for s in sessions if s["overall"] is not None]
    avg_score = round(sum(overalls) / len(overalls)) if overalls else None
    latest = sessions[0] if sessions else None

    return {
        "total_points": total_points,
        "games_played": len(sessions),
        "wins": sum(1 for s in sessions if s["won"]),
        "unique_personalities": unique_personalities,
        "avg_score": avg_score,
        "achievements": [a["badge_key"] for a in achievements],
        "last_sessions": sessions[:10],
        "latest_strength": latest["mission"] if latest else "",
        "latest_growth": latest["mission"] if latest else "",
        "latest_growth_plan": "",
        "behaviour": user["behaviour"] if user else "",
        "title": user["title"] if user else "",
        "nemesis_defeated": user["nemesis_defeated"] if user else 0,
    }


def count_battles(telegram_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM game_sessions WHERE telegram_id = ?",
                           (telegram_id,)).fetchone()
    return row["c"] if row else 0


def get_last_personality(telegram_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT personality FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (telegram_id,)).fetchone()
    return row["personality"] if row else None


def get_hours_since_last_battle(telegram_id: int) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT created_at FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()
    if not row or not row["created_at"]:
        return None
    try:
        last_dt = datetime.fromisoformat(row["created_at"])
    except ValueError:
        return None
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600


def has_battled_today(telegram_id: int) -> bool:
    hours = get_hours_since_last_battle(telegram_id)
    return hours is not None and hours < BATTLE_COOLDOWN_HOURS


def cooldown_hours_left(telegram_id: int) -> float:
    hours = get_hours_since_last_battle(telegram_id)
    if hours is None:
        return 0.0
    return max(0.0, BATTLE_COOLDOWN_HOURS - hours)


def get_recent_battle_topics(telegram_id: int, n: int = 3) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT topic FROM game_sessions WHERE telegram_id = ? AND topic != '' "
            "ORDER BY id DESC LIMIT ?",
            (telegram_id, n),
        ).fetchall()
    return [r["topic"] for r in rows]


def get_recent_avg_scores(telegram_id: int, n: int = 3, level: str | None = None) -> float | None:
    query = ("SELECT overall, argumentation_score, vocabulary_score, grammar_score, fluency_score "
             "FROM game_sessions WHERE telegram_id = ? ")
    params: list = [telegram_id]
    if level:
        query += "AND level = ? "
        params.append(level)
    query += "ORDER BY id DESC LIMIT ?"
    params.append(n)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    if level and len(rows) < n:
        return None
    vals = []
    for r in rows:
        if r["overall"] is not None:
            vals.append(r["overall"])
            continue
        s = [v for v in (r["argumentation_score"], r["vocabulary_score"],
                         r["grammar_score"], r["fluency_score"]) if v is not None]
        if s:
            vals.append(sum(s) / len(s))
    return sum(vals) / len(vals) if vals else None


# ---------- Free talk ----------

def save_freetalk_session(telegram_id: int, personality: str, language: str,
                          level: str, topic: str, messages: list, analysis: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO freetalk_sessions
               (telegram_id, personality, language, level, topic, messages, analysis, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, personality, language, level, topic,
             json.dumps(messages, ensure_ascii=False),
             json.dumps(analysis or {}, ensure_ascii=False), _now()),
        )


# ---------- Criteria ----------

def update_criteria(telegram_id: int, scores: dict, weight: float = 0.4):
    with get_conn() as conn:
        for key, val in scores.items():
            if key not in ALL_CRITERIA or not isinstance(val, (int, float)):
                continue
            val = int(max(0, min(100, val)))
            row = conn.execute(
                "SELECT value FROM user_criteria WHERE telegram_id = ? AND criterion = ?",
                (telegram_id, key)).fetchone()
            new = val if row is None else round(row["value"] * (1 - weight) + val * weight)
            conn.execute(
                """INSERT INTO user_criteria (telegram_id, criterion, value, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(telegram_id, criterion) DO UPDATE SET
                       value = excluded.value, updated_at = excluded.updated_at""",
                (telegram_id, key, new, _now()),
            )


def get_criteria(telegram_id: int) -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT criterion, value FROM user_criteria WHERE telegram_id = ?",
                            (telegram_id,)).fetchall()
    return {r["criterion"]: r["value"] for r in rows}


# ---------- Achievements ----------

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


# ---------- Vocabulary ----------

def add_vocabulary_mistakes(telegram_id: int, mistakes: list[dict]):
    if not mistakes:
        return
    with get_conn() as conn:
        for m in mistakes:
            existing = conn.execute(
                "SELECT id FROM vocabulary_mistakes WHERE telegram_id = ? AND wrong = ?",
                (telegram_id, m["wrong"]),
            ).fetchone()
            if existing:
                conn.execute("UPDATE vocabulary_mistakes SET times_seen = times_seen + 1 WHERE id = ?",
                             (existing["id"],))
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
            "WHERE telegram_id = ? AND learned = 0 ORDER BY times_seen DESC, id DESC LIMIT ?",
            (telegram_id, limit),
        ).fetchall()
    return [{"wrong": r["wrong"], "correct": r["correct"], "times_seen": r["times_seen"]} for r in rows]


# ---------- Level history ----------

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
            "SELECT level FROM user_level_history WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()
    return row["level"] if row else None


# ---------- Arena analysis ----------

def save_arena_analysis(telegram_id: int, analysis: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO arena_analyses
               (telegram_id, language_metrics, communication, hidden_metrics,
                grammar_weak, vocabulary_weak, behaviour, weakest_skill,
                strongest_skill, arena_rank, interests, main_topic, level,
                recommended_personality, pattern, pattern_evidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                analysis.get("recommended_personality", ""),
                analysis.get("pattern", ""),
                json.dumps(analysis.get("pattern_evidence", []), ensure_ascii=False),
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
        "recommended_personality": row["recommended_personality"] or "",
        "pattern": row["pattern"] or "",
        "pattern_evidence": json.loads(row["pattern_evidence"] or "[]"),
    }


# ---------- Skill progress ----------

def add_skill_progress(telegram_id: int, skill: str, delta: int, battles: int = 1):
    if not skill:
        return
    delta = max(0, int(delta))
    with get_conn() as conn:
        row = conn.execute(
            "SELECT points, battles FROM user_skills WHERE telegram_id = ? AND skill = ?",
            (telegram_id, skill),
        ).fetchone()
        points = (row["points"] if row else 0) + delta
        total_battles = (row["battles"] if row else 0) + battles
        rank = min(5, 1 + points // 50)
        conn.execute(
            """INSERT INTO user_skills (telegram_id, skill, points, rank, battles, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id, skill) DO UPDATE SET
                   points = excluded.points, rank = excluded.rank,
                   battles = excluded.battles, updated_at = excluded.updated_at""",
            (telegram_id, skill, points, rank, total_battles, _now()),
        )


def get_all_skills(telegram_id: int) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT skill, points, rank, battles FROM user_skills WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchall()
    return {r["skill"]: {"points": r["points"], "rank": r["rank"], "battles": r["battles"]} for r in rows}


# ---------- Arsenal tools ----------

def unlock_tool(telegram_id: int, tool_key: str) -> bool:
    if not tool_key:
        return False
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO user_tools (telegram_id, tool_key, unlocked_at, uses, wins) "
                "VALUES (?, ?, ?, 0, 0)",
                (telegram_id, tool_key, _now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_unlocked_tools(telegram_id: int) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT tool_key FROM user_tools WHERE telegram_id = ?", (telegram_id,)
        ).fetchall()
    return {r["tool_key"] for r in rows}


def get_last_unlocked_tool(telegram_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT tool_key FROM user_tools WHERE telegram_id = ? "
            "ORDER BY unlocked_at DESC LIMIT 1", (telegram_id,)
        ).fetchone()
    return row["tool_key"] if row else None


def record_tool_use(telegram_id: int, tool_key: str, won: bool, source: str = "") -> dict | None:
    if not tool_key:
        return None
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT uses, wins FROM user_tools WHERE telegram_id = ? AND tool_key = ?",
            (telegram_id, tool_key),
        ).fetchone()
        if row:
            uses = (row["uses"] or 0) + 1
            wins = (row["wins"] or 0) + (1 if won else 0)
            conn.execute(
                "UPDATE user_tools SET uses = ?, wins = ?, last_used_at = ?, last_source = ? "
                "WHERE telegram_id = ? AND tool_key = ?",
                (uses, wins, now, source, telegram_id, tool_key),
            )
        else:
            uses = 1
            wins = 1 if won else 0
            conn.execute(
                "INSERT INTO user_tools (telegram_id, tool_key, unlocked_at, uses, wins, "
                "last_used_at, last_source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (telegram_id, tool_key, now, uses, wins, now, source),
            )
    return {"uses": uses, "wins": wins, "status": arsenal_status_for_count(uses)}


def get_tool_stats(telegram_id: int, tool_key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT uses, wins, unlocked_at, last_used_at FROM user_tools "
            "WHERE telegram_id = ? AND tool_key = ?",
            (telegram_id, tool_key),
        ).fetchone()
    if not row:
        return None
    uses = row["uses"] or 0
    return {
        "uses": uses,
        "wins": row["wins"] or 0,
        "status": arsenal_status_for_count(max(1, uses)),
        "unlocked_at": row["unlocked_at"],
        "last_used_at": row["last_used_at"],
    }


def get_all_tool_stats(telegram_id: int) -> dict[str, dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT tool_key, uses, wins, unlocked_at, last_used_at FROM user_tools "
            "WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchall()
    out = {}
    for r in rows:
        uses = r["uses"] or 0
        out[r["tool_key"]] = {
            "uses": uses,
            "wins": r["wins"] or 0,
            "status": arsenal_status_for_count(max(1, uses)) if uses > 0 else "discovered",
            "unlocked_at": r["unlocked_at"],
            "last_used_at": r["last_used_at"],
        }
    return out


# ---------- Weapons ----------

def get_weapon_tier(telegram_id: int, skill_area: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(tier) AS t FROM user_weapons WHERE telegram_id = ? AND skill_area = ?",
            (telegram_id, skill_area),
        ).fetchone()
    return (row["t"] or 0) if row else 0


def add_weapon(telegram_id: int, skill_area: str, tier: int, name: str, what_it_does: str,
              how_to_use: list[str], example: str, when_to_use: str, source: str = "") -> bool:
    if not name:
        return False
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO user_weapons
               (telegram_id, skill_area, tier, name, what_it_does, how_to_use,
                example, when_to_use, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, skill_area or "general", max(1, tier), name, what_it_does,
             json.dumps(how_to_use or [], ensure_ascii=False), example, when_to_use,
             source, _now()),
        )
    return True


def get_weapons(telegram_id: int, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT skill_area, tier, name, what_it_does, how_to_use, example, when_to_use, "
            "source, created_at FROM user_weapons WHERE telegram_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (telegram_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["how_to_use"] = json.loads(d["how_to_use"])
        except (ValueError, TypeError):
            d["how_to_use"] = []
        out.append(d)
    return out


def get_weapon_tiers(telegram_id: int) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT skill_area, MAX(tier) AS t FROM user_weapons WHERE telegram_id = ? GROUP BY skill_area",
            (telegram_id,),
        ).fetchall()
    return {r["skill_area"]: r["t"] for r in rows}


# ---------- Arsenal (user_arsenal + usage) ----------

def add_arsenal_item(telegram_id: int, kind: str, content: str, source: str = "") -> bool:
    content = (content or "").strip()
    if not content:
        return False
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO user_arsenal (telegram_id, kind, content, source, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (telegram_id, kind, content, source, _now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_arsenal(telegram_id: int, kind: str | None = None) -> list[dict]:
    query = "SELECT kind, content, source, created_at FROM user_arsenal WHERE telegram_id = ?"
    params: list = [telegram_id]
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    query += " ORDER BY kind, id DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [{"kind": r["kind"], "content": r["content"], "source": r["source"] or ""} for r in rows]


def add_grammar_phrases(telegram_id: int, goal: str, phrases: list[str]) -> int:
    if not phrases or not goal:
        return 0
    added = 0
    with get_conn() as conn:
        for p in phrases:
            p = (p or "").strip()
            if not p:
                continue
            try:
                conn.execute(
                    "INSERT INTO user_arsenal (telegram_id, kind, content, source, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (telegram_id, f"grammar:{goal}", p[:300], "battle_debrief", _now()),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass
    return added


def get_grammar_phrases(telegram_id: int, goal: str | None = None, limit: int = 40) -> list[dict]:
    with get_conn() as conn:
        if goal:
            rows = conn.execute(
                "SELECT kind, content, source, created_at FROM user_arsenal "
                "WHERE telegram_id = ? AND kind = ? ORDER BY id DESC LIMIT ?",
                (telegram_id, f"grammar:{goal}", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT kind, content, source, created_at FROM user_arsenal "
                "WHERE telegram_id = ? AND kind LIKE 'grammar:%' ORDER BY id DESC LIMIT ?",
                (telegram_id, limit),
            ).fetchall()
    return [
        {"goal": r["kind"].replace("grammar:", ""), "phrase": r["content"],
         "source": r["source"] or "", "created_at": r["created_at"]}
        for r in rows
    ]


def record_phrase_use(telegram_id: int, phrase: str, won: bool) -> dict | None:
    phrase = (phrase or "").strip()
    if not phrase:
        return None
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT uses, wins FROM user_arsenal_usage WHERE telegram_id = ? AND content = ?",
            (telegram_id, phrase),
        ).fetchone()
        if row:
            uses = (row["uses"] or 0) + 1
            wins = (row["wins"] or 0) + (1 if won else 0)
            conn.execute(
                "UPDATE user_arsenal_usage SET uses = ?, wins = ?, last_used_at = ? "
                "WHERE telegram_id = ? AND content = ?",
                (uses, wins, now, telegram_id, phrase),
            )
        else:
            uses = 1
            wins = 1 if won else 0
            conn.execute(
                "INSERT INTO user_arsenal_usage (telegram_id, content, uses, wins, last_used_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (telegram_id, phrase, uses, wins, now),
            )
    return {"uses": uses, "wins": wins, "status": arsenal_status_for_count(uses)}


def get_grammar_phrases_with_stats(telegram_id: int, goal: str | None = None, limit: int = 40) -> list[dict]:
    with get_conn() as conn:
        if goal:
            rows = conn.execute(
                "SELECT kind, content, source, created_at FROM user_arsenal "
                "WHERE telegram_id = ? AND kind = ? ORDER BY id DESC LIMIT ?",
                (telegram_id, f"grammar:{goal}", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT kind, content, source, created_at FROM user_arsenal "
                "WHERE telegram_id = ? AND kind LIKE 'grammar:%' ORDER BY id DESC LIMIT ?",
                (telegram_id, limit),
            ).fetchall()

        out = []
        for r in rows:
            phrase = r["content"]
            usage = conn.execute(
                "SELECT uses, wins FROM user_arsenal_usage WHERE telegram_id = ? AND content = ?",
                (telegram_id, phrase),
            ).fetchone()
            uses = usage["uses"] if usage else 0
            wins = usage["wins"] if usage else 0
            out.append({
                "goal": r["kind"].replace("grammar:", ""),
                "phrase": phrase,
                "source": r["source"] or "",
                "created_at": r["created_at"],
                "uses": uses,
                "wins": wins,
                "status": arsenal_status_for_count(uses) if uses else "discovered",
            })
    return out


# ---------- Nemesis ----------

NEMESIS_MAP = {
    "analyst": "philosopher",
    "challenger": "philosopher",
    "explorer": "devil_advocate",
    "precise": "hr_manager",
    "defender": "ceo",
}


def set_nemesis(telegram_id: int, behaviour: str):
    nemesis = NEMESIS_MAP.get(behaviour, "devil_advocate")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO user_nemesis (telegram_id, nemesis_personality, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   nemesis_personality = excluded.nemesis_personality,
                   last_fought_at = NULL,
                   defeated = 0""",
            (telegram_id, nemesis, _now()),
        )


def get_nemesis(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM user_nemesis WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not row:
        return None
    return {
        "personality": row["nemesis_personality"],
        "last_fought_at": row["last_fought_at"],
        "defeated": bool(row["defeated"]),
    }


def mark_nemesis_fought(telegram_id: int, defeated: bool = False):
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_nemesis SET last_fought_at = ?, defeated = ? WHERE telegram_id = ?",
            (_now(), 1 if defeated else 0, telegram_id),
        )
        if defeated:
            conn.execute(
                "UPDATE users SET nemesis_defeated = nemesis_defeated + 1 WHERE telegram_id = ?",
                (telegram_id,),
            )


# ==================================================================
# PERSONALIZATION MEMORY
# ==================================================================

DEBRIEF_KEYS = ("result_line", "worked", "win_move", "cost", "growth", "tool_used",
                "next_target", "language_upgrade", "result_state", "deeper_content",
                "the_mechanism", "the_moment", "the_shift", "escape_route",
                "arena_read", "grammar_for_goal", "debrief_shape", "single_insight",
                "headline", "notification_line", "arena_file_update", "grammar_used")


def save_session_debrief(session_id: int | None, fb: dict):
    if not session_id or not fb:
        return
    slim = {k: fb.get(k) for k in DEBRIEF_KEYS if fb.get(k)}
    with get_conn() as conn:
        conn.execute("UPDATE game_sessions SET debrief_json = ? WHERE id = ?",
                     (json.dumps(slim, ensure_ascii=False), session_id))


def get_last_session(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, personality, topic, mission, result_state, won, created_at, debrief_json "
            "FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT 1", (telegram_id,)
        ).fetchone()
    if not row:
        return None
    try:
        debrief = json.loads(row["debrief_json"]) if row["debrief_json"] else {}
    except ValueError:
        debrief = {}
    return {
        "id": row["id"], "personality": row["personality"], "topic": row["topic"] or "",
        "mission": row["mission"] or "", "result_state": row["result_state"] or "",
        "won": bool(row["won"]), "created_at": row["created_at"], "debrief": debrief,
    }


def get_last_freetalk(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT topic, created_at FROM freetalk_sessions WHERE telegram_id = ? AND topic != '' "
            "ORDER BY id DESC LIMIT 1", (telegram_id,)
        ).fetchone()
    return {"topic": row["topic"], "created_at": row["created_at"]} if row else None


def record_interest_clusters(telegram_id: int, items: list[dict]):
    merged: dict[str, list[str]] = {}
    for it in items or []:
        c = (it.get("cluster") or "").strip()
        if not c:
            continue
        merged.setdefault(c, [])
        ex = (it.get("example") or "").strip()
        if ex and ex.lower() not in [e.lower() for e in merged[c]]:
            merged[c].append(ex)
    if not merged:
        return
    now = _now()
    with get_conn() as conn:
        for cluster, examples in merged.items():
            row = conn.execute(
                "SELECT count, examples FROM user_interest_clusters WHERE telegram_id = ? AND cluster = ?",
                (telegram_id, cluster)).fetchone()
            if row:
                try:
                    old = json.loads(row["examples"] or "[]")
                except ValueError:
                    old = []
                seen = {e.lower() for e in old}
                allx = (old + [e for e in examples if e.lower() not in seen])[-5:]
                conn.execute(
                    "UPDATE user_interest_clusters SET count = count + 1, examples = ?, last_seen_at = ? "
                    "WHERE telegram_id = ? AND cluster = ?",
                    (json.dumps(allx, ensure_ascii=False), now, telegram_id, cluster))
            else:
                conn.execute(
                    "INSERT INTO user_interest_clusters (telegram_id, cluster, count, examples, "
                    "first_seen_at, last_seen_at) VALUES (?, ?, 1, ?, ?, ?)",
                    (telegram_id, cluster, json.dumps(examples[-5:], ensure_ascii=False), now, now))


def get_interest_clusters(telegram_id: int, limit: int = 6) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT cluster, count, examples, last_seen_at FROM user_interest_clusters "
            "WHERE telegram_id = ? ORDER BY last_seen_at DESC, count DESC LIMIT ?",
            (telegram_id, limit)).fetchall()
    out = []
    for r in rows:
        try:
            ex = json.loads(r["examples"] or "[]")
        except ValueError:
            ex = []
        out.append({"cluster": r["cluster"], "count": r["count"], "examples": ex,
                    "last_seen_at": r["last_seen_at"]})
    return out


def _status_for_count(n: int) -> str:
    return "hypothesis" if n <= 1 else ("emerging" if n == 2 else "confirmed")


def observe_pattern(telegram_id: int, pattern_id: str, category: str, kind: str,
                    example: str = "", counter_of: str | None = None,
                    display_name: str = "") -> str:
    now = _now()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM user_patterns WHERE telegram_id = ? AND pattern_id = ?",
                           (telegram_id, pattern_id)).fetchone()
        if row:
            count = row["evidence_count"] + 1
            try:
                examples = json.loads(row["supporting_examples"] or "[]")
            except ValueError:
                examples = []
            if example and example not in examples:
                examples = (examples + [example])[-3:]
            status, improve = row["status"], row["improve_count"]
            if status in ("improving", "resolved") and kind == "growth":
                status, improve = ("confirmed" if count >= 3 else _status_for_count(count)), 0
            elif status not in ("improving", "resolved"):
                status = _status_for_count(count)
            dn = display_name or row["display_name"] or pattern_id
            conn.execute(
                "UPDATE user_patterns SET evidence_count = ?, status = ?, improve_count = ?, confidence = ?, "
                "supporting_examples = ?, display_name = ?, last_observed_at = ? WHERE id = ?",
                (count, status, improve, round(min(1.0, count / 4), 2),
                 json.dumps(examples, ensure_ascii=False), dn, now, row["id"]))
        else:
            status = "hypothesis"
            conn.execute(
                "INSERT INTO user_patterns (telegram_id, pattern_id, category, kind, status, confidence, "
                "evidence_count, improve_count, supporting_examples, display_name, "
                "first_observed_at, last_observed_at) "
                "VALUES (?, ?, ?, ?, 'hypothesis', 0.25, 1, 0, ?, ?, ?, ?)",
                (telegram_id, pattern_id, category, kind,
                 json.dumps([example] if example else [], ensure_ascii=False),
                 display_name or pattern_id, now, now))

        if counter_of:
            g = conn.execute("SELECT id, status, improve_count FROM user_patterns "
                             "WHERE telegram_id = ? AND pattern_id = ?", (telegram_id, counter_of)).fetchone()
            if g and g["status"] in ("confirmed", "improving"):
                imp = g["improve_count"] + 1
                conn.execute("UPDATE user_patterns SET improve_count = ?, status = ? WHERE id = ?",
                             (imp, "resolved" if imp >= 3 else "improving", g["id"]))
    return status


def get_patterns(telegram_id: int, statuses: tuple | None = None) -> list[dict]:
    sql = "SELECT * FROM user_patterns WHERE telegram_id = ?"
    args: list = [telegram_id]
    if statuses:
        sql += f" AND status IN ({','.join('?' * len(statuses))})"
        args += list(statuses)
    sql += " ORDER BY evidence_count DESC, last_observed_at DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    out = []
    for r in rows:
        try:
            ex = json.loads(r["supporting_examples"] or "[]")
        except ValueError:
            ex = []
        out.append({
            "pattern_id": r["pattern_id"], "category": r["category"], "kind": r["kind"],
            "status": r["status"], "confidence": r["confidence"], "evidence_count": r["evidence_count"],
            "supporting_examples": ex, "display_name": r["display_name"] or r["pattern_id"],
            "first_observed_at": r["first_observed_at"],
            "last_observed_at": r["last_observed_at"],
        })
    return out


# ---------- Notification history ----------

def mark_previous_unclicked_dismissed(telegram_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE notification_log SET dismissed = 1 WHERE telegram_id = ? AND clicked = 0",
                     (telegram_id,))


def log_notification(telegram_id: int, ntype: str, text: str, interest: str | None = None,
                     pattern: str | None = None, battle: int | None = None,
                     arsenal_item: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO notification_log (telegram_id, created_at, type, text, referenced_interest, "
            "referenced_pattern, referenced_battle, referenced_arsenal_item) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (telegram_id, _now(), ntype, text, interest, pattern, battle, arsenal_item))
        return cur.lastrowid


def get_recent_notifications(telegram_id: int, n: int = 7) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notification_log WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
            (telegram_id, n)).fetchall()
    return [dict(r) for r in rows]


def mark_notification_clicked(notification_id: int, telegram_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE notification_log SET clicked = 1, dismissed = 0 WHERE id = ? AND telegram_id = ?",
                     (notification_id, telegram_id))


# ---------- Goals / professional context / avoids ----------

def set_professional_context(telegram_id: int, context: str):
    context = (context or "").strip()
    if not context:
        return
    with get_conn() as conn:
        conn.execute("UPDATE users SET professional_context = ?, updated_at = ? WHERE telegram_id = ?",
                     (context[:120], _now(), telegram_id))


def get_professional_context(telegram_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT professional_context FROM users WHERE telegram_id = ?",
                           (telegram_id,)).fetchone()
    return (row["professional_context"] if row and row["professional_context"] else "")


def add_goal(telegram_id: int, goal: str):
    goal = (goal or "").strip()
    if not goal:
        return
    with get_conn() as conn:
        try:
            conn.execute("INSERT INTO user_goals (telegram_id, goal, created_at) VALUES (?, ?, ?)",
                         (telegram_id, goal[:120], _now()))
        except sqlite3.IntegrityError:
            pass


def get_goals(telegram_id: int, limit: int = 5) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT goal FROM user_goals WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit)).fetchall()
    return [r["goal"] for r in rows]


def add_avoids(telegram_id: int, topic: str):
    topic = (topic or "").strip()
    if not topic:
        return
    with get_conn() as conn:
        try:
            conn.execute("INSERT INTO user_avoids (telegram_id, topic, created_at) VALUES (?, ?, ?)",
                         (telegram_id, topic[:80], _now()))
        except sqlite3.IntegrityError:
            pass


def get_avoids(telegram_id: int, limit: int = 3) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT topic FROM user_avoids WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit)).fetchall()
    return [r["topic"] for r in rows]


# ==================================================================
# LIVING MY ARENA
# ==================================================================

def set_current_read(telegram_id: int, read_text: str, evidence: list | None = None):
    read_text = (read_text or "").strip()
    if not read_text:
        return
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO user_current_read (telegram_id, read_text, evidence, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   read_text = excluded.read_text,
                   evidence = excluded.evidence,
                   updated_at = excluded.updated_at""",
            (telegram_id, read_text[:400],
             json.dumps(evidence or [], ensure_ascii=False), _now()),
        )


def get_current_read(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT read_text, evidence, updated_at FROM user_current_read WHERE telegram_id = ?",
            (telegram_id,)).fetchone()
    if not row:
        return None
    try:
        ev = json.loads(row["evidence"] or "[]")
    except ValueError:
        ev = []
    return {"read_text": row["read_text"], "evidence": ev, "updated_at": row["updated_at"]}


def set_under_pressure(telegram_id: int, trajectory: str, evidence: list | None = None):
    trajectory = (trajectory or "").strip()
    if not trajectory:
        return
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO user_under_pressure (telegram_id, trajectory, evidence, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   trajectory = excluded.trajectory,
                   evidence = excluded.evidence,
                   updated_at = excluded.updated_at""",
            (telegram_id, trajectory[:300],
             json.dumps(evidence or [], ensure_ascii=False), _now()),
        )


def get_under_pressure(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT trajectory, evidence, updated_at FROM user_under_pressure WHERE telegram_id = ?",
            (telegram_id,)).fetchone()
    if not row:
        return None
    try:
        ev = json.loads(row["evidence"] or "[]")
    except ValueError:
        ev = []
    return {"trajectory": row["trajectory"], "evidence": ev, "updated_at": row["updated_at"]}


def add_unsolved(telegram_id: int, question: str):
    question = (question or "").strip()
    if not question:
        return
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO user_unsolved (telegram_id, question, created_at) VALUES (?, ?, ?)",
                (telegram_id, question[:300], _now()),
            )
        except sqlite3.IntegrityError:
            pass


def resolve_unsolved(telegram_id: int, question: str):
    question = (question or "").strip()
    if not question:
        return
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_unsolved SET resolved_at = ? WHERE telegram_id = ? AND question = ?",
            (_now(), telegram_id, question[:300]),
        )


def get_unsolved(telegram_id: int, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, question, created_at FROM user_unsolved "
            "WHERE telegram_id = ? AND resolved_at IS NULL "
            "ORDER BY id DESC LIMIT ?",
            (telegram_id, limit)).fetchall()
    return [{"id": r["id"], "question": r["question"], "created_at": r["created_at"]} for r in rows]


# ==================================================================
# DISCOVERY ENGINE
# ==================================================================

def add_evidence(telegram_id: int, interaction_id: str, text_excerpt: str,
                 detected: str = "", interpretation: str = "", confidence: float = 0.5) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO user_evidence (telegram_id, interaction_id, text_excerpt, detected, "
            "interpretation, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (telegram_id, interaction_id, text_excerpt[:400], detected[:300],
             interpretation[:400], float(confidence), _now()),
        )
        return cur.lastrowid


def get_recent_evidence(telegram_id: int, since_hours: int = 48, limit: int = 40) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, interaction_id, text_excerpt, detected, interpretation, confidence, created_at "
            "FROM user_evidence WHERE telegram_id = ? AND created_at >= ? "
            "ORDER BY id DESC LIMIT ?",
            (telegram_id, since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def log_discovery(telegram_id: int, kind: str, headline: str, body: str,
                  evidence: list | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO user_discoveries (telegram_id, kind, headline, body, evidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (telegram_id, kind, headline[:120], body[:600],
             json.dumps(evidence or [], ensure_ascii=False), _now()),
        )
        return cur.lastrowid


def get_last_discovery(telegram_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, kind, headline, body, evidence, shown, created_at FROM user_discoveries "
            "WHERE telegram_id = ? ORDER BY id DESC LIMIT 1", (telegram_id,)
        ).fetchone()
    if not row:
        return None
    try:
        ev = json.loads(row["evidence"] or "[]")
    except ValueError:
        ev = []
    return {"id": row["id"], "kind": row["kind"], "headline": row["headline"],
            "body": row["body"], "evidence": ev, "shown": bool(row["shown"]),
            "created_at": row["created_at"]}


def mark_discovery_shown(discovery_id: int, telegram_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_discoveries SET shown = 1 WHERE id = ? AND telegram_id = ?",
            (discovery_id, telegram_id))


def get_notification_state(telegram_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_sent_at, sent_today_count, last_day, last_type "
            "FROM user_notification_state WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    if not row:
        return {"last_sent_at": None, "sent_today_count": 0, "last_day": "", "last_type": ""}
    return {"last_sent_at": row["last_sent_at"], "sent_today_count": row["sent_today_count"] or 0,
            "last_day": row["last_day"] or "", "last_type": row["last_type"] or ""}


def bump_notification_state(telegram_id: int, ntype: str):
    today = datetime.now(timezone.utc).date().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT sent_today_count, last_day FROM user_notification_state WHERE telegram_id = ?",
            (telegram_id,)).fetchone()
        if row and row["last_day"] == today:
            count = (row["sent_today_count"] or 0) + 1
        else:
            count = 1
        conn.execute(
            """INSERT INTO user_notification_state
               (telegram_id, last_sent_at, sent_today_count, last_day, last_type)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   last_sent_at = excluded.last_sent_at,
                   sent_today_count = excluded.sent_today_count,
                   last_day = excluded.last_day,
                   last_type = excluded.last_type""",
            (telegram_id, _now(), count, today, ntype),
        )