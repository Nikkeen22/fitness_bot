import aiosqlite
import json
from datetime import datetime, timedelta

DB_NAME = 'fitness_bot.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Оновлена таблиця users з додатковими полями
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

        # Існуючі таблиці
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
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Прогрес
        await db.execute('''
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Досягнення
        await db.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement_id TEXT,
                date_achieved TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, achievement_id)
            )
        ''')

        # Платежі
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_payments (
                user_id INTEGER PRIMARY KEY,
                payment_code TEXT,
                created_at TEXT
            )
        ''')

        # Публічні виклики
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

        # Учасники викликів
        await db.execute('''
            CREATE TABLE IF NOT EXISTS challenge_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_id INTEGER,
                user_id INTEGER,
                progress_days INTEGER DEFAULT 0,
                last_completion_date TEXT,
                FOREIGN KEY (challenge_id) REFERENCES public_challenges (id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(challenge_id, user_id)
            )
        ''')

        # Дуелі
        await db.execute('''
            CREATE TABLE IF NOT EXISTS duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiator_id INTEGER,
                opponent_id INTEGER,
                description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                winner_id INTEGER
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                photo_file_id TEXT NOT NULL,
                date_added TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
        
        await db.commit()

# Збереження плану тренувань з датою старту
async def save_fitness_plan(user_id: int, plan: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET fitness_plan = ?, plan_start_date = ? WHERE user_id = ?",
            (plan, datetime.now().isoformat(), user_id)
        )
        await db.commit()

# Додавання або оновлення користувача
async def add_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if await cursor.fetchone() is None:
            trial_expiry = (datetime.now() + timedelta(days=7)).isoformat()
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, registration_date, subscription_status, subscription_expiry_date) VALUES (?, ?, ?, ?, 'trial', ?)",
                (user_id, username, full_name, datetime.now().isoformat(), trial_expiry)
            )
            await db.commit()
            return True
        else:
            await db.execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (username, full_name, user_id)
            )
            await db.commit()
        return False

# Отримати статус підписки користувача
async def get_user_subscription_status(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT subscription_status, subscription_expiry_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return 'none', None
        status, expiry_str = row
        expiry = datetime.fromisoformat(expiry_str) if expiry_str else None
        if status in ['trial', 'active'] and expiry and datetime.now() > expiry:
            await db.execute(
                "UPDATE users SET subscription_status = 'expired' WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
            return 'expired', expiry
        return status, expiry

# Оновлення підписки
async def update_user_subscription(user_id: int, months: int):
    status, expiry = await get_user_subscription_status(user_id)
    start = datetime.now()
    if status == 'active' and expiry and expiry > start:
        start = expiry
    new_expiry = (start + timedelta(days=30*months)).isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET subscription_status = 'active', subscription_expiry_date = ? WHERE user_id = ?",
            (new_expiry, user_id)
        )
        await db.commit()

# Інші функції: grant_lifetime_access, save_onboarding_data, get_user_onboarding_data, get_user_plan, etc.
# Усі існуючі функції залишаються без змін за аналогією з попередніми реалізаціями.

async def grant_lifetime_access(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        far_future_date = (datetime.now() + timedelta(days=365 * 100)).isoformat()
        await db.execute("INSERT OR IGNORE INTO users (user_id, registration_date) VALUES (?, ?)", (user_id, datetime.now().isoformat()))
        await db.execute("UPDATE users SET subscription_status = 'active', subscription_expiry_date = ? WHERE user_id = ?", (far_future_date, user_id))
        await db.commit()
async def save_onboarding_data(user_id: int, data: dict):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET onboarding_data = ? WHERE user_id = ?", (json.dumps(data), user_id))
        await db.commit()
async def get_user_onboarding_data(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT onboarding_data FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return json.loads(row[0]) if row and row[0] else None

async def get_user_plan(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT fitness_plan FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None
async def get_all_active_users():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT user_id, registration_date, plan_start_date FROM users WHERE is_active = TRUE"
        )
        return await cursor.fetchall()

async def grant_achievement(user_id: int, achievement_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO achievements (user_id, achievement_id, date_achieved) VALUES (?, ?, ?)", (user_id, achievement_id, datetime.now().isoformat()))
        await db.commit()
async def has_achievement(user_id: int, achievement_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT 1 FROM achievements WHERE user_id = ? AND achievement_id = ?", (user_id, achievement_id))
        return await cursor.fetchone() is not None
async def get_user_achievements(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT achievement_id FROM achievements WHERE user_id = ?", (user_id,))
        return await cursor.fetchall()
async def log_workout_completion(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO progress (user_id, date) VALUES (?, ?)", (user_id, datetime.now().isoformat()))
        await db.commit()
async def count_total_workouts(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM progress WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0
async def count_workouts_last_n_days(user_id: int, days: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        date_limit = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = await db.execute("SELECT COUNT(*) FROM progress WHERE user_id = ? AND date >= ?", (user_id, date_limit))
        row = await cursor.fetchone()
        return row[0] if row else 0
async def add_pending_payment(user_id: int, payment_code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO pending_payments (user_id, payment_code, created_at) VALUES (?, ?, ?)", (user_id, payment_code, datetime.now().isoformat()))
        await db.commit()
async def get_pending_payment_code(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT payment_code FROM pending_payments WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None
async def delete_pending_payment(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM pending_payments WHERE user_id = ?", (user_id,))
        await db.commit()
async def create_public_challenge(author_id: int, title: str, description: str, duration: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO public_challenges (author_id, title, description, duration_days, created_at) VALUES (?, ?, ?, ?, ?)",
            (author_id, title, description, duration, datetime.now().isoformat())
        )
        await db.commit()

async def set_meal_reminders(user_id: int, breakfast: str, lunch: str, dinner: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET reminder_breakfast = ?, reminder_lunch = ?, reminder_dinner = ? WHERE user_id = ?",
            (breakfast, lunch, dinner, user_id)
        )
        await db.commit()

async def get_all_user_reminders():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, reminder_breakfast, reminder_lunch, reminder_dinner FROM users WHERE is_active = TRUE")
        return await cursor.fetchall()
async def set_daily_activity(user_id: int, activity_level: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET daily_activity_level = ? WHERE user_id = ?", (activity_level, user_id))
        await db.commit()
async def log_meal(user_id: int, description: str, calories: int, proteins: float, fats: float, carbs: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO food_log (user_id, meal_description, calories, proteins, fats, carbs, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, description, calories, proteins, fats, carbs, datetime.now().isoformat())
        )
        await db.commit()
async def get_daily_food_summary(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await db.execute(
            "SELECT meal_description, calories, proteins, fats, carbs FROM food_log WHERE user_id = ? AND created_at >= ?",
            (user_id, today_start)
        )
        return await cursor.fetchall()

        return cursor.lastrowid
async def get_top_users_by_workouts(limit: int = 3):
    async with aiosqlite.connect(DB_NAME) as db:
        date_limit = (datetime.now() - timedelta(days=7)).isoformat()
        query = """
            SELECT u.user_id, u.username, COUNT(p.id) as workout_count
            FROM users u JOIN progress p ON u.user_id = p.user_id
            WHERE p.date >= ? GROUP BY u.user_id ORDER BY workout_count DESC LIMIT ?
        """
        cursor = await db.execute(query, (date_limit, limit))
        return await cursor.fetchall()
async def get_user_by_username(username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        return await cursor.fetchone()
async def create_duel(initiator_id: int, opponent_id: int, description: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO duels (initiator_id, opponent_id, description, created_at) VALUES (?, ?, ?, ?)",
            (initiator_id, opponent_id, description, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid
async def get_duel_by_id(duel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM duels WHERE id = ?", (duel_id,))
        return await cursor.fetchone()
async def update_duel_status(duel_id: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE duels SET status = ? WHERE id = ?", (status, duel_id))
        await db.commit()
async def get_users_not_in_group():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE in_group = FALSE")
        return await cursor.fetchall()
async def set_user_in_group(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET in_group = TRUE WHERE user_id = ?", (user_id,))
        await db.commit()
async def get_public_challenges():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, title FROM public_challenges WHERE is_active = TRUE ORDER BY id DESC")
        return await cursor.fetchall()
async def get_public_challenge_details(challenge_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM public_challenges WHERE id = ?", (challenge_id,))
        return await cursor.fetchone()
async def join_public_challenge(user_id: int, challenge_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO challenge_participants (challenge_id, user_id) VALUES (?, ?)", (challenge_id, user_id))
        await db.commit()
async def get_user_challenge_progress(user_id: int, challenge_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT progress_days, last_completion_date FROM challenge_participants WHERE user_id = ? AND challenge_id = ?", (user_id, challenge_id))
        return await cursor.fetchone()

async def has_completed_workout_today(user_id: int) -> bool:
    """Перевіряє, чи виконав користувач тренування сьогодні."""
    async with aiosqlite.connect(DB_NAME) as db:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await db.execute(
            "SELECT 1 FROM progress WHERE user_id = ? AND date >= ?",
            (user_id, today_start)
        )
        return await cursor.fetchone() is not None


async def add_user_result(user_id: int, photo_file_id: str):
    """Додає фото результату користувача в базу даних."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO user_results (user_id, photo_file_id, date_added) VALUES (?, ?, ?)",
            (user_id, photo_file_id, datetime.now().isoformat())
        )
        await db.commit()

async def get_user_results(user_id: int):
    """Отримує всі фото результатів для конкретного користувача."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT photo_file_id FROM user_results WHERE user_id = ? ORDER BY date_added ASC",
            (user_id,)
        )
        return await cursor.fetchall()
    
async def check_workout_done_today(user_id: int) -> bool:
    """Перевіряє, чи користувач вже підтвердив тренування сьогодні."""
    async with aiosqlite.connect(DB_NAME) as db:
        today_str = datetime.now().strftime('%Y-%m-%d')
        # Припускаємо, що created_at - це TEXT у форматі ISO
        cursor = await db.execute(
            "SELECT 1 FROM progress WHERE user_id = ? AND date(created_at) = ?",
            (user_id, today_str)
        )
        return await cursor.fetchone() is not None
    
async def get_daily_activity(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT daily_activity_level FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None
