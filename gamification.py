"""
Геймификация Arena 2.0: баллы, игровые уровни, достижения.
Логика отделена от базы данных и хендлеров.
"""
import database as db
from game_data import BADGES, PERSONALITIES

# Игровые уровни (баллы)
PLAYER_LEVELS = [
    {"name": "🌱 Новичок", "min_points": 0},
    {"name": "⚔️ Искатель", "min_points": 100},
    {"name": "🔥 Боец", "min_points": 300},
    {"name": "🧠 Мастер", "min_points": 600},
    {"name": "🏆 Легенда", "min_points": 1000},
]

# Начисление баллов за игровой раунд
POINTS_PER_ROUND = 10
COMPLETION_BONUS = 20
HIGH_SCORE_BONUS = 15  # если средний балл > 80


def calculate_points(rounds_completed: int, scores: dict) -> int:
    """Рассчитывает баллы за одну игру."""
    points = rounds_completed * POINTS_PER_ROUND
    if rounds_completed >= 3:
        points += COMPLETION_BONUS

    if scores:
        avg = sum(scores.values()) / len(scores) if scores else 0
        if avg > 80:
            points += HIGH_SCORE_BONUS

    return min(points, 200)  # кап на раунд


def get_player_level(total_points: int) -> dict:
    """Возвращает игровой уровень по количеству баллов."""
    current = PLAYER_LEVELS[0]
    next_level = None

    for i, lvl in enumerate(PLAYER_LEVELS):
        if total_points >= lvl["min_points"]:
            current = lvl
            if i < len(PLAYER_LEVELS) - 1:
                next_level = PLAYER_LEVELS[i + 1]

    return {
        "current": current,
        "next": next_level,
        "points_to_next": next_level["min_points"] - total_points if next_level else None,
    }


def check_and_unlock_achievements(telegram_id: int, personality: str, rounds: int, scores: dict) -> list[str]:
    """
    Проверяет условия достижений и разблокирует новые.
    Возвращает список ключей разблокированных бейджей.
    """
    unlocked = []

    # first_debate
    if not db.unlock_achievement(telegram_id, "first_debate"):
        pass  # уже есть
    else:
        unlocked.append("first_debate")

    # grammar_master
    if scores.get("grammar", 0) >= 90:
        if db.unlock_achievement(telegram_id, "grammar_master"):
            unlocked.append("grammar_master")

    # wordsmith
    if scores.get("vocabulary", 0) >= 90:
        if db.unlock_achievement(telegram_id, "wordsmith"):
            unlocked.append("wordsmith")

    # marathoner
    if rounds >= 10:
        if db.unlock_achievement(telegram_id, "marathoner"):
            unlocked.append("marathoner")

    # all_characters
    stats = db.get_user_stats(telegram_id)
    if len(stats["unique_personalities"]) >= len(PERSONALITIES):
        if db.unlock_achievement(telegram_id, "all_characters"):
            unlocked.append("all_characters")

    # high_scorer
    if stats.get("avg_score") and stats["avg_score"] >= 85:
        if db.unlock_achievement(telegram_id, "high_scorer"):
            unlocked.append("high_scorer")

    return unlocked


def format_profile(telegram_id: int, first_name: str) -> str:
    """Форматирует профиль пользователя."""
    stats = db.get_user_stats(telegram_id)
    level_info = get_player_level(stats["total_points"])

    text = f"""
👤 <b>Профиль игрока</b>
{first_name}

📊 <b>Баллы</b>
{stats["total_points"]}

🏅 <b>Уровень</b>
{level_info["current"]["name"]}
"""
    if level_info["next"]:
        text += f"До {level_info['next']['name']}: {level_info['points_to_next']} баллов\n"

    text += f"""
🎮 <b>Игр сыграно</b>
{stats["games_played"]}

🎭 <b>Персонажей встречено</b>
{len(stats["unique_personalities"])} из {len(PERSONALITIES)}

📈 <b>Средний балл</b>
{stats["avg_score"] or "—"}%

🏆 <b>Достижения</b>
{len(stats["achievements"])} / {len(BADGES)}
"""
    return text


def format_achievements(telegram_id: int) -> str:
    """Форматирует список достижений."""
    stats = db.get_user_stats(telegram_id)
    unlocked = set(stats["achievements"])

    if not unlocked:
        return "🏆 <b>Достижения</b>\n\nПока нет разблокированных достижений. Сыграй несколько игр, чтобы открыть их!"

    lines = ["🏆 <b>Достижения</b>\n"]
    for key, badge in BADGES.items():
        status = "✅" if key in unlocked else "⬜"
        lines.append(f"{status} {badge['name']} — {badge['description']}")

    return "\n".join(lines)


# ---------- ARENA XP (отдельная система, 100 XP = уровень) ----------
# Battle Score (0-30, за конкретный бой) и Arena XP (общий прогресс по кампании) —
# разные вещи, см. пункт "XP SYSTEM" в ТЗ. XP_REWARDS — в game_data.py.

def award_arena_xp(telegram_id: int, band_key: str) -> dict:
    """Начисляет Arena XP по итогам боя (band_key: defeated/almost/victory/outplayed).
    Возвращает {'xp': итоговый XP, 'level': уровень, 'leveled_up': bool, 'xp_gained': int}."""
    from game_data import XP_REWARDS
    xp_gained = XP_REWARDS.get(band_key, 5)
    result = db.add_arena_xp(telegram_id, xp_gained)
    result["xp_gained"] = xp_gained
    return result