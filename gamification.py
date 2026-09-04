"""
Геймификация: уровни игрока по опыту, начисление баллов за пройденные этапы,
разблокировка достижений и текст профиля.
"""
from game_data import BADGES, PERSONALITIES
import database as db

# Пороги баллов для игрового уровня (не путать с уровнем CEFR!)
PLAYER_LEVELS = [
    (0, "🌱 Новичок"),
    (20, "🔤 Практикант"),
    (60, "💬 Собеседник"),
    (150, "⚔️ Спорщик"),
    (300, "🎯 Профи"),
    (600, "🏆 Мастер Арены"),
    (1000, "👑 Легенда"),
]

POINTS_PER_ROUND = 2       # баллы за каждый пройденный раунд (этап) диалога
COMPLETION_BONUS = 5       # бонус за то, что довёл раунд до конца (получил фидбэк)
HIGH_SCORE_BONUS = 5       # бонус, если средний скор за раунд > 80


def get_player_level(total_points: int) -> str:
    label = PLAYER_LEVELS[0][1]
    for threshold, name in PLAYER_LEVELS:
        if total_points >= threshold:
            label = name
        else:
            break
    return label


def next_level_progress(total_points: int) -> tuple[str, int] | None:
    """Возвращает (название следующего уровня, сколько баллов до него) или None, если уровень максимальный."""
    for threshold, name in PLAYER_LEVELS:
        if total_points < threshold:
            return name, threshold - total_points
    return None


def calculate_points(rounds_completed: int, scores: dict) -> int:
    points = rounds_completed * POINTS_PER_ROUND + COMPLETION_BONUS
    values = [v for v in scores.values() if v is not None]
    if values and (sum(values) / len(values)) > 80:
        points += HIGH_SCORE_BONUS
    return points


def check_and_unlock_achievements(telegram_id: int, personality: str, rounds_completed: int, scores: dict) -> list[str]:
    """Проверяет условия и разблокирует новые бейджи. Возвращает список НОВЫХ бейджей (для уведомления)."""
    newly_unlocked = []

    def try_unlock(key: str):
        if db.unlock_achievement(telegram_id, key):
            newly_unlocked.append(key)

    try_unlock("first_debate")

    if rounds_completed >= 10:
        try_unlock("marathoner")

    if scores.get("grammar") and scores["grammar"] > 90:
        try_unlock("grammar_master")

    if scores.get("vocabulary") and scores["vocabulary"] > 90:
        try_unlock("wordsmith")

    values = [v for v in scores.values() if v is not None]
    if values and (sum(values) / len(values)) > 85:
        try_unlock("high_scorer")

    stats = db.get_user_stats(telegram_id)
    played_all = set(PERSONALITIES.keys()).issubset(stats["unique_personalities"] | {personality})
    if played_all:
        try_unlock("all_characters")

    return newly_unlocked


def format_profile(telegram_id: int, first_name: str) -> str:
    stats = db.get_user_stats(telegram_id)
    level_name = get_player_level(stats["total_points"])
    progress = next_level_progress(stats["total_points"])

    lines = [
        f"👤 <b>{first_name}</b>",
        "",
        f"🏅 Уровень: <b>{level_name}</b>",
        f"⭐ Баллы: <b>{stats['total_points']}</b>",
        f"🎮 Игр сыграно: <b>{stats['games_played']}</b>",
    ]
    if stats["avg_score"] is not None:
        lines.append(f"📊 Средний результат: <b>{stats['avg_score']}/100</b>")
    if progress:
        next_name, remaining = progress
        lines.append(f"➡️ До уровня «{next_name}»: <b>{remaining}</b> баллов")

    lines.append("")
    if stats["achievements"]:
        badge_names = ", ".join(BADGES[b]["name"] for b in stats["achievements"] if b in BADGES)
        lines.append(f"🏆 Достижения: {badge_names}")
    else:
        lines.append("🏆 Достижений пока нет — сыграй первый раунд, чтобы получить первый бейдж!")

    return "\n".join(lines)


def format_achievements(telegram_id: int) -> str:
    stats = db.get_user_stats(telegram_id)
    unlocked = set(stats["achievements"])

    lines = ["🏆 <b>Достижения</b>", ""]
    for key, badge in BADGES.items():
        mark = "✅" if key in unlocked else "🔒"
        lines.append(f"{mark} <b>{badge['name']}</b> — {badge['description']}")
    return "\n".join(lines)

def format_arena_profile(telegram_id: int) -> str:
    """
    Формирует расширенный профиль с данными ARENA.
    """
    # Здесь нужно получать данные из БД
    # Пока заглушка
    return """
🧠 <b>ARENA PROFILE</b>

📊 <b>Текущий уровень</b>
B1 → B2 (в процессе)

📈 <b>Прогресс</b>
Language Skills
  📝 Грамматика ████████░░ 82%
  📚 Словарный запас ██████░░░ 68%
  🎤 Беглость █████████░ 90%
  🧩 Сложность речи ██████░░░ 65%

Communication Skills
  💡 Ясность ████████░░ 78%
  📐 Точность формулировок ██████░░░ 62% 🎯
  ⚔️ Аргументация ███████░░░ 71%
  🔥 Убедительность ██████░░░ 60%
  🧠 Критическое мышление ███████░░░ 74%
  💪 Уверенность ████████░░ 80%

🎯 <b>Current Focus</b>
Точность формулировок

⚔️ <b>Last Battle</b>
HR Manager — Convince the HR Manager
Result: 3/4 arguments
+120 XP

🏆 <b>Battles Won</b>
6 из 12
"""