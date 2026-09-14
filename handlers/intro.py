import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
from config import FIRST_ENCOUNTER_MOVES, BATTLE_DURATION_MINUTES
from game_data import LANGUAGES, PERSONALITIES, ARENA_UI_STRINGS, BEGINNER_LEVELS

logger = logging.getLogger(__name__)

FE_STATE_KEYS = ["fe_language", "fe_dialogue", "fe_awaiting_response"]


def _reset_fe_state(context: ContextTypes.DEFAULT_TYPE):
    for key in FE_STATE_KEYS:
        context.user_data.pop(key, None)


async def enter_arena_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_fe_state(context)
    keyboard = [
        [InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"fe_lang_{key}")]
        for key, data in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])
    text = "🏛️ <b>ARENA</b>\n\nВыбери язык."
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.replace("fe_lang_", "")
    context.user_data["fe_language"] = language
    context.user_data["fe_dialogue"] = []
    context.user_data["fe_awaiting_response"] = True

    await query.edit_message_text(
        "🏛️ <b>ARENA IS LISTENING.</b>\n\n"
        "<b>Your move.</b>\n\n"
        "<i>what I do · what I love · what I think · anything</i>",
        parse_mode="HTML",
    )


async def handle_fe_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if len(user_text) < 1:
        return

    dialogue = context.user_data.setdefault("fe_dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    context.user_data["fe_awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")

    if user_turns >= FIRST_ENCOUNTER_MOVES:
        await _reveal(update, context)
        return

    language = context.user_data.get("fe_language", "english")
    history = "\n".join(f"{'User' if d['speaker'] == 'User' else 'ARENA'}: {d['text']}" for d in dialogue)

    reaction = await asyncio.to_thread(
        ai.generate_arena_reaction,
        history,
        user_text,
        language,
        user_turns + 1,
    )
    dialogue.append({"speaker": "AI", "text": reaction})
    context.user_data["fe_awaiting_response"] = True

    await update.message.reply_text(reaction)


async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("fe_language", "english")
    dialogue = context.user_data.get("fe_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    result = await asyncio.to_thread(ai.analyze_first_encounter, user_responses, language)

    level = result["estimated_level"]
    personality = result["recommended_personality"]
    topic = result.get("main_topic") or result.get("interests", ["интересная тема"])[0]

    # --- Всё, что дал разбор, кладём в context ---
    context.user_data["level"] = level
    context.user_data["personality"] = personality
    context.user_data["language"] = language
    context.user_data["user_interests"] = result.get("interests", [])
    context.user_data["topic"] = topic

    arena_analysis = {
        "language": result.get("language", {}),
        "grammar_weak_areas": result.get("grammar_weak_areas", []),
        "vocabulary_weak_areas": result.get("vocabulary_weak_areas", []),
        "communication": result.get("communication", {}),
        "hidden": result.get("hidden", {}),
        "behaviour": result.get("behaviour", "explorer"),
        "weakest_skill": result.get("weakest_skill", ""),
        "strongest_skill": result.get("strongest_skill", ""),
        "arena_rank": result.get("arena_rank", {}),
        "interests": result.get("interests", []),
        "main_topic": topic,
        "estimated_level": level,
    }
    context.user_data["arena_analysis"] = arena_analysis

    # --- Инициализация геймификации ---
    user_id = update.effective_user.id
    db.init_user_skills(user_id)

    # Квест — персонализирован под слабый скилл/стиль поведения
    quest = gamification.generate_quest(result)
    db.set_quest(user_id, quest["type"], quest["description"], quest["target"], quest["skill_bonus"])

    # Немезида
    db.set_nemesis(user_id, result["behaviour"])

    # Титул
    title = gamification.get_title(result["behaviour"], 1)
    db.set_user_behaviour_title(user_id, result["behaviour"], title)

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    ui = ARENA_UI_STRINGS.get(language) or ARENA_UI_STRINGS["english"]

    observation = await asyncio.to_thread(
        ai.generate_arena_observation, user_responses, language, level,
        result["strongest_skill"], result["weakest_skill"],
    )
    pitch = await asyncio.to_thread(ai.generate_character_pitch, personality, topic, language, level)
    opening = await asyncio.to_thread(ai.generate_opening_statement, personality, topic, level, language)

    # Оружие + совет, персонализированные под слабые места, вскрытые Храмом.
    weapons, tip, win_condition = await asyncio.to_thread(
        ai.generate_mission_weapons, topic, level, personality, language,
        arena_analysis, result.get("weakest_skill"),
    )

    context.user_data["mission_weapons"] = weapons
    context.user_data["mission_tip"] = tip
    context.user_data["win_condition"] = win_condition
    context.user_data["used_weapons"] = []
    context.user_data["mission"] = (
        f"{person['short_name']} is testing the user's {result['weakest_skill']} "
        f"on the topic: {topic}. Stay in character, don't let the user change the subject."
    )

    # --- Сохраняем всё в БД ---
    db.set_push_profile(update.effective_user.id, personality, result.get("interests", [topic]))
    db.add_level_snapshot(update.effective_user.id, level, source="arena_reveal")
    db.save_arena_analysis(update.effective_user.id, arena_analysis)

    is_beginner = level in BEGINNER_LEVELS
    weapon_label = ui["arsenal"] if not is_beginner else f"{ui['arsenal']} ({level})"
    tip_block = f"\n💡 {tip}\n" if tip else ""

    text = (
        f"🏛️ {ui['heard_enough']}\n\n"
        f"{observation}\n\n"
        f"⚔️ {person['short_name'].upper()}\n"
        f"{person['role']}\n\n"
        f"{pitch}\n\n"
        f"{person['short_name']}:\n"
        f"\"{opening}\"\n\n"
        f"{ui['your_move']}\n\n"
        f"🗡️ {weapon_label}\n"
        f"{weapons}\n"
        f"{tip_block}\n"
        f"{BATTLE_DURATION_MINUTES} {ui['min']}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ {ui['enter_battle']} →", callback_data="fe_start_battle")]
    ])

    photo = person.get("photo")
    if photo:
        try:
            await update.message.reply_photo(photo=photo, caption=text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

    _reset_fe_state(context)


async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    personality = context.user_data.get("personality", "hr_manager")
    language = context.user_data.get("language", "english")
    topic = context.user_data.get("topic", "интересную тему")

    level = (
        context.user_data.get("level")
        or db.get_current_level(update.effective_user.id)
        or "B1"
    )
    context.user_data["level"] = level

    weapons = context.user_data.get("mission_weapons", "")
    tip = context.user_data.get("mission_tip", "")
    mission = context.user_data.get("mission") or f"Убедить {personality} в теме «{topic}»."

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    opening = await asyncio.to_thread(ai.generate_opening_statement, personality, topic, level, language)

    from bot import start_arena_timer
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    start_arena_timer(context, user_id, chat_id, minutes=BATTLE_DURATION_MINUTES)

    context.user_data["dialogue"] = [{"speaker": "AI", "text": opening}]
    context.user_data["awaiting_response"] = True
    context.user_data["turn"] = 0
    context.user_data["personality"] = personality
    context.user_data["mission_weapons"] = weapons
    context.user_data["used_weapons"] = []
    context.user_data["language"] = language
    context.user_data["level"] = level
    context.user_data["topic"] = topic
    context.user_data["mission"] = mission
    context.user_data["conviction"] = 100

    tip_block = f"\n💡 <i>{tip}</i>\n" if tip else ""

    await query.edit_message_text(
        f"⚔️ <b>БИТВА НАЧАЛАСЬ!</b>\n\n"
        f"🎭 <b>{person['full_name']}:</b>\n"
        f"<i>{opening}</i>\n"
        f"{tip_block}\n"
        f"💬 Напиши свой ответ!\n"
        f"⏰ <i>У тебя {BATTLE_DURATION_MINUTES} минуты!</i>\n\n"
        f"🗡️ <b>Твоё оружие:</b> {weapons}",
        parse_mode="HTML"
    )