import aiosqlite
import json
import os
from datetime import datetime, timedelta
import pytz

# --- Налаштування ---
DB_NAME = 'fitness_bot.db'
KYIV_TZ = pytz.timezone("Europe/Kiev")

# --- Ініціалізація та структура БД ---

async def init_db():
    """Створює всі необхідні таблиці та виконує міграції, якщо потрібно."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                registration_date TEXT,
                onboarding_data TEXT,
                fitness_plan TEXT,
                plan_start_date TEXT,
                subscription_status TEXT DEFAULT 'none',
                subscription_expiry_date TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                in_group BOOLEAN DEFAULT FALSE,
                reminder_breakfast TEXT DEFAULT '09:00',
                reminder_lunch TEXT DEFAULT '14:00',
                reminder_dinner TEXT DEFAULT '19:00',
                daily_activity_level TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS food_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                meal_description TEXT,
                calories INTEGER,
                proteins REAL,
                fats REAL,
                carbs REAL,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement_id TEXT,
                date_achieved TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                UNIQUE(user_id, achievement_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_payments (
                user_id INTEGER PRIMARY KEY,
                payment_code TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS public_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER,
                title TEXT,
                description TEXT,
                duration_days INTEGER,
                created_at TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS challenge_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_id INTEGER,
                user_id INTEGER,
                progress_days INTEGER DEFAULT 0,
                last_completion_date TEXT,
                FOREIGN KEY (challenge_id) REFERENCES public_challenges (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                UNIQUE(challenge_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiator_id INTEGER,
                opponent_id INTEGER,
                description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                initiator_completed BOOLEAN DEFAULT FALSE,
                opponent_completed BOOLEAN DEFAULT FALSE,
                winner_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                photo_file_id TEXT NOT NULL,
                date_added TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )''')
        
        # --- Проста міграція для таблиці duels ---
        cursor = await db.execute("PRAGMA table_info(duels)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if 'initiator_completed' not in columns:
            print("Виконую міграцію: додаю колонку 'initiator_completed' до таблиці 'duels'.")
            await db.execute("ALTER TABLE duels ADD COLUMN initiator_completed BOOLEAN DEFAULT FALSE")
        
        if 'opponent_completed' not in columns:
            print("Виконую міграцію: додаю колонку 'opponent_completed' до таблиці 'duels'.")
            await db.execute("ALTER TABLE duels ADD COLUMN opponent_completed BOOLEAN DEFAULT FALSE")
        
        await db.commit()

# --- Робота з користувачами ---

async def add_user(user_id: int, username: str, full_name: str):
    """Додає нового користувача або оновлює дані існуючого."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if await cursor.fetchone() is None:
            now = datetime.now(KYIV_TZ)
            trial_expiry = (now + timedelta(days=7)).isoformat()
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, registration_date, subscription_status, subscription_expiry_date) VALUES (?, ?, ?, ?, 'trial', ?)",
                (user_id, username, full_name, now.isoformat(), trial_expiry)
            )
        else:
            await db.execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (username, full_name, user_id)
            )
        await db.commit()

async def get_user_by_username(username: str):
    """Знаходить користувача за його username."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        return await cursor.fetchone()

async def get_all_active_users():
    """Повертає список всіх активних користувачів."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id, registration_date, plan_start_date FROM users WHERE is_active = TRUE")
        return await cursor.fetchall()

async def get_users_not_in_group():
    """Повертає користувачів, які ще не в групі."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id FROM users WHERE in_group = FALSE")
        return await cursor.fetchall()

async def set_user_in_group(user_id: int):
    """Відмічає, що користувач приєднався до групи."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("UPDATE users SET in_group = TRUE WHERE user_id = ?", (user_id,))
        await db.commit()

async def is_admin(user_id: int) -> bool:
    """Перевіряє, чи є користувач адміністратором."""
    admin_id = os.getenv("ADMIN_ID")
    if admin_id is None:
        try:
            from config import ADMIN_ID as config_admin_id
            admin_id = str(config_admin_id)
        except (ImportError, AttributeError):
            return False
    return str(user_id) == str(admin_id)

# --- Робота з підписками та платежами ---

async def get_user_subscription_status(user_id: int):
    """Перевіряє статус підписки користувача та оновлює, якщо вона закінчилась."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT subscription_status, subscription_expiry_date FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return 'none', None
        
        status, expiry_str = row['subscription_status'], row['subscription_expiry_date']
        if not expiry_str:
            return status, None

        expiry = datetime.fromisoformat(expiry_str)
        if status in ['trial', 'active'] and datetime.now(KYIV_TZ) > expiry:
            await db.execute("UPDATE users SET subscription_status = 'expired' WHERE user_id = ?", (user_id,))
            await db.commit()
            return 'expired', expiry
        return status, expiry

async def update_user_subscription(user_id: int, months: int):
    """Оновлює або продовжує підписку користувача."""
    status, expiry = await get_user_subscription_status(user_id)
    start = datetime.now(KYIV_TZ)
    if status == 'active' and expiry and expiry > start:
        start = expiry
    
    new_expiry = (start + timedelta(days=30 * months)).isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("UPDATE users SET subscription_status = 'active', subscription_expiry_date = ? WHERE user_id = ?", (new_expiry, user_id))
        await db.commit()

async def grant_lifetime_access(user_id: int):
    """Надає довічний доступ користувачу."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        far_future_date = (datetime.now() + timedelta(days=365 * 100)).isoformat()
        await db.execute("INSERT OR IGNORE INTO users (user_id, registration_date) VALUES (?, ?)", (user_id, datetime.now(KYIV_TZ).isoformat()))
        await db.execute("UPDATE users SET subscription_status = 'active', subscription_expiry_date = ? WHERE user_id = ?", (far_future_date, user_id))
        await db.commit()

async def add_pending_payment(user_id: int, payment_code: str):
    """Зберігає код для очікуючого платежу."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("INSERT OR REPLACE INTO pending_payments (user_id, payment_code, created_at) VALUES (?, ?, ?)", (user_id, payment_code, datetime.now(KYIV_TZ).isoformat()))
        await db.commit()

async def get_pending_payment_code(user_id: int) -> str | None:
    """Отримує код очікуючого платежу."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT payment_code FROM pending_payments WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row['payment_code'] if row else None

async def delete_pending_payment(user_id: int):
    """Видаляє очікуючий платіж."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM pending_payments WHERE user_id = ?", (user_id,))
        await db.commit()

# --- Робота з челенджами ---

async def create_public_challenge(author_id: int, title: str, description: str, duration: int) -> int:
    """Створює новий публічний челендж і повертає його ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cursor = await db.execute(
            "INSERT INTO public_challenges (author_id, title, description, duration_days, created_at) VALUES (?, ?, ?, ?, ?)",
            (author_id, title, description, duration, datetime.now(KYIV_TZ).isoformat())
        )
        await db.commit()
        return cursor.lastrowid

async def get_public_challenges():
    """Повертає список активних публічних челенджів."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, title FROM public_challenges WHERE is_active = TRUE ORDER BY id DESC")
        return await cursor.fetchall()

async def get_public_challenge_details(challenge_id: int):
    """Повертає детальну інформацію про челендж."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM public_challenges WHERE id = ?", (challenge_id,))
        return await cursor.fetchone()

async def join_public_challenge(user_id: int, challenge_id: int):
    """Додає користувача до учасників челенджу."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("INSERT OR IGNORE INTO challenge_participants (challenge_id, user_id) VALUES (?, ?)", (challenge_id, user_id))
        await db.commit()

async def get_user_challenge_progress(user_id: int, challenge_id: int):
    """Отримує прогрес користувача в конкретному челенджі."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT progress_days, last_completion_date FROM challenge_participants WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
        return await cursor.fetchone()

async def update_challenge_progress(user_id: int, challenge_id: int):
    """Оновлює прогрес користувача в челенджі, збільшуючи лічильник на 1."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            "UPDATE challenge_participants SET progress_days = progress_days + 1, last_completion_date = ? WHERE user_id = ? AND challenge_id = ?",
            (datetime.now(KYIV_TZ).isoformat(), user_id, challenge_id)
        )
        await db.commit()

async def delete_challenge(challenge_id: int):
    """
    Видаляє челендж та всіх його учасників.
    Спочатку видаляє учасників, потім сам челендж для надійності.
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM challenge_participants WHERE challenge_id = ?", (challenge_id,))
        await db.execute("DELETE FROM public_challenges WHERE id = ?", (challenge_id,))
        await db.commit()
        print(f"Challenge {challenge_id} and its participants have been deleted from the database.")


# --- Робота з дуелями ---

async def create_duel(initiator_id: int, opponent_id: int, description: str) -> int:
    """Створює нову дуель."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cursor = await db.execute(
            "INSERT INTO duels (initiator_id, opponent_id, description, created_at) VALUES (?, ?, ?, ?)",
            (initiator_id, opponent_id, description, datetime.now(KYIV_TZ).isoformat())
        )
        await db.commit()
        return cursor.lastrowid

async def get_duel_by_id(duel_id: int):
    """Отримує інформацію про дуель за її ID."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM duels WHERE id = ?", (duel_id,))
        return await cursor.fetchone()

async def update_duel_status(duel_id: int, status: str):
    """Оновлює статус дуелі (pending, active, completed, rejected)."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("UPDATE duels SET status = ? WHERE id = ?", (status, duel_id))
        await db.commit()

async def mark_duel_completed(user_id: int, duel_id: int):
    """Відмічає, що один з учасників виконав своє завдання в дуелі."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT initiator_id, opponent_id FROM duels WHERE id = ?", (duel_id,))
        duel = await cursor.fetchone()
        if not duel:
            return
        if user_id == duel['initiator_id']:
            await db.execute("UPDATE duels SET initiator_completed = TRUE WHERE id = ?", (duel_id,))
        elif user_id == duel['opponent_id']:
            await db.execute("UPDATE duels SET opponent_completed = TRUE WHERE id = ?", (duel_id,))
        await db.commit()

# --- Інші функції (плани, досягнення, їжа, тощо) ---

async def save_onboarding_data(user_id: int, data: dict):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("UPDATE users SET onboarding_data = ? WHERE user_id = ?", (json.dumps(data), user_id))
        await db.commit()

async def get_user_onboarding_data(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT onboarding_data FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return json.loads(row['onboarding_data']) if row and row['onboarding_data'] else None

async def save_fitness_plan(user_id: int, plan: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            "UPDATE users SET fitness_plan = ?, plan_start_date = ? WHERE user_id = ?",
            (plan, datetime.now(KYIV_TZ).isoformat(), user_id)
        )
        await db.commit()

async def get_user_plan(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT fitness_plan FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row['fitness_plan'] if row else None

async def log_workout_completion(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("INSERT INTO progress (user_id, date) VALUES (?, ?)", (user_id, datetime.now(KYIV_TZ).isoformat()))
        await db.commit()

async def has_completed_workout_today(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        today_start = datetime.now(KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await db.execute(
            "SELECT 1 FROM progress WHERE user_id = ? AND date >= ? LIMIT 1",
            (user_id, today_start)
        )
        return await cursor.fetchone() is not None

async def grant_achievement(user_id: int, achievement_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("INSERT OR IGNORE INTO achievements (user_id, achievement_id, date_achieved) VALUES (?, ?, ?)", (user_id, achievement_id, datetime.now(KYIV_TZ).isoformat()))
        await db.commit()

async def has_achievement(user_id: int, achievement_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT 1 FROM achievements WHERE user_id = ? AND achievement_id = ?", (user_id, achievement_id))
        return await cursor.fetchone() is not None

async def get_user_achievements(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT achievement_id FROM achievements WHERE user_id = ?", (user_id,))
        return await cursor.fetchall()

async def log_meal(user_id: int, description: str, calories: int, proteins: float, fats: float, carbs: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            "INSERT INTO food_log (user_id, meal_description, calories, proteins, fats, carbs, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, description, calories, proteins, fats, carbs, datetime.now(KYIV_TZ).isoformat())
        )
        await db.commit()

async def get_daily_food_summary(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        today_start = datetime.now(KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await db.execute(
            "SELECT meal_description, calories, proteins, fats, carbs FROM food_log WHERE user_id = ? AND created_at >= ?",
            (user_id, today_start)
        )
        return await cursor.fetchall()

async def add_user_result(user_id: int, photo_file_id: str):
    """Додає фото результату користувача в базу даних."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            "INSERT INTO user_results (user_id, photo_file_id, date_added) VALUES (?, ?, ?)",
            (user_id, photo_file_id, datetime.now(KYIV_TZ).isoformat())
        )
        await db.commit()

async def get_user_results(user_id: int):
    """Отримує всі фото результатів для конкретного користувача."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT photo_file_id FROM user_results WHERE user_id = ? ORDER BY date_added ASC",
            (user_id,)
        )
        return await cursor.fetchall()

async def set_meal_reminders(user_id: int, breakfast: str, lunch: str, dinner: str):
    """Встановлює час для нагадувань про прийоми їжі."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            "UPDATE users SET reminder_breakfast = ?, reminder_lunch = ?, reminder_dinner = ? WHERE user_id = ?",
            (breakfast, lunch, dinner, user_id)
        )
        await db.commit()

async def get_all_user_reminders():
    """Отримує налаштування нагадувань для всіх активних користувачів."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id, reminder_breakfast, reminder_lunch, reminder_dinner FROM users WHERE is_active = TRUE")
        return await cursor.fetchall()

async def count_total_workouts(user_id: int) -> int:
    """Рахує загальну кількість тренувань користувача."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(id) FROM progress WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def count_workouts_last_n_days(user_id: int, days: int) -> int:
    """Рахує кількість тренувань за останні N днів."""
    async with aiosqlite.connect(DB_NAME) as db:
        date_limit = (datetime.now(KYIV_TZ) - timedelta(days=days)).isoformat()
        cursor = await db.execute("SELECT COUNT(id) FROM progress WHERE user_id = ? AND date >= ?", (user_id, date_limit))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_top_users_by_workouts(limit: int = 3):
    """Повертає топ користувачів за кількістю тренувань за останній тиждень."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        date_limit = (datetime.now(KYIV_TZ) - timedelta(days=7)).isoformat()
        query = """
            SELECT u.user_id, u.username, COUNT(p.id) as workout_count
            FROM users u JOIN progress p ON u.user_id = p.user_id
            WHERE p.date >= ? GROUP BY u.user_id ORDER BY workout_count DESC LIMIT ?
        """
        cursor = await db.execute(query, (date_limit, limit))
        return await cursor.fetchall()

async def set_daily_activity(user_id: int, activity_level: str):
    """Зберігає щоденний рівень активності користувача."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("UPDATE users SET daily_activity_level = ? WHERE user_id = ?", (activity_level, user_id))
        await db.commit()

async def get_daily_activity(user_id: int) -> str | None:
    """Отримує щоденний рівень активності користувача."""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT daily_activity_level FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row['daily_activity_level'] if row else None
