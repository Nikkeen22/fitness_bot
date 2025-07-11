from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, PhotoSize, InputMediaPhoto
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import keyboards as kb
import gemini
import database as db
from utils.safe_sender import answer_message_safely, send_message_safely
from .common import cmd_help
from config import GROUP_ID
import re
from html import escape
from aiogram.utils.markdown import hlink
from .community_handler import list_challenges, create_challenge_start, create_duel_start_from_button

router = Router()

class ToolsStates(StatesGroup):
    ai_chat_active = State()
    # Стани для калькулятора
    calc_waiting_for_gender = State()
    calc_waiting_for_params = State()
    calc_waiting_for_activity = State()
    calc_waiting_for_goal = State()
    # Стани для налаштування нагадувань
    reminders_waiting_for_breakfast = State()
    reminders_waiting_for_lunch = State()
    reminders_waiting_for_dinner = State()

class ResultStates(StatesGroup):
    waiting_for_photo = State()

# --- Головне меню інструментів ---
@router.message(F.chat.type == "private", F.text == "⚙️ Інструменти")
async def show_tools_menu(message: Message):
    await message.answer("Оберіть інструмент:", reply_markup=kb.tools_menu_kb)

# --- FAQ ---
@router.callback_query(F.data == "tool_faq")
async def show_faq(callback: CallbackQuery):
    faq_text = (
        "**❓ Часті питання (FAQ)**\n\n"
        "**1. Як часто оновлюється мій план?**\n"
        "Ваш план тренувань автоматично коригується щотижня на основі вашого відгуку. Щонеділі бот запитає вас про складність навантажень.\n\n"
        "**2. Що робити, якщо я пропустив тренування?**\n"
        "Нічого страшного! Просто продовжуйте за планом з наступного тренувального дня. Головне - не пропускати тренування систематично.\n\n"
        "**3. Як працює система підписки?**\n"
        "Після реєстрації ви отримуєте 7 днів безкоштовного доступу. Після цього для використання функцій бота потрібна буде місячна підписка. Керувати нею можна через команду /subscribe.\n\n"
        "**4. Чи можна змінити ціль (схуднення/набір маси)?**\n"
        "Так! Просто напишіть команду /start, і ви зможете пройти налаштування заново з новою ціллю."
    )
    await answer_message_safely(callback.message, faq_text)
    await callback.answer()

# --- Новий обробник для кнопки "Команди" ---
@router.callback_query(F.data == "tool_help")
async def show_help_from_tool(callback: CallbackQuery):
    await cmd_help(callback.message)
    await callback.answer()

# --- Калькулятор калорій ---
@router.callback_query(F.data == "tool_calories")
async def start_calorie_calculator(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⚖️ **Калькулятор калорій**\n\nДавайте розрахуємо вашу денну норму. Вкажіть вашу стать (Чоловік/Жінка):")
    await state.set_state(ToolsStates.calc_waiting_for_gender)
    await callback.answer()

@router.message(ToolsStates.calc_waiting_for_gender, F.chat.type == "private")
async def calc_process_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Введіть вашу вагу (кг), зріст (см) та вік через кому. Наприклад: 75, 180, 28")
    await state.set_state(ToolsStates.calc_waiting_for_params)

@router.message(ToolsStates.calc_waiting_for_params, F.chat.type == "private")
async def calc_process_params(message: Message, state: FSMContext):
    try:
        weight, height, age = map(str.strip, message.text.split(','))
        await state.update_data(weight=int(weight), height=int(height), age=int(age))
        await message.answer("Який у вас рівень щоденної активності? (сидяча робота, помірна активність, висока активність)")
        await state.set_state(ToolsStates.calc_waiting_for_activity)
    except (ValueError, IndexError):
        await message.answer("Будь ласка, введіть дані у правильному форматі: вага, зріст, вік.")

@router.message(ToolsStates.calc_waiting_for_activity, F.chat.type == "private")
async def calc_process_activity(message: Message, state: FSMContext):
    await state.update_data(activity_level=message.text)
    await message.answer("Яка ваша головна ціль? (Схуднути, Набрати м'язи, Підтримати форму)")
    await state.set_state(ToolsStates.calc_waiting_for_goal)

@router.message(ToolsStates.calc_waiting_for_goal, F.chat.type == "private")
async def calc_process_goal_and_calculate(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    user_data = await state.get_data()
    await message.answer("⏳ Розраховую...")
    
    result = await gemini.calculate_calories(user_data)
    await answer_message_safely(message, result)
    await state.clear()
    await message.answer("Ви повернулись до головного меню.", reply_markup=kb.main_menu_kb)


@router.callback_query(F.data == "tool_reminders")
async def start_reminders_setup(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⏰ **Налаштування нагадувань**\n\nВкажіть бажаний час для сніданку (у форматі ГГ:ХХ, наприклад, 08:30):")
    await state.set_state(ToolsStates.reminders_waiting_for_breakfast)
    await callback.answer()

async def process_time_input(message: Message, state: FSMContext, next_state: State, prompt: str, field_name: str):
    time_pattern = re.compile(r"^\d{2}:\d{2}$")
    if not time_pattern.match(message.text):
        await message.answer("Неправильний формат. Будь ласка, введіть час у форматі ГГ:ХХ (наприклад, 09:00).")
        return
    await state.update_data({field_name: message.text})
    if next_state:
        await message.answer(prompt)
        await state.set_state(next_state)
    else: # This is the last step
        data = await state.get_data()
        await db.set_meal_reminders(
            user_id=message.from_user.id,
            breakfast=data['breakfast_time'],
            lunch=data['lunch_time'],
            dinner=data['dinner_time']
        )
        await message.answer(f"✅ Налаштування збережено!\nСніданок: {data['breakfast_time']}\nОбід: {data['lunch_time']}\nВечеря: {data['dinner_time']}", reply_markup=kb.main_menu_kb)
        await state.clear()


@router.message(ToolsStates.reminders_waiting_for_breakfast, F.chat.type == "private")
async def process_breakfast_time(message: Message, state: FSMContext):
    await process_time_input(message, state, ToolsStates.reminders_waiting_for_lunch, "Добре. Тепер вкажіть час для обіду:", "breakfast_time")

@router.message(ToolsStates.reminders_waiting_for_lunch, F.chat.type == "private")
async def process_lunch_time(message: Message, state: FSMContext):
    await process_time_input(message, state, ToolsStates.reminders_waiting_for_dinner, "І останнє, час для вечері:", "lunch_time")

@router.message(ToolsStates.reminders_waiting_for_dinner, F.chat.type == "private")
async def process_dinner_time(message: Message, state: FSMContext):
    await process_time_input(message, state, None, "", "dinner_time")


# --- Чат з AI-тренером ---
@router.message(F.chat.type == "private", F.text == "💬 Чат з AI-тренером")
async def start_ai_chat(message: Message, state: FSMContext):
    await state.set_state(ToolsStates.ai_chat_active)
    await state.update_data(history=[])
    await message.answer(
        "Ви увійшли в режим вільного чату з AI-тренером. 💬\n\n"
        "Ставте будь-яке питання про фітнес, харчування або тренування. Щоб завершити розмову, надішліть команду /stop_chat.",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(Command("stop_chat"), F.chat.type == "private")
async def stop_ai_chat(message: Message, state: FSMContext):
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("Режим чату завершено. Ви повернулись до головного меню.", reply_markup=kb.main_menu_kb)

@router.message(ToolsStates.ai_chat_active, F.chat.type == "private")
async def handle_ai_chat(message: Message, state: FSMContext, bot: Bot):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    data = await state.get_data()
    history = data.get('history', [])
    
    response_text = await gemini.get_ai_chat_response(history, message.text)
    
    history.append({"author": "user", "text": message.text})
    history.append({"author": "model", "text": response_text})
    await state.update_data(history=history[-4:]) # Keep last 4 turns
    
    await answer_message_safely(message, response_text)

# --- Обробка "Поділитися результатом" ---
@router.callback_query(F.data == "share_result")
async def handle_share_result(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Чудово! Надішліть фото вашого результату, яким ви хочете поділитися.")
    await state.set_state(ResultStates.waiting_for_photo)
    await callback.answer()

# --- NEW AND IMPROVED PHOTO HANDLER ---
@router.message(ResultStates.waiting_for_photo, F.photo)
async def process_result_photo(message: Message, state: FSMContext, bot: Bot):
    photo: PhotoSize = message.photo[-1]
    photo_file_id = photo.file_id

    # 1. Save to DB first
    await db.add_user_result(message.from_user.id, photo_file_id)
    await state.clear()
    await message.answer("✅ Дякую, ваш результат збережено! Намагаюся опублікувати в групі...")

    # 2. Try to publish to the group
    if GROUP_ID:
        try:
            # Prepare caption with a safe HTML link
            user_name = escape(message.from_user.full_name)
            user_link_html = hlink(user_name, f"tg://user?id={message.from_user.id}")
            caption_text = f"💪 Користувач {user_link_html} поділився своїм результатом!"

            # Send photo with caption in one message
            await bot.send_photo(
                chat_id=int(GROUP_ID),
                photo=photo_file_id,
                caption=caption_text,
                parse_mode="HTML"
            )
            
            # 3. Confirm successful publication to the user ONLY after it succeeds
            await message.answer("✅ Результат успішно опубліковано в групі!")

        except Exception as e:
            # 3. Inform user about the failure and log the detailed error
            await message.answer("❌ На жаль, не вдалося опублікувати ваш результат. Адміністратор вже сповіщений про проблему.")
            print(f"ПОМИЛКА: Не вдалося опублікувати результат в групу {GROUP_ID}. Причина: {e}")
    else:
        # Handle case where GROUP_ID is not configured
        print("INFO: Публікація в групу не налаштована (GROUP_ID не вказано).")

# --- Обробка "Мої результати" ---
@router.callback_query(F.data == "my_results")
async def handle_my_results(callback: CallbackQuery, bot: Bot):
    results = await db.get_user_results(callback.from_user.id)
    if not results:
        await callback.answer("Ви ще не ділилися жодними результатами.", show_alert=True)
        return

    await callback.message.answer("Ось ваші збережені результати:")
    
    # Send photos in chunks of 10 (Telegram API limit)
    media_group = [InputMediaPhoto(media=file_id) for file_id, in results]
    for i in range(0, len(media_group), 10):
        chunk = media_group[i:i + 10]
        if chunk:
            await bot.send_media_group(chat_id=callback.from_user.id, media=chunk)
    
    await callback.answer()

@router.callback_query(F.data == "tool_challenges")
async def handle_challenges_button(callback: CallbackQuery):
    await list_challenges(callback.message)
    await callback.answer()

@router.callback_query(F.data == "tool_create_challenge")
async def handle_create_challenge_button(callback: CallbackQuery, state: FSMContext):
    await create_challenge_start(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "tool_duel")
async def handle_duel_button(callback: CallbackQuery, state: FSMContext):
    await create_duel_start_from_button(callback.message, state)
    await callback.answer()