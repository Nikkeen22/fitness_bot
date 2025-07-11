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

        # --- Стіна слави ---
        if achievement_id in SIGNIFICANT_ACHIEVEMENTS and GROUP_ID:
            try:
                user_info = await bot.get_chat(user_id)
                username = f"@{user_info.username}" if user_info.username else user_info.full_name
                group_message = (
                    f"🏆 **Стіна слави!** 🏆\n\n"
                    f"Вітаємо {username} з отриманням досягнення **'{achievement['name']}'**!\n\n"
                    f"Так тримати! Ваші успіхи надихають усю спільноту! 💪"
                )
                await send_message_safely(bot, int(GROUP_ID), group_message)
            except Exception as e:
                print(f"Не вдалося відправити на Стіну слави: {e}")


async def check_workout_achievements(user_id: int, bot: Bot):
    if await db.count_total_workouts(user_id) == 1:
        await check_and_grant_achievement(user_id, 'first_step', bot)
    if await db.count_workouts_last_n_days(user_id, 7) >= 3:
        await check_and_grant_achievement(user_id, 'stability', bot)

