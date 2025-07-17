from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
import keyboards as kb
import achievements
from datetime import datetime, timedelta
import pytz  # <-- Додано
from utils.safe_sender import send_message_safely
from config import GROUP_ID, GROUP_INVITE_LINK
from handlers.nutrition_handler import send_daily_summary
import re
from aiogram.filters import Command
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

# Глобальний об'єкт scheduler для імпорту
scheduler = None

# Київська часова зона
KYIV_TZ = pytz.timezone("Europe/Kiev")

def get_current_kyiv_time():
    """Повертає поточний час за київською часовою зоною."""
    return datetime.now(KYIV_TZ)


# Словник для надійного перекладу днів тижня, незалежно від локалі системи
DAY_MAP = {
    "Monday": "Понеділок",
    "Tuesday": "Вівторок",
    "Wednesday": "Середа",
    "Thursday": "Четвер",
    "Friday": "П'ятниця",
    "Saturday": "Субота",
    "Sunday": "Неділя",
}

async def send_today_workout_for_user(user_id: int, bot: Bot, is_reminder: bool = False):
    try:
        today_english = get_current_kyiv_time().strftime('%A')
        today_ukrainian = DAY_MAP.get(today_english)

        if not today_ukrainian:
            print(f"Помилка: не вдалося визначити український день для {today_english}")
            if not is_reminder:
                await send_message_safely(bot, user_id, "Виникла системна помилка, спробуйте пізніше.")
            return

        plan = await db.get_user_plan(user_id)
        if not plan:
            if not is_reminder:
                await send_message_safely(bot, user_id, "У вас ще немає активного плану тренувань. Створіть його за допомогою команди /create_plan")
            return

        pattern = re.compile(rf"\*\*{today_ukrainian}.*?\*\*([\s\S]*?)(?=\n\*\*|\Z)", re.IGNORECASE)
        match = pattern.search(plan)

        if match:
            workout_for_today = match.group(0).strip()
            if "відпочинок" in workout_for_today.lower():
                text = f"Сьогодні у вас за планом **день відпочинку** 🧘. Насолоджуйтесь!"
                await send_message_safely(bot, user_id, f"Привіт! {text.lower()}" if not is_reminder else text)
            else:
                text = (
                    f"Привіт! Нагадую про ваше сьогоднішнє тренування. Ваш шлях до мети продовжується! 💪\n\n"
                    if is_reminder else
                    f"Ось ваше тренування на сьогодні. Вперед до мети! 💪\n\n"
                ) + workout_for_today
                await send_message_safely(bot, user_id, text, reply_markup=kb.confirm_workout_kb)
        else:
            if not is_reminder:
                await send_message_safely(bot, user_id, "Схоже, у вашому плані немає тренування на сьогодні.")
    except Exception as e:
        print(f"Не вдалося надіслати тренування на сьогодні користувачу {user_id}: {e}")
        if not is_reminder:
            await send_message_safely(bot, user_id, "Виникла помилка при спробі отримати ваше тренування.")

async def send_daily_reminder(bot: Bot):
    users = await db.get_all_active_users()
    for user_id, *_ in users:
        await send_today_workout_for_user(user_id, bot, is_reminder=True)

async def ask_for_weekly_feedback(bot: Bot):
    users = await db.get_all_active_users()
    feedback_text = "🗓️ **Час для тижневого відгуку!**\n\nЯк ви оцінюєте складність тренувань минулого тижня? (де 1 - дуже легко, 5 - дуже важко)"
    for user_id, *_ in users:
        try:
            await send_message_safely(bot, user_id, feedback_text, reply_markup=kb.feedback_kb)
        except Exception as e:
            print(f"Не вдалося надіслати тижневий відгук користувачу {user_id}: {e}")

async def send_monthly_report(bot: Bot):
    users = await db.get_all_active_users()
    for user_data in users:
        try:
            user_id = user_data[0]
            reg_date_str = user_data[1] if len(user_data) > 1 else None

            if not reg_date_str: continue
            reg_date = datetime.fromisoformat(reg_date_str)
            if datetime.now() - reg_date > timedelta(days=30):
                await achievements.check_and_grant_achievement(user_id, 'marathoner', bot)
            
            total_workouts = await db.count_total_workouts(user_id)
            last_30_days = await db.count_workouts_last_n_days(user_id, 30)
            report_text = (f"📅 **Ваш звіт за місяць!**\n\nВи чудово попрацювали! Ось ваша статистика:\n🔸 Тренувань за останній місяць: **{last_30_days}**\n🔸 Всього тренувань з ботом: **{total_workouts}**\n\nНовий місяць - нові вершини! Не зупиняйтесь!")
            await send_message_safely(bot, user_id, report_text)
        except Exception as e:
            print(f"Не вдалося надіслати місячний звіт користувачу! {user_id}: {e}")

async def post_weekly_leaderboard(bot: Bot):
    if not GROUP_ID: return
    top_users = await db.get_top_users_by_workouts(limit=3)
    if not top_users: return
    leaderboard_text = "🏆 **Щотижневий Лідерборд!** 🏆\n\nОсь наші найактивніші спортсмени за минулий тиждень:\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, username, workout_count) in enumerate(top_users):
        display_name = f"@{username}" if username else f"User {user_id}"
        leaderboard_text += f"{medals[i]} {display_name} - **{workout_count}** тренувань\n"
    leaderboard_text += "\nВітаємо лідерів та бажаємо всім продуктивного нового тижня!"
    await send_message_safely(bot, int(GROUP_ID), leaderboard_text)

async def remind_to_join_group(bot: Bot):
    if not GROUP_INVITE_LINK: return
    users_not_in_group = await db.get_users_not_in_group()
    if not users_not_in_group: return

    group_invite_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Приєднатись до спільноти", url=GROUP_INVITE_LINK)]
    ])
    reminder_text = "👋 Привіт! Нагадуємо, що у нас є закрита спільнота, де ви можете ділитися успіхами, брати участь у групових челенджах та отримувати додаткову мотивацію. Долучайтеся!"
    for (user_id,) in users_not_in_group:
        try:
            await send_message_safely(bot, user_id, reminder_text, reply_markup=group_invite_kb)
        except Exception as e:
            print(f"Не вдалося надіслати нагадування про групу користувачу {user_id}: {e}")


async def send_bedtime_reminder(bot: Bot):
    users = await db.get_all_active_users()
    text = "🌙 Пора лягати спати! Гарного відпочинку 😴"
    for user_id, *_ in users:
        try:
            await send_message_safely(bot, user_id, text)
        except Exception as e:
            print(f"Не вдалося надіслати нагадування про сон користувачу {user_id}: {e}")

async def ask_daily_activity(bot: Bot):
    users = await db.get_all_active_users()
    builder = InlineKeyboardBuilder()
    builder.button(text="Пасивний 🧘", callback_data="set_activity:passive")
    builder.button(text="Середній 🚶‍♂️", callback_data="set_activity:medium")
    builder.button(text="Активний 🏋️", callback_data="set_activity:active")
    builder.adjust(3)
    
    for user_id, *_ in users:
        await send_message_safely(bot, user_id, "Доброго ранку! Який у вас сьогодні план на активність?", reply_markup=builder.as_markup())

async def send_evening_summary(bot: Bot):
    users = await db.get_all_active_users()
    for user_id, *_ in users:
        try:
            print(f"[LOG] Відправляю вечірній звіт користувачу {user_id}")
            try:
                await send_daily_summary(user_id, bot)
                print(f"[LOG] Звіт успішно надіслано користувачу {user_id}")
            except Exception as e:
                print(f"[ERROR] send_daily_summary не вдалося для {user_id}: {e}")
        except Exception as e:
            print(f"[ERROR] Не вдалося надіслати вечірній звіт користувачу {user_id}: {e}")

async def send_meal_reminders(bot: Bot):
    """Нагадування про прийоми їжі для користувачів."""
    current_time = get_current_kyiv_time().strftime("%H:%M")
    user_reminders = await db.get_all_user_reminders()

    for user_id, breakfast, lunch, dinner in user_reminders:
        reminder_to_send = None
        if breakfast == current_time:
            reminder_to_send = ("сніданку 🍳", "breakfast")
        elif lunch == current_time:
            reminder_to_send = ("обіду 🍲", "lunch")
        elif dinner == current_time:
            reminder_to_send = ("вечері 🥗", "dinner")

        if reminder_to_send:
            text = f"Час для {reminder_to_send[0]}! Не забудьте записати свій прийом їжі."
            kb_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Записати їжу", callback_data=f"log_meal:{reminder_to_send[1]}")]
            ])
            try:
                await send_message_safely(bot, user_id, text, reply_markup=kb_markup)
            except Exception as e:
                print(f"Не вдалося надіслати нагадування про їжу {user_id}: {e}")

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ)

    scheduler.add_job(send_daily_reminder, 'cron', hour=7, minute=30, args=(bot,))
    scheduler.add_job(ask_for_weekly_feedback, 'cron', day_of_week='sun', hour=19, minute=0, args=(bot,))
    scheduler.add_job(send_monthly_report, 'cron', day=1, hour=10, minute=0, args=(bot,))
    scheduler.add_job(post_weekly_leaderboard, 'cron', day_of_week='sun', hour=20, minute=0, args=(bot,))
    scheduler.add_job(remind_to_join_group, 'cron', day_of_week='tue,fri', hour=12, minute=0, args=(bot,))
    scheduler.add_job(send_evening_summary, 'cron', hour=21, minute=30, args=(bot,))
    scheduler.add_job(send_meal_reminders, 'cron', minute='*', args=(bot,))
    scheduler.add_job(send_bedtime_reminder, 'cron', hour=22, minute=0, args=(bot,))

    if not scheduler.running:
        scheduler.start()

    return scheduler

router = Router()

# Кнопка для перегляду звіту калорій
calories_report_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Мій звіт за сьогодні", callback_data="show_calories_report")]
])

# Команда для перегляду звіту калорій
@router.message(Command("calories"), F.chat.type == "private")
async def show_calories_report(message: Message):
    calories_data = await db.get_today_calories(message.from_user.id)
    if not calories_data:
        await message.answer("Сьогодні ви ще не додавали інформацію про їжу або тренування.")
        return

    food_list = calories_data.get("food", [])
    total_calories = calories_data.get("total", 0)
    recommended = 2200

    food_text = "\n".join([f"- {item['name']}: {item['calories']} ккал" for item in food_list])
    report = (
        f"Ваш раціон за сьогодні:\n\n"
        f"{food_text}\n\n"
        f"---\n"
        f"🔥 Всього спожито: {total_calories} ккал\n"
        f"Рекомендована норма: ~{recommended} ккал"
    )
    await message.answer(report)

# Обробник для кнопки
@router.callback_query(F.data == "show_calories_report")
async def show_calories_report_callback(callback: CallbackQuery):
    calories_data = await db.get_today_calories(callback.from_user.id)
    if not calories_data:
        await callback.message.answer("Сьогодні ви ще не додавали інформацію про їжу або тренування.")
        await callback.answer()
        return

    food_list = calories_data.get("food", [])
    total_calories = calories_data.get("total", 0)
    recommended = 2200

    food_text = "\n".join([f"- {item['name']}: {item['calories']} ккал" for item in food_list])
    report = (
        f"Ваш раціон за сьогодні:\n\n"
        f"{food_text}\n\n"
        f"---\n"
        f"🔥 Всього спожито: {total_calories} ккал\n"
        f"Рекомендована норма: ~{recommended} ккал"
    )
    await callback.message.answer(report)
    await callback.answer()

