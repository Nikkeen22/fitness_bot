from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import challenges as ch

# --- Постійне меню ---
main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[

        [KeyboardButton(text="📝 Мій план"), KeyboardButton(text="📊 Прогрес")],
        [KeyboardButton(text="🥑 Додати їжу"), KeyboardButton(text="⚙️ Інструменти")],
        [KeyboardButton(text="💬 Чат з AI-тренером")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Оберіть дію з меню"
)

# --- Меню інструментів ---
tools_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎯 Публічні челенджі", callback_data="tool_challenges")],
    [InlineKeyboardButton(text="📝 Створити свій челендж", callback_data="tool_create_challenge")],
    [InlineKeyboardButton(text="⚔️ Кинути виклик (Дуель)", callback_data="tool_duel")],
    [InlineKeyboardButton(text="💪 Поділитися результатом", callback_data="share_result")],
    [InlineKeyboardButton(text="📸 Мої результати", callback_data="my_results")],
    [InlineKeyboardButton(text="⚖️ Калькулятор калорій", callback_data="tool_calories")],
    [InlineKeyboardButton(text="⏰ Налаштувати нагадування", callback_data="tool_reminders")],
    [InlineKeyboardButton(text="📖 Команди (Help)", callback_data="tool_help")],
    [InlineKeyboardButton(text="Мій звіт про калорії", callback_data="tool_calories_report")],
])


# ... (решта клавіатур без змін)
goal_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Схуднути")], [KeyboardButton(text="Набрати м'язи")], [KeyboardButton(text="Підтримати форму")]], resize_keyboard=True, one_time_keyboard=True)
conditions_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Вдома без інвентарю")], [KeyboardButton(text="Вдома (є гантелі/турнік)")], [KeyboardButton(text="Тренажерний зал")]], resize_keyboard=True, one_time_keyboard=True)
confirm_workout_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я виконав(ла)", callback_data="workout_done")]])
feedback_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="1️⃣", callback_data="feedback_rating:1"), InlineKeyboardButton(text="2️⃣", callback_data="feedback_rating:2"), InlineKeyboardButton(text="3️⃣", callback_data="feedback_rating:3"), InlineKeyboardButton(text="4️⃣", callback_data="feedback_rating:4"), InlineKeyboardButton(text="5️⃣", callback_data="feedback_rating:5")]])
subscribe_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оплатити підписку (1 міс. - 49 грн)", callback_data="initiate_payment")]])
confirm_user_payment_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Я оплатив(ла)", callback_data="user_confirm_payment")]])

def get_admin_payment_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити", callback_data=f"admin_confirm:{user_id}")
    builder.button(text="❌ Відхилити", callback_data=f"admin_reject:{user_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_challenges_kb(challenges):
    builder = InlineKeyboardBuilder()
    for challenge_id, title in challenges:
        builder.button(text=title, callback_data=f"view_challenge:{challenge_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_challenge_action_kb(challenge_id: int, is_participant: bool):
    builder = InlineKeyboardBuilder()
    if is_participant:
        builder.button(text="✅ Відмітити виконання сьогодні", callback_data=f"do_challenge:{challenge_id}")
    else:
        builder.button(text="🚀 Приєднатися", callback_data=f"join_challenge:{challenge_id}")
    builder.button(text="⬅️ Назад до списку", callback_data="back_to_challenges_list")
    builder.adjust(1)
    return builder.as_markup()

def get_duel_action_kb(duel_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Я виконав завдання (надіслати відео)", callback_data=f"complete_duel:{duel_id}")
    return builder.as_markup()

def get_meal_confirmation_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, записати", callback_data="confirm_meal")
    builder.button(text="❌ Ні, скасувати", callback_data="cancel_meal")
    return builder.as_markup()