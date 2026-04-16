# 🏋️‍♂️ Fitness Telegram Bot with Gemini AI

Професійний Telegram-бот для автоматизації фітнес-процесів, мотивації та отримання розумних консультацій через ШІ.

---

### 🌟 Ключові можливості

* **🤖 AI Coaching:** Інтеграція з **Google Gemini AI** для персоналізованих відповідей на питання про тренування та дієту.
* **🏆 Гейміфікація:** Власна система досягнень (`achievements.py`) та щоденні челенджі (`challenges.py`) для підтримки мотивації.
* **📅 Розумний розклад:** Автоматичні нагадування про активність та звіти за допомогою `APScheduler`.
* **⚙️ Модульна архітектура:** Чіткий розподіл на хендлери, мідлварі та утиліти (Asynchronous OOP).
* **📊 Облік прогресу:** Збереження та відстеження статистики користувача через базу даних.

---

### 🛠 Технологічний стек

* **Core:** Python 3.10+
* **Framework:** [aiogram 3.x](https://docs.aiogram.dev/)
* **AI Engine:** Google Generative AI (Gemini API)
* **Database:** SQLite / SQLAlchemy
* **Automation:** APScheduler
* **Deployment:** Підтримка Docker та Heroku (наявність Procfile)

---

### 🚀 Швидкий запуск

1. **Клонуйте проєкт:**
   ```bash
   git clone [https://github.com/Nikkeen22/fitness_bot.git](https://github.com/Nikkeen22/fitness_bot.git)
   cd fitness_bot
Встановіть залежності:

Bash
pip install -r requirements.txt
Налаштуйте змінні оточення:
Створіть файл .env у кореневій папці проєкту:

Фрагмент коду
BOT_TOKEN=ваш_токен_від_botfather
GEMINI_API_KEY=ваш_ключ_від_google_ai
Запустіть бота:

Bash
python main.py
📂 Структура репозиторію
handlers/ — обробка команд та повідомлень користувача.

middlewares/ — проміжне ПЗ для обробки запитів.

utils/ — допоміжні скрипти та інтеграція з Gemini AI.

database/ — моделі даних та робота з БД.

scheduler.py — логіка фонових та запланованих завдань.

👨‍💻 Автор
Микола Тихоненко

Портфоліо: nikkeen-portfolio.vercel.app

GitHub: @Nikkeen22

Спеціалізація: Python / Django / Mobile Development
