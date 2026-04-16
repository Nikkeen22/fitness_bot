🏋️‍♂️ Fitness Telegram Bot with Gemini AI

Професійний Telegram-бот для автоматизації фітнес-процесів, мотивації та розумних консультацій за допомогою штучного інтелекту.

🌟 Ключові можливості

🤖 AI Coaching: Інтеграція з Google Gemini AI для персоналізованих відповідей на питання про тренування та дієту.

🏆 Гейміфікація: Система досягнень (achievements.py) та щоденні челенджі (challenges.py) для підтримки азарту.

📅 Розумний розклад: Автоматичні нагадування про активність за допомогою APScheduler.

⚙️ Модульна архітектура: Чіткий розподіл на хендлери, мідлварі та утиліти, що полегшує підтримку та розширення коду.

📊 Облік прогресу: Відстеження статистики користувача в реальному часі.

🛠 Технологічний стек

Core: Python 3.10+

Framework: aiogram 3.x (Asynchronous OOP)

AI Engine: Google Generative AI (Gemini API)

Database: SQLite / SQLAlchemy

Automation: APScheduler

Deployment: Підтримка Docker та Heroku (наявність Procfile)

🚀 Швидкий запуск

Клонуйте проєкт:

git clone [https://github.com/Nikkeen22/fitness_bot.git](https://github.com/Nikkeen22/fitness_bot.git)
cd fitness_bot


Встановіть залежності:

pip install -r requirements.txt


Налаштуйте змінні оточення:
Створіть файл .env та додайте ваші ключі (не завантажуйте цей файл на GitHub!):

BOT_TOKEN=ваш_токен_від_botfather
GEMINI_API_KEY=ваш_ключ_від_google_ai


Запустіть бота:

python main.py


📂 Структура репозиторію

handlers/ — логіка взаємодії з користувачем.

middlewares/ — фільтрація та попередня обробка запитів.

utils/ — допоміжні скрипти та логіка Gemini AI.

database/ — схеми таблиць та робота з даними.

scheduler.py — логіка фонових завдань.

👨‍💻 Автор

Микола Тихоненко

Портфоліо: nikkeen-portfolio.vercel.app

GitHub: @Nikkeen22
