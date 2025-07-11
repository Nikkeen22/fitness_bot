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

# Київська часова зона
KYIV_TZ = pytz.timezone("Europe/Kiev")

def get_current_kyiv_time():
    """Повертає поточний час за київською часовою зоною."""
    return datetime.now(KYIV_TZ)

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

# Усі інші функції залишаються незмінними, окрім тих, де є datetime.now()

async def send_meal_reminders(bot: Bot):
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

async def send_monthly_report(bot: Bot):
    users = await db.get_all_active_users()
    for user_data in users:
        try:
            user_id = user_data[0]
            reg_date_str = user_data[1] if len(user_data) > 1 else None
            if not reg_date_str:
                continue
            reg_date = datetime.fromisoformat(reg_date_str)
            if get_current_kyiv_time() - reg_date > timedelta(days=30):
                await achievements.check_and_grant_achievement(user_id, 'marathoner', bot)
            total_workouts = await db.count_total_workouts(user_id)
            last_30_days = await db.count_workouts_last_n_days(user_id, 30)
            report_text = (
                f"📅 **Ваш звіт за місяць!**\n\nВи чудово попрацювали! Ось ваша статистика:\n"
                f"🔸 Тренувань за останній місяць: **{last_30_days}**\n"
                f"🔸 Всього тренувань з ботом: **{total_workouts}**\n\n"
                f"Новий місяць — нові вершини! Не зупиняйтесь!"
            )
            await send_message_safely(bot, user_id, report_text)
        except Exception as e:
            print(f"Не вдалося надіслати місячний звіт користувачу {user_id}: {e}")

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone=KYIV_TZ)

    scheduler.add_job(send_daily_reminder, 'cron', hour=23, minute=40, args=(bot,))
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
