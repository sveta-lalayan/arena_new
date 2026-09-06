"""
Упрощённая БД под геймификацию: профиль, баллы, история игр, достижения.
Никакой логики про клубы/расписание/подписки — этого больше нет.

SQLite выбран специально: не требует отдельного сервера, легко переносить.
Если проект вырастет — можно заменить на Postgres, поменяв только этот файл.
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id     INTEGER PRIMARY KEY,
    username        TEXT,
    first_name      TEXT,
    total_points    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER NOT NULL,
    personality         TEXT NOT NULL,
    language            TEXT NOT NULL,
    level               TEXT NOT NULL,
    topic               TEXT NOT NULL,
    rounds_completed     INTEGER NOT NULL DEFAULT 0,
    argumentation_score INTEGER,
    vocabulary_score    INTEGER,
    grammar_score       INTEGER,
    fluency_score       INTEGER,
    points_earned       INTEGER NOT NULL DEFAULT 0,
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

-- Arena XP отдельно от total_points (Battle Score). 100 XP = level up.
CREATE TABLE IF NOT EXISTS arena_progress (
    telegram_id   INTEGER PRIMARY KEY,
    arena_xp      INTEGER NOT NULL DEFAULT 0,
    arena_level   INTEGER NOT NULL DEFAULT 1,
    updated_at    TEXT NOT NULL
);

-- CHARACTER MEMORY: что персонаж помнит о предыдущей встрече с этим пользователем.
-- Используется для rematch ("Last time you couldn't give me evidence...")
-- и для "узнавания" персонажа при повторной встрече.
CREATE TABLE IF NOT EXISTS character_memory (
    telegram_id     INTEGER NOT NULL,
    personality     TEXT NOT NULL,
    last_mission    TEXT,
    last_weakness   TEXT,
    last_result     TEXT,
    encounters_count INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (telegram_id, personality)
);

CREATE TABLE IF NOT EXISTS arena_profiles (
    telegram_id             INTEGER PRIMARY KEY,
    level                   TEXT NOT NULL,
    language                TEXT NOT NULL,
    recommended_personality TEXT NOT NULL,
    strength_skills         TEXT,
    growth_skills           TEXT,
    total_xp                INTEGER DEFAULT 0,
    battles_won             INTEGER DEFAULT 0,
    battles_total           INTEGER DEFAULT 0,
    current_focus           TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
);

CREATE TABLE IF NOT EXISTS battle_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id       INTEGER NOT NULL,
    personality       TEXT NOT NULL,
    mission_name      TEXT NOT NULL,
    result            TEXT NOT NULL,
    score             INTEGER,
    xp_earned         INTEGER DEFAULT 0,
    skills_improved   TEXT,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_user(telegram_id: int, username: str | None, first_name: str | None) -> sqlite3.Row:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET username = ?, first_name = ?, updated_at = ? WHERE telegram_id = ?",
                (username, first_name, _now(), telegram_id),
            )
            return conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()

        now = _now()
        conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, total_points, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?)",
            (telegram_id, username, first_name, now, now),
        )
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def add_points(telegram_id: int, points: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET total_points = total_points + ?, updated_at = ? WHERE telegram_id = ?",
            (points, _now(), telegram_id),
        )


def save_game_session(
        telegram_id: int,
        personality: str,
        language: str,
        level: str,
        topic: str,
        rounds_completed: int,
        scores: dict,
        points_earned: int,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO game_sessions
               (telegram_id, personality, language, level, topic, rounds_completed,
                argumentation_score, vocabulary_score, grammar_score, fluency_score,
                points_earned, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id, personality, language, level, topic, rounds_completed,
                scores.get("argumentation"), scores.get("vocabulary"),
                scores.get("grammar"), scores.get("fluency"),
                points_earned, _now(),
            ),
        )
        return cur.lastrowid


def get_user_stats(telegram_id: int) -> dict:
    with get_conn() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        sessions = conn.execute(
            "SELECT * FROM game_sessions WHERE telegram_id = ? ORDER BY created_at DESC",
            (telegram_id,),
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

    return {
        "total_points": total_points,
        "games_played": games_played,
        "unique_personalities": unique_personalities,
        "avg_score": avg_score,
        "achievements": [a["badge_key"] for a in achievements],
        "last_sessions": sessions[:5],
    }


def unlock_achievement(telegram_id: int, badge_key: str) -> bool:
    """Возвращает True, если бейдж выдан впервые (для уведомления пользователя)."""
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO achievements (telegram_id, badge_key, unlocked_at) VALUES (?, ?, ?)",
                (telegram_id, badge_key, _now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


# ========== ARENA: функции для работы с профилем ==========

def save_arena_profile(
        telegram_id: int,
        level: str,
        language: str,
        personality: str,
        strength_skills: list,
        growth_skills: list,
        current_focus: str = None,
) -> None:
    """Сохраняет или обновляет ARENA профиль пользователя."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM arena_profiles WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()

        now = _now()
        strength_json = json.dumps(strength_skills)
        growth_json = json.dumps(growth_skills)

        if existing:
            conn.execute(
                """UPDATE arena_profiles SET
                   level = ?, language = ?, recommended_personality = ?,
                   strength_skills = ?, growth_skills = ?,
                   current_focus = ?, updated_at = ?
                   WHERE telegram_id = ?""",
                (level, language, personality, strength_json, growth_json, current_focus, now, telegram_id)
            )
        else:
            conn.execute(
                """INSERT INTO arena_profiles
                   (telegram_id, level, language, recommended_personality,
                    strength_skills, growth_skills, current_focus, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, level, language, personality, strength_json, growth_json, current_focus, now, now)
            )


def get_arena_profile(telegram_id: int) -> dict | None:
    """Получает ARENA профиль пользователя."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM arena_profiles WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()

        if not row:
            return None

        return {
            "level": row["level"],
            "language": row["language"],
            "personality": row["recommended_personality"],
            "strength_skills": json.loads(row["strength_skills"]) if row["strength_skills"] else [],
            "growth_skills": json.loads(row["growth_skills"]) if row["growth_skills"] else [],
            "total_xp": row["total_xp"],
            "battles_won": row["battles_won"],
            "battles_total": row["battles_total"],
            "current_focus": row["current_focus"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def add_xp(telegram_id: int, xp: int) -> None:
    """Добавляет XP пользователю."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE arena_profiles SET total_xp = total_xp + ?, updated_at = ? WHERE telegram_id = ?",
            (xp, _now(), telegram_id),
        )


def save_battle_result(
        telegram_id: int,
        personality: str,
        mission_name: str,
        result: str,
        score: int = None,
        xp_earned: int = 0,
        skills_improved: dict = None,
) -> int:
    """Сохраняет результат битвы."""
    with get_conn() as conn:
        if result == "won":
            conn.execute(
                "UPDATE arena_profiles SET battles_won = battles_won + 1, battles_total = battles_total + 1, updated_at = ? WHERE telegram_id = ?",
                (_now(), telegram_id)
            )
        else:
            conn.execute(
                "UPDATE arena_profiles SET battles_total = battles_total + 1, updated_at = ? WHERE telegram_id = ?",
                (_now(), telegram_id)
            )

        skills_json = json.dumps(skills_improved) if skills_improved else None
        cur = conn.execute(
            """INSERT INTO battle_results
               (telegram_id, personality, mission_name, result, score, xp_earned, skills_improved, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, personality, mission_name, result, score, xp_earned, skills_json, _now())
        )
        return cur.lastrowid


def get_battle_history(telegram_id: int, limit: int = 10) -> list:
    """Получает историю битв пользователя."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM battle_results
               WHERE telegram_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (telegram_id, limit)
        ).fetchall()

        return [
            {
                "personality": row["personality"],
                "mission_name": row["mission_name"],
                "result": row["result"],
                "score": row["score"],
                "xp_earned": row["xp_earned"],
                "skills_improved": json.loads(row["skills_improved"]) if row["skills_improved"] else {},
                "created_at": row["created_at"],
            }
            for row in rows
        ]


# ---------- ARENA XP (отдельно от Battle Score) ----------

def add_arena_xp(telegram_id: int, xp: int) -> dict:
    """Начисляет Arena XP, пересчитывает уровень (100 XP = 1 уровень).
    Возвращает {'xp': ..., 'level': ..., 'leveled_up': bool}."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM arena_progress WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        old_level = row["arena_level"] if row else 1
        old_xp = row["arena_xp"] if row else 0
        new_xp = old_xp + xp
        new_level = max(1, new_xp // 100 + 1)

        if row:
            conn.execute(
                "UPDATE arena_progress SET arena_xp = ?, arena_level = ?, updated_at = ? WHERE telegram_id = ?",
                (new_xp, new_level, _now(), telegram_id),
            )
        else:
            conn.execute(
                "INSERT INTO arena_progress (telegram_id, arena_xp, arena_level, updated_at) VALUES (?, ?, ?, ?)",
                (telegram_id, new_xp, new_level, _now()),
            )

    return {"xp": new_xp, "level": new_level, "leveled_up": new_level > old_level}


def get_arena_progress(telegram_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM arena_progress WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    if not row:
        return {"xp": 0, "level": 1}
    return {"xp": row["arena_xp"], "level": row["arena_level"]}


# ---------- CHARACTER MEMORY (для rematch и "узнавания" персонажа) ----------

def save_character_memory(telegram_id: int, personality: str, mission: str,
                          weakness: str, result: str):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT encounters_count FROM character_memory WHERE telegram_id = ? AND personality = ?",
            (telegram_id, personality),
        ).fetchone()
        count = (existing["encounters_count"] if existing else 0) + 1
        conn.execute(
            """INSERT INTO character_memory
               (telegram_id, personality, last_mission, last_weakness, last_result, encounters_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (telegram_id, personality) DO UPDATE SET
                   last_mission = excluded.last_mission,
                   last_weakness = excluded.last_weakness,
                   last_result = excluded.last_result,
                   encounters_count = excluded.encounters_count,
                   updated_at = excluded.updated_at""",
            (telegram_id, personality, mission, weakness, result, count, _now()),
        )


def get_character_memory(telegram_id: int, personality: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM character_memory WHERE telegram_id = ? AND personality = ?",
            (telegram_id, personality),
        ).fetchone()
    if not row:
        return None
    return {
        "last_mission": row["last_mission"],
        "last_weakness": row["last_weakness"],
        "last_result": row["last_result"],
        "encounters_count": row["encounters_count"],
    }