# test_gemini.py

import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY # Переконайтесь, що цей імпорт працює з вашої папки

# --- Сюди скопіюйте код ваших функцій з файлу gemini.py ---
# Потрібні як мінімум _call_gemini та adjust_fitness_plan

# Початок скопійованого коду
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def _call_gemini(prompt: str, error_message: str, is_json: bool = False) -> str:
    # ... (код вашої функції _call_gemini)
    try:
        generation_config = {"response_mime_type": "application/json"} if is_json else None
        response = await asyncio.wait_for(
            model.generate_content_async(prompt, generation_config=generation_config),
            timeout=90.0
        )
        return response.text if response.text else error_message
    except Exception as e:
        print(f"Помилка: {e}")
        return error_message

async def adjust_fitness_plan(user_data: dict, current_plan: str, rating: int, comment: str) -> str:
    """
    Адаптує фітнес-план користувача на основі відгуку.
    ПОВЕРТАЄ НОВИЙ ПОВНІСТЮ СФОРМОВАНИЙ ПЛАН.
    """
    goal = user_data.get('goal', 'не вказана')
    conditions = user_data.get('conditions', 'не вказані')

    prompt = f"""
    Ви - експертний фітнес-тренер. Ваше завдання - переглянути існуючий фітнес-план користувача, 
    врахувати його відгук і згенерувати **новий, повний і самодостатній план на наступний тиждень.**
    **ДАНІ ПРО КОРИСТУВАЧА:**
    - Головна ціль: {goal}
    - Умови для тренувань: {conditions}
    **ПОПЕРЕДНІЙ ПЛАН:**
    ---
    {current_plan}
    ---
    **ВІДГУК КОРИСТУВАЧА ПРО ПОПЕРЕДНІЙ ПЛАН:**
    - Оцінка: {rating} з 5
    - Коментар: "{comment}"
    **ВАШЕ ЗАВДАННЯ:**
    1.  Проаналізуй оцінку та коментар. Якщо оцінка < 4, зроби план трохи легшим. Якщо оцінка = 5, зроби його трохи складнішим (прогресивне навантаження). Якщо оцінка = 4, залиш складність такою ж, але можеш урізноманітнити вправи. Якщо є конкретні прохання в коментарі, врахуй їх.
    2.  Згенеруй **повністю новий текст плану на тиждень**. Не використовуй фрази типу "(як у попередньому плані)" або "(без змін)".
    3.  Кожен тренувальний день у новому плані має містити повний список вправ, підходів та повторень.
    4.  Почни відповідь з короткого резюме про те, які зміни було внесено. Наприклад: "Чудово, я почув ваш відгук! Я трохи збільшив навантаження на ноги, як ви й просили."
    5.  Форматуй відповідь у Markdown для гарного відображення в Telegram.
    """
    error_message = "На жаль, не вдалося адаптувати ваш план. Будь ласка, спробуйте пізніше."
    return await _call_gemini(prompt, error_message)

# Кінець скопійованого коду


async def run_test():
    """Головна функція для запуску тесту."""
    print("--- Запускаю тест функції adjust_fitness_plan ---")

    # --- Змінюйте ці дані для різних тестів ---
    
    # 1. Дані про користувача (можна взяти з вашої бази даних або вигадати)
    test_user_data = {
        'goal': 'Набрати м\'язи',
        'conditions': 'Вдома (є гантелі/турнік)'
    }

    # 2. Поточний план тренувань користувача
    test_current_plan = """
    **Понеділок:**
    - Віджимання: 3 підходи по 15 повторень
    - Присідання з гантелями: 3 підходи по 12 повторень
    - Планка: 3 підходи по 45 секунд
    **Вівторок:**
    - Відпочинок
    """
    
    # 3. Відгук, який ми хочемо протестувати
    test_rating = 5
    test_comment = "Все супер, але хочу додати більше вправ на спину, якщо можна."
    
    # --- Кінець даних для зміни ---

    print(f"\nТестуємо з оцінкою: {test_rating}/5 та коментарем: '{test_comment}'")
    
    # Викликаємо нашу функцію
    new_plan = await adjust_fitness_plan(
        user_data=test_user_data,
        current_plan=test_current_plan,
        rating=test_rating,
        comment=test_comment
    )

    print("\n--- РЕЗУЛЬТАТ ГЕНЕРАЦІЇ: ---\n")
    print(new_plan)
    print("\n--- Тест завершено ---")


if __name__ == "__main__":
    asyncio.run(run_test())