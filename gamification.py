"""
Геймификация ARENA: баллы, игровые уровни, достижения, профиль,
мягкая адаптация уровня персонажей под участника.
"""
import database as db
from game_data import BADGES, PERSONALITIES

PLAYER_LEVELS = [
    {"name": "🌱 Новичок", "min_points": 0},
    {"name": "⚔️ Искатель", "min_points": 100},
    {"name": "🔥 Боец", "min_points": 300},
    {"name": "🧠 Мастер", "min_points": 600},
    {"name": "🏆 Легенда", "min_points": 1000},
]

POINTS_PER_ROUND = 10
COMPLETION_BONUS = 20
HIGH_SCORE_BONUS = 15


def calculate_points(rounds_completed: int, scores: dict) -> int:
    points = rounds_completed * POINTS_PER_ROUND
    if rounds_completed >= 3:
        points += COMPLETION_BONUS
    if scores:
        avg = sum(scores.values()) / len(scores) if scores else 0
        if avg > 80:
            points += HIGH_SCORE_BONUS
    return min(points, 200)


def get_player_level(total_points: int) -> dict:
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
    unlocked = []
    if db.unlock_achievement(telegram_id, "first_debate"):
        unlocked.append("first_debate")
    if scores.get("grammar", 0) >= 90:
        if db.unlock_achievement(telegram_id, "grammar_master"):
            unlocked.append("grammar_master")
    if scores.get("vocabulary", 0) >= 90:
        if db.unlock_achievement(telegram_id, "wordsmith"):
            unlocked.append("wordsmith")
    if rounds >= 10:
        if db.unlock_achievement(telegram_id, "marathoner"):
            unlocked.append("marathoner")

    stats = db.get_user_stats(telegram_id)
    if len(stats["unique_personalities"]) >= len(PERSONALITIES):
        if db.unlock_achievement(telegram_id, "all_characters"):
            unlocked.append("all_characters")
    if stats.get("avg_score") and stats["avg_score"] >= 85:
        if db.unlock_achievement(telegram_id, "high_scorer"):
            unlocked.append("high_scorer")

    return unlocked


def format_profile(telegram_id: int, first_name: str) -> str:
    stats = db.get_user_stats(telegram_id)
    level_info = get_player_level(stats["total_points"])

    text = f"""
👤 <b>{first_name}</b>

📊 Баллы: {stats["total_points"]}
🏅 Уровень: {level_info["current"]["name"]}
"""
    if level_info["next"]:
        text += f"До {level_info['next']['name']}: {level_info['points_to_next']} баллов\n"

    text += (
        f"\n🎮 Боёв сыграно: {stats['games_played']}\n"
        f"🎭 Персонажей встречено: {len(stats['unique_personalities'])} из {len(PERSONALITIES)}\n"
        f"📈 Средний балл: {stats['avg_score'] or '—'}%\n"
        f"🏆 Достижения: {len(stats['achievements'])} / {len(BADGES)}\n"
    )

    if stats.get("latest_strength") or stats.get("latest_growth"):
        text += (
            f"\n✅ <b>Сильная сторона:</b> {stats.get('latest_strength', '—')}\n"
            f"🎯 <b>Зона роста:</b> {stats.get('latest_growth', '—')}\n"
        )

    if stats.get("latest_growth_plan"):
        text += f"\n🗺️ <b>План на следующие 10 раундов:</b>\n{stats['latest_growth_plan']}\n"

    vocab = db.get_vocabulary_to_learn(telegram_id, limit=8)
    if vocab:
        text += "\n📚 <b>Слова для заучивания</b> (были использованы неправильно):\n"
        for v in vocab:
            text += f"  • {v['wrong']} → <b>{v['correct']}</b>\n"

    return text


def format_achievements(telegram_id: int) -> str:
    stats = db.get_user_stats(telegram_id)
    unlocked = set(stats["achievements"])
    if not unlocked:
        return "🏆 <b>Достижения</b>\n\nПока нет разблокированных достижений. Сыграй несколько игр, чтобы открыть их!"
    lines = ["🏆 <b>Достижения</b>\n"]
    for key, badge in BADGES.items():
        status = "✅" if key in unlocked else "⬜"
        lines.append(f"{status} {badge['name']} — {badge['description']}")
    return "\n".join(lines)


# ---------- Мягкая адаптация уровня персонажей под участника ----------

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def adapt_level(current_level: str, avg_score: float | None) -> str:
    if avg_score is None or current_level not in LEVEL_ORDER:
        return current_level
    idx = LEVEL_ORDER.index(current_level)
    if avg_score >= 82 and idx < len(LEVEL_ORDER) - 1:
        return LEVEL_ORDER[idx + 1]
    if avg_score <= 45 and idx > 0:
        return LEVEL_ORDER[idx - 1]
    return current_level