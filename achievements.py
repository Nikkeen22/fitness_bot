import database as db
from aiogram import Bot
from config import GROUP_ID
from utils.safe_sender import send_message_safely

SIGNIFICANT_ACHIEVEMENTS = ['marathoner', 'stability']

ACHIEVEMENTS = {
    'novice': {'name': '🎓 Новачок', 'description': 'Створили свій перший фітнес-план!'},
    'first_step': {'name': '🚀 Перший крок', 'description': 'Виконали своє перше тренування!'},
    'stability': {'name': '⚖️ Стабільність', 'description': '3 тренування за останні 7 днів!'},
    'chef': {'name': '👨‍🍳 Шеф-кухар', 'description': 'Використали функцію генерації рецептів.'},
    'marathoner': {'name': '🏃‍♂️ Марафонець', 'description': 'Ви з нами вже цілий місяць!'},
    'challenger': {'name': '🎯 Челенджер', 'description': 'Прийняли свій перший виклик!'}
}

async def check_and_grant_achievement(user_id: int, achievement_id: str, bot: Bot):
    if not await db.has_achievement(user_id, achievement_id):
        await db.grant_achievement(user_id, achievement_id)
        achievement = ACHIEVEMENTS[achievement_id]
        
        # Надсилаємо особисте повідомлення
        await send_message_safely(bot, user_id, f"🎉 **Нове досягнення!** 🎉\n\nВи отримали ачівку: **{achievement['name']}**\n_{achievement['description']}_")

        # --- Повідомлення у спільноту ---
        if GROUP_ID:
            try:
                user_info = await bot.get_chat(user_id)
                username = f"@{user_info.username}" if user_info.username else user_info.full_name
                group_message = (
                    f" <b>Нове досягнення!</b> \n\n"
                    f"{username} отримав(ла) ачівку: <b>{achievement['name']}</b>\n"
                    f"<i>{achievement['description']}</i>"
                )
                await send_message_safely(bot, int(GROUP_ID), group_message, parse_mode="HTML")
            except Exception as e:
                import traceback
                print(f"Не вдалося відправити у групу: {e}")
                traceback.print_exc()


async def check_workout_achievements(user_id: int, bot: Bot):
    if await db.count_total_workouts(user_id) == 1:
        await check_and_grant_achievement(user_id, 'first_step', bot)
    if await db.count_workouts_last_n_days(user_id, 7) >= 3:
        await check_and_grant_achievement(user_id, 'stability', bot)

