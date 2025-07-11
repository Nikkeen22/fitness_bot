from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandStart
import keyboards as kb
import gemini
import database as db
import achievements
from utils.safe_sender import answer_message_safely
from config import GROUP_INVITE_LINK
import locale
from datetime import datetime

router = Router()

try:
    locale.setlocale(locale.LC_TIME, 'uk_UA.UTF-8')
except locale.Error:
    print("Українська локаль не підтримується, дні тижня можуть бути англійською.")

class OnboardingStates(StatesGroup):
    waiting_for_goal = State()
    waiting_for_gender = State()
    waiting_for_params = State()
    waiting_for_body_type = State()
    waiting_for_activity = State()
    waiting_for_conditions = State()
    waiting_for_frequency = State()
    waiting_for_duration = State()
    waiting_for_food_prefs = State()

# --- Команди /start та /newplan переїхали сюди ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    is_new_user = await db.add_user(user.id, user.username, user.full_name)
    if is_new_user:
        await message.answer("Вітаємо в AI Fitness Coach! 🎉\n\nВам надано **безкоштовний 7-денний доступ** до всіх функцій. Давайте почнемо налаштування!")
    await start_onboarding(message, state)

@router.message(Command("newplan"))
async def cmd_newplan(message: Message, state: FSMContext):
    await message.answer("Давайте створимо новий план! Процес такий самий, як і на початку.")
    await start_onboarding(message, state)


async def start_onboarding(message: Message, state: FSMContext):
    await message.answer(
        "Привіт! Я ваш персональний AI Fitness Coach. Давайте налаштуємо вашу програму.\n\n"
        "Для початку, яка ваша головна ціль?",
        reply_markup=kb.goal_kb
    )
    await state.set_state(OnboardingStates.waiting_for_goal)
    
# ... (решта обробників онбордингу без змін)
@router.message(OnboardingStates.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.answer("Вкажіть вашу стать (Чоловік/Жінка).", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OnboardingStates.waiting_for_gender)
@router.message(OnboardingStates.waiting_for_gender)
async def process_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Чудово! Тепер введіть вашу вагу (кг), зріст (см) та вік через кому. Наприклад: 75, 180, 28")
    await state.set_state(OnboardingStates.waiting_for_params)
@router.message(OnboardingStates.waiting_for_params)
async def process_params(message: Message, state: FSMContext):
    try:
        weight, height, age = map(str.strip, message.text.split(','))
        await state.update_data(weight=int(weight), height=int(height), age=int(age))
        await message.answer("Дякую. Коротко опишіть свою статуру (наприклад: худорлявий, є невеликий живіт, спортивна).")
        await state.set_state(OnboardingStates.waiting_for_body_type)
    except ValueError:
        await message.answer("Будь ласка, введіть дані у правильному форматі.")
@router.message(OnboardingStates.waiting_for_body_type)
async def process_body_type(message: Message, state: FSMContext):
    await state.update_data(body_type=message.text)
    await message.answer("Який у вас рівень щоденної активності? (сидяча робота, помірна активність, висока активність)")
    await state.set_state(OnboardingStates.waiting_for_activity)
@router.message(OnboardingStates.waiting_for_activity)
async def process_activity(message: Message, state: FSMContext):
    await state.update_data(activity_level=message.text)
    await message.answer("Де ви плануєте тренуватись?", reply_markup=kb.conditions_kb)
    await state.set_state(OnboardingStates.waiting_for_conditions)
@router.message(OnboardingStates.waiting_for_conditions)
async def process_conditions(message: Message, state: FSMContext):
    await state.update_data(conditions=message.text)
    await message.answer("Скільки разів на тиждень ви готові тренуватися (2-6)?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OnboardingStates.waiting_for_frequency)
@router.message(OnboardingStates.waiting_for_frequency)
async def process_frequency(message: Message, state: FSMContext):
    await state.update_data(frequency=message.text)
    await message.answer("Скільки хвилин ви готові приділяти одному тренуванню (30-90)?")
    await state.set_state(OnboardingStates.waiting_for_duration)
@router.message(OnboardingStates.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    await state.update_data(duration=message.text)
    await message.answer("Останній крок: чи є у вас особливі харчові вподобання? (наприклад: вегетаріанець, алергія на горіхи). Якщо ні, напишіть 'немає'.")
    await state.set_state(OnboardingStates.waiting_for_food_prefs)

@router.message(OnboardingStates.waiting_for_food_prefs)
async def process_food_prefs_and_generate(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(food_prefs=message.text)
    user_data = await state.get_data()
    user_id = message.from_user.id
    
    await db.save_onboarding_data(user_id, user_data)
    
    await bot.send_chat_action(chat_id=user_id, action="typing")
    await message.answer("Супер! Всі дані зібрано. Готую вашу персональну програму...", reply_markup=ReplyKeyboardRemove())
    
    today_weekday = datetime.now().strftime('%A').capitalize()
    full_plan, today_workout = await gemini.generate_plan(user_data, today_weekday)
    
    await db.save_fitness_plan(user_id, full_plan)
    
    await answer_message_safely(message, full_plan)
    
    if "На жаль, виникла помилка" not in full_plan and "Вибачте, генерація" not in full_plan:
        await message.answer("Ваш план збережено! Ви можете переглянути його в будь-який час.", reply_markup=kb.main_menu_kb)
        await achievements.check_and_grant_achievement(user_id, 'novice', bot)

        await answer_message_safely(message, f"**Ось ваше тренування на сьогодні ({today_weekday}):**\n\n{today_workout}", reply_markup=kb.confirm_workout_kb)

        if GROUP_INVITE_LINK:
            group_invite_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Приєднатись до спільноти", url=GROUP_INVITE_LINK)]])
            await message.answer("� А тепер долучайтеся до нашої спільноти, щоб ділитися результатами та брати участь у челенджах!", reply_markup=group_invite_kb)

    await state.clear()

