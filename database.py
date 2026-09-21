"""
БД ARENA: профиль, баллы, история боёв, 10 критериев, достижения, словарь ошибок,
история уровня, разбор Храма, скиллы, квесты, немезида, свободные разговоры,
память Арены (интересы/темы), история пушей.
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from config import DB_PATH, BATTLE_COOLDOWN_HOURS
from game_data import ALL_CRITERIA

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id      INTEGER PRIMARY KEY,
    username         TEXT,
    first_name       TEXT,
    total_points     INTEGER NOT NULL DEFAULT 0,
    first_battle_done INTEGER NOT NULL DEFAULT 0,
    temple_done      INTEGER NOT NULL DEFAULT 0,
    language         TEXT,
    push_personality TEXT,
    push_topics      TEXT,
    last_push_topic  TEXT,
    behaviour        TEXT,
    title            TEXT,
    nemesis_defeated INTEGER NOT NULL DEFAULT 0,
    last_push_at     TEXT,
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
    conviction_final    INTEGER,
    quest_done          INTEGER NOT NULL DEFAULT 0,
    won                 INTEGER NOT NULL DEFAULT 0,
    overall             INTEGER,
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

-- Накопленная шкала по 10 критериям (скользящее среднее по всем разговорам)
CREATE TABLE IF NOT EXISTS user_criteria (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    criterion     TEXT NOT NULL,
    value         INTEGER NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (telegram_id, criterion)
);

CREATE TABLE IF NOT EXISTS user_skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    skill         TEXT NOT NULL,
    points        INTEGER NOT NULL DEFAULT 0,
    battles       INTEGER NOT NULL DEFAULT 0,
    rank          INTEGER NOT NULL DEFAULT 1,
    UNIQUE (telegram_id, skill)
);

CREATE TABLE IF NOT EXISTS user_quests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER NOT NULL,
    quest_type    TEXT NOT NULL,
    description   TEXT NOT NULL,
    target        INTEGER NOT NULL DEFAULT 1,
    current       INTEGER NOT NULL DEFAULT 0,
    completed     INTEGER NOT NULL DEFAULT 0,
    skill_bonus   TEXT,
    created_at    TEXT NOT NULL,
    expires_at    TEXT
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
            ("first_battle_done", "INTEGER NOT NULL DEFAULT 0"),
            ("temple_done", "INTEGER NOT NULL DEFAULT 0"),
            ("language", "TEXT"),
            ("push_personality", "TEXT"),
            ("push_topics", "TEXT"),
            ("last_push_topic", "TEXT"),
            ("behaviour", "TEXT"),
            ("title", "TEXT"),
            ("nemesis_defeated", "INTEGER NOT NULL DEFAULT 0"),
            ("last_push_at", "TEXT"),
        ]:
            _add_col("users", col, f"ALTER TABLE users ADD COLUMN {col} {ddl}")

        for col, ddl in [
            ("strength", "TEXT"), ("growth", "TEXT"), ("growth_plan", "TEXT"),
            ("conviction_final", "INTEGER"), ("quest_done", "INTEGER NOT NULL DEFAULT 0"),
            ("won", "INTEGER NOT NULL DEFAULT 0"), ("overall", "INTEGER"), ("criteria", "TEXT"),
        ]:
            _add_col("game_sessions", col, f"ALTER TABLE game_sessions ADD COLUMN {col} {ddl}")

        _add_col("arena_analyses", "recommended_personality",
                 "ALTER TABLE arena_analyses ADD COLUMN recommended_personality TEXT")

        # Пользователи, уже игравшие бой, точно прошли Храм.
        conn.execute("UPDATE users SET temple_done = 1 WHERE first_battle_done = 1 AND temple_done = 0")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_later() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


# ---------- Users ----------

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
            "INSERT INTO users (telegram_id, username, first_name, total_points, first_battle_done, "
            "created_at, updated_at) VALUES (?, ?, ?, 0, 0, ?, ?)",
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


def has_completed_temple(telegram_id: int) -> bool:
    """Храм (первые 8 реплик) пройден — можно показывать полное меню."""
    with get_conn() as conn:
        row = conn.execute("SELECT temple_done FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return bool(row and row["temple_done"])


def mark_temple_done(telegram_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET temple_done = 1, updated_at = ? WHERE telegram_id = ?",
                     (_now(), telegram_id))


def set_user_language(telegram_id: int, language: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET language = ?, updated_at = ? WHERE telegram_id = ?",
                     (language, _now(), telegram_id))


def get_user_language(telegram_id: int) -> str | None:
    """Язык, который человек выбрал в Храме. Запасной вариант — язык последнего боя."""
    with get_conn() as conn:
        row = conn.execute("SELECT language FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row and row["language"]:
            return row["language"]
        row = conn.execute(
            "SELECT language FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()
    return row["language"] if row else None


# Старое имя — оставлено для совместимости
get_last_language = get_user_language


def set_user_behaviour_title(telegram_id: int, behaviour: str, title: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET behaviour = ?, title = ?, updated_at = ? WHERE telegram_id = ?",
            (behaviour, title, _now(), telegram_id),
        )


def add_points(telegram_id: int, points: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET total_points = total_points + ?, updated_at = ? WHERE telegram_id = ?",
            (points, _now(), telegram_id),
        )


def reset_user_data(telegram_id: int):
    """Полный сброс — только для админов (config.is_admin)."""
    with get_conn() as conn:
        for table in (
            "game_sessions", "achievements", "vocabulary_mistakes",
            "user_level_history", "arena_analyses", "freetalk_sessions",
            "user_criteria", "user_skills", "user_quests", "user_nemesis",
        ):
            conn.execute(f"DELETE FROM {table} WHERE telegram_id = ?", (telegram_id,))
        conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))


# ---------- Push ----------

def set_push_profile(telegram_id: int, personality: str, topics: list):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET push_personality = ?, push_topics = ?, updated_at = ? WHERE telegram_id = ?",
            (personality, json.dumps(topics, ensure_ascii=False), _now(), telegram_id),
        )


def get_all_push_profiles() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT telegram_id, push_personality, push_topics, first_name, last_push_at, language "
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
            "language": row["language"],
        })
    return result


def mark_push_sent(telegram_id: int, topic: str = ""):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_push_at = ?, last_push_topic = ? WHERE telegram_id = ?",
            (_now(), topic, telegram_id),
        )


def pop_push_topic(telegram_id: int) -> str | None:
    """Тема последнего пуша (если он был не старше 36 ч) — бой по кнопке пуша идёт именно на неё."""
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
    """Новые интересы — вперёд списка, дубликаты убираем, список ограничен."""
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


def get_memory(telegram_id: int) -> dict:
    """Что Арена помнит о человеке: интересы, недавние темы, последние его реплики."""
    interests = get_interests(telegram_id)
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
    return {"interests": interests, "recent_topics": recent, "last_said": said}


# ---------- Sessions ----------

def save_game_session(
        telegram_id: int, personality: str, language: str, level: str, topic: str,
        rounds_completed: int, scores: dict, points_earned: int,
        strength: str = "", growth: str = "", growth_plan: str = "",
        conviction_final: int = 0, quest_done: int = 0, won: int = 0, overall: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO game_sessions
               (telegram_id, personality, language, level, topic, rounds_completed,
                argumentation_score, vocabulary_score, grammar_score, fluency_score,
                points_earned, strength, growth, growth_plan, conviction_final, quest_done,
                won, overall, criteria, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id, personality, language, level, topic, rounds_completed,
                scores.get("argumentation"), scores.get("vocabulary"),
                scores.get("grammar"), scores.get("fluency"),
                points_earned, strength, growth, growth_plan, conviction_final, quest_done,
                won, overall, json.dumps(scores, ensure_ascii=False), _now(),
            ),
        )
        return cur.lastrowid


def get_user_stats(telegram_id: int) -> dict:
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        sessions = conn.execute(
            "SELECT * FROM game_sessions WHERE telegram_id = ? ORDER BY id DESC", (telegram_id,)
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
        "last_sessions": sessions[:5],
        "latest_strength": latest["strength"] if latest else "",
        "latest_growth": latest["growth"] if latest else "",
        "latest_growth_plan": latest["growth_plan"] if latest else "",
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
    """Сколько часов прошло с последнего боя. None — боёв не было."""
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
    return (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600


def has_battled_today(telegram_id: int) -> bool:
    """Правило «один бой в 24 часа» (BATTLE_COOLDOWN_HOURS). Админов обходят handlers."""
    hours = get_hours_since_last_battle(telegram_id)
    return hours is not None and hours < BATTLE_COOLDOWN_HOURS


def cooldown_hours_left(telegram_id: int) -> float:
    hours = get_hours_since_last_battle(telegram_id)
    if hours is None:
        return 0.0
    return max(0.0, BATTLE_COOLDOWN_HOURS - hours)


def get_recent_avg_scores(telegram_id: int, n: int = 3, level: str | None = None) -> float | None:
    """
    Средний общий балл (по 10 критериям) за последние n боёв.
    Если задан level — учитываются только бои на этом уровне и нужно ровно n таких боёв
    (иначе None): так уровень не прыгает после каждого боя.
    """
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


# ---------- Criteria (10 критериев) ----------

def update_criteria(telegram_id: int, scores: dict, weight: float = 0.4):
    """
    Скользящее среднее: new = old*(1-weight) + score*weight.
    Храм: weight=1 (первичная оценка), бой: 0.4, free talk: 0.2.
    """
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


def mark_word_learned(telegram_id: int, wrong: str):
    with get_conn() as conn:
        conn.execute("UPDATE vocabulary_mistakes SET learned = 1 WHERE telegram_id = ? AND wrong = ?",
                     (telegram_id, wrong))


def count_learned_words(telegram_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM vocabulary_mistakes WHERE telegram_id = ? AND learned = 1",
            (telegram_id,)).fetchone()
    return row["cnt"] if row else 0


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


# ---------- Arena analysis (разбор Храма) ----------

def save_arena_analysis(telegram_id: int, analysis: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO arena_analyses
               (telegram_id, language_metrics, communication, hidden_metrics,
                grammar_weak, vocabulary_weak, behaviour, weakest_skill,
                strongest_skill, arena_rank, interests, main_topic, level,
                recommended_personality, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
    }


# ---------- Skills (XP за тренировку с персонажами) ----------

SKILL_NAMES = ["clarity", "argumentation", "evidence", "persuasion", "adaptability", "control"]


def init_user_skills(telegram_id: int):
    with get_conn() as conn:
        for sk in SKILL_NAMES:
            conn.execute(
                "INSERT OR IGNORE INTO user_skills (telegram_id, skill, points, battles, rank) "
                "VALUES (?, ?, 0, 0, 1)", (telegram_id, sk))


def get_skill_points(telegram_id: int, skill: str) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT points FROM user_skills WHERE telegram_id = ? AND skill = ?",
                           (telegram_id, skill)).fetchone()
    return row["points"] if row else 0


def add_skill_progress(telegram_id: int, skill: str, delta: int, battles: int = 1):
    init_user_skills(telegram_id)
    with get_conn() as conn:
        conn.execute(
            """UPDATE user_skills
               SET points = points + ?,
                   battles = battles + ?,
                   rank = CASE
                       WHEN points + ? >= 1000 THEN 6
                       WHEN points + ? >= 800  THEN 5
                       WHEN points + ? >= 600  THEN 4
                       WHEN points + ? >= 400  THEN 3
                       WHEN points + ? >= 200  THEN 2
                       ELSE 1
                   END
               WHERE telegram_id = ? AND skill = ?""",
            (delta, battles, delta, delta, delta, delta, delta, telegram_id, skill),
        )


def get_all_skills(telegram_id: int) -> dict[str, dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT skill, points, battles, rank FROM user_skills WHERE telegram_id = ?", (telegram_id,)
        ).fetchall()
    return {r["skill"]: {"points": r["points"], "battles": r["battles"], "rank": r["rank"]} for r in rows}


# ---------- Quests ----------

def set_quest(telegram_id: int, quest_type: str, description: str, target: int = 1, skill_bonus: str = ""):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_quests WHERE telegram_id = ?", (telegram_id,))
        conn.execute(
            """INSERT INTO user_quests (telegram_id, quest_type, description, target, current, completed,
                                        skill_bonus, created_at, expires_at)
               VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)""",
            (telegram_id, quest_type, description, target, skill_bonus, _now(), _week_later()),
        )


def get_active_quest(telegram_id: int) -> dict | None:
    """Активный (не выполненный и не просроченный) квест."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_quests WHERE telegram_id = ? AND completed = 0 ORDER BY id DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()
    if not row:
        return None
    if row["expires_at"]:
        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                return None
        except ValueError:
            pass
    return {
        "id": row["id"], "type": row["quest_type"], "description": row["description"],
        "target": row["target"], "current": row["current"], "skill_bonus": row["skill_bonus"],
    }


def complete_quest(telegram_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE user_quests SET completed = 1 WHERE telegram_id = ? AND completed = 0",
                     (telegram_id,))


def delete_quest(telegram_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_quests WHERE telegram_id = ?", (telegram_id,))


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

def get_user_first_name(telegram_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT first_name FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    return row["first_name"] if row and row["first_name"] else ""
