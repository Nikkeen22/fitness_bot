import asyncio
import json
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def _call_gemini(prompt: str, error_message: str, is_json: bool = False) -> str:
    """
    Універсальна функція для виклику Gemini API з підтримкою JSON-режиму.
    """
    try:
        generation_config = {"response_mime_type": "application/json"} if is_json else None

        response = await asyncio.wait_for(
            model.generate_content_async(
                prompt,
                generation_config=generation_config
            ),
            timeout=60.0
        )

        if response.text:
            return response.text
        else:
            print("Помилка: Gemini повернув пусту відповідь.")
            return json.dumps({"error": error_message}) if is_json else error_message

    except asyncio.TimeoutError:
        print("Помилка: Час очікування відповіді від Gemini API вичерпано.")
        error_text = "Вибачте, генерація займає занадто багато часу. Спробуйте, будь ласка, трохи пізніше."
        return json.dumps({"error": error_text}) if is_json else error_text

    except Exception as e:
        print(f"Помилка генерації в Gemini: {e}")
        return json.dumps({"error": error_message}) if is_json else error_message

async def generate_plan(user_data: dict, today_weekday: str) -> tuple[str, str]:
    prompt = f"""
    Ви - експертний фітнес-тренер та дієтолог. Створи персоналізований фітнес-план для користувача з наступними даними.
    Відповідь має бути чітко структурована у форматі Markdown для Telegram.

    **Вхідні дані користувача:**
    - **Головна ціль:** {user_data.get('goal')}
    - **Стать:** {user_data.get('gender')}
    - **Вага:** {user_data.get('weight')} кг
    - **Зріст:** {user_data.get('height')} см
    - **Вік:** {user_data.get('age')} років
    - **Опис статури:** {user_data.get('body_type')}
    - **Рівень активності:** {user_data.get('activity_level')}
    - **Умови для тренувань:** {user_data.get('conditions')}
    - **Частота тренувань:** {user_data.get('frequency')} разів на тиждень
    - **Тривалість тренування:** {user_data.get('duration')} хвилин
    - **Харчові вподобання/обмеження:** {user_data.get('food_prefs')}

    **Ваше завдання - згенерувати:**

    **1. МОТИВАЦІЙНЕ ПРИВІТАННЯ:**
    Коротке, надихаюче повідомлення для початку, звертаючись до користувача.

    **2. ПЛАН ХАРЧУВАННЯ:**
    - Розрахуйте денну норму КБЖВ.
    - Надайте меню на 3 дні (сніданок, обід, вечеря, перекуси), враховуючи КБЖВ та обмеження.

    **3. ПРОГРАМА ТРЕНУВАНЬ НА ТИЖДЕНЬ:**
    - Детальний план на {user_data.get('frequency')} днів + дні відпочинку.
    - Для кожного дня: 5-7 вправ, підходи, повторення.
    - Завершуйте кожен день рядком: `Орієнтовно спалених калорій: XXX ккал.`

    **4. ТРЕНУВАННЯ НА СЬОГОДНІ ({today_weekday}):**
    Почніть секцію з унікального маркера `---TODAY_WORKOUT---`. Якщо день відпочинку — вкажіть.
    """

    full_response = await _call_gemini(prompt, "На жаль, виникла помилка при створенні вашого плану.")
    
    if "---TODAY_WORKOUT---" in full_response:
        parts = full_response.split("---TODAY_WORKOUT---")
        return parts[0].strip(), parts[1].strip()
    else:
        return full_response, "Не вдалося визначити тренування на сьогодні."

async def analyze_meal(description: str) -> str:
    """
    Аналізує опис страви та повертає JSON з КБЖВ.
    """
    prompt = f"""
    Проаналізуй опис страви та поверни JSON об'єкт з такими полями:
    "meal_name", "calories", "proteins", "fats", "carbs".
    Опис страви: "{description}"
    """
    return await _call_gemini(prompt, "На жаль, не вдалося розпізнати страву.", is_json=True)

async def get_ai_chat_response(history: list, new_prompt: str) -> str:
    """
    Генерує відповідь у режимі чату на основі історії.
    """
    system_instruction = (
        "Ти - досвідчений фітнес-тренер та дієтолог на ім'я AI Fitness Coach. "
        "Відповідай чітко, експертно, підбадьорливо. Будь дружелюбним."
    )

    formatted_history = [
        {"role": "user" if turn['author'] == 'user' else "model", "parts": [{"text": turn['text']}]}
        for turn in history
    ]
    formatted_history.append({"role": "user", "parts": [{"text": new_prompt}]})

    chat_model = genai.GenerativeModel(
        'gemini-1.5-flash',
        system_instruction=system_instruction
    )

    try:
        response = await asyncio.wait_for(chat_model.generate_content_async(formatted_history), timeout=45.0)
        return response.text
    except Exception as e:
        print(f"Помилка в чаті з Gemini: {e}")
        return "Вибачте, сталася помилка. Спробуйте ще раз або використайте /stop_chat."

async def calculate_calories(user_data: dict) -> str:
    """
    Розраховує приблизну денну норму калорій та КБЖВ.
    """
    prompt = f"""
    Розрахуй добову потребу в калоріях, білках, жирах і вуглеводах для:
    - Стать: {user_data.get('gender')}
    - Вік: {user_data.get('age')}
    - Вага: {user_data.get('weight')}
    - Зріст: {user_data.get('height')}
    - Рівень активності: {user_data.get('activity_level')}
    - Ціль: {user_data.get('goal')}
    
    Вкажи значення у форматі:
    Калорії: XXXX ккал
    Білки: XX г
    Жири: XX г
    Вуглеводи: XX г
    """
    return await _call_gemini(prompt, "Не вдалося розрахувати калорії.")

async def get_daily_analysis(summary: dict) -> str:
    """
    Генерує щоденний аналіз харчування та активності.
    """
    prompt = f"""
    Зроби короткий аналіз на основі щоденного звіту:
    - Калорії спожито: {summary.get("calories_eaten")}
    - Калорії спалено: {summary.get("calories_burned")}
    - Ціль: {summary.get("goal")}
    - Прогрес: {summary.get("progress_notes")}

    Виведи рекомендації на завтра у 3-4 реченнях.
    """
    return await _call_gemini(prompt, "Не вдалося згенерувати аналіз.")


async def generate_fitness_tip() -> str:
    """
    Генерує коротку, випадкову фітнес-пораду.
    """
    prompt = "Дай одну коротку, корисну та несподівану пораду про фітнес або здоровий спосіб життя. Відповідь має бути одним-двома реченнями."
    
    # Використовуємо вже існуючу універсальну функцію _call_gemini
    error_message = "На жаль, не вдалося придумати для вас пораду."
    return await _call_gemini(prompt, error_message)

async def generate_recipe_from_products(products: str, user_data: dict) -> str:
    """
    Генерує здоровий та корисний рецепт на основі списку продуктів та даних користувача.
    """
    # Збираємо дані користувача, які можуть бути корисними для рецепта
    food_prefs = user_data.get('food_prefs', 'немає')
    goal = user_data.get('goal', 'здорове харчування')

    prompt = f"""
    Будь ласка, виступи в ролі шеф-кухаря та дієтолога.
    Створи один здоровий, смачний та простий рецепт, використовуючи наступні продукти: {products}.

    При створенні рецепта, будь ласка, врахуй наступні дані про користувача:
    - Харчові вподобання або обмеження: {food_prefs}
    - Головна ціль користувача: {goal}

    Твоя відповідь повинна містити:
    1.  **Назву страви** (креативну та апетитну).
    2.  **Короткий опис** (1-2 речення).
    3.  **Список інгредієнтів** (включаючи ті, що надав користувач, та, можливо, додаткові прості інгредієнти, як-от сіль, перець, олія).
    4.  **Покрокову інструкцію приготування.**
    5.  **Приблизний розрахунок КБЖВ** на порцію.

    Форматуй відповідь у Markdown для гарного відображення в Telegram.
    """
    
    error_message = "Вибачте, не вдалося придумати рецепт з цих продуктів. Спробуйте інший набір."
    return await _call_gemini(prompt, error_message)

async def adjust_fitness_plan(user_data: dict, current_plan: str, rating: int, comment: str) -> str:
    """
    Адаптує фітнес-план користувача на основі відгуку (рейтинг і коментар).
    Повертає оновлений план у форматі Markdown.
    """
    prompt = f"""
    Ви - експертний фітнес-тренер.
    Користувач надав фітнес-план:
    {current_plan}

    Користувач оцінив план на {rating} з 5 і додав коментар:
    {comment}

    Враховуючи оцінку та коментар, адаптуйте фітнес-план для кращого результату.
    Залишайте відповідь у форматі Markdown, коротко і чітко.
    """

    response = await _call_gemini(prompt, "Не вдалося адаптувати план.")
    return response
