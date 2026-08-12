"""
Упрощённая БД под геймификацию: профиль, баллы, история игр, достижения.
Никакой логики про клубы/расписание/подписки — этого больше нет.

SQLite выбран специально: не требует отдельного сервера, легко переносить.
Если проект вырастет — можно заменить на Postgres, поменяв только этот файл.
"""
import sqlite3
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
