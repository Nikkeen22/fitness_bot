from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
import gemini
import achievements
import keyboards as kb
from utils.safe_sender import answer_message_safely
from scheduler import send_today_workout_for_user


router = Router()

class UserActionStates(StatesGroup):
    waiting_for_products = State()
    waiting_for_feedback_comment = State()

@router.message(Command("progress"))
async def cmd_progress(message: Message):
    user_id = message.from_user.id
    total_workouts = await db.count_total_workouts(user_id)
    last_7_days = await db.count_workouts_last_n_days(user_id, 7)
    text = (
        f"📊 **Ваш прогрес:**\n\n"
        f"🔹 **Всього виконано тренувань:** {total_workouts}\n"
        f"🔹 **Тренувань за останні 7 днів:** {last_7_days}\n\n"
        f"Продовжуйте в тому ж дусі!"
    )
    await answer_message_safely(message, text)
@router.message(Command("tip"))
async def cmd_tip(message: Message):
    await message.answer("🧠 Генерую корисну пораду...")
    tip = await gemini.generate_fitness_tip()
    await answer_message_safely(message, tip)
@router.message(Command("food"))
async def cmd_food(message: Message, state: FSMContext):
    await message.answer("Введіть список продуктів, які у вас є, через кому (наприклад: курка, гречка, помідор, сир).")
    await state.set_state(UserActionStates.waiting_for_products)
@router.message(UserActionStates.waiting_for_products)
async def process_products(message: Message, state: FSMContext, bot: Bot):
    products = message.text
    user_id = message.from_user.id
    user_data = await db.get_user_onboarding_data(user_id)
    if not user_data:
        await message.answer("Не можу знайти ваші дані. Будь ласка, пройдіть налаштування через /start.")
        await state.clear()
        return
    await message.answer("🍳 Шукаю рецепти для вас...")
    recipe = await gemini.generate_recipe_from_products(products, user_data)
    await answer_message_safely(message, recipe)
    await achievements.check_and_grant_achievement(user_id, 'chef', bot)
    await state.clear()
@router.callback_query(F.data.startswith("feedback_rating:"))
async def process_feedback_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[1])
    await state.update_data(rating=rating)
    await callback.message.edit_text("Дякую за оцінку! Напишіть, будь ласка, короткий коментар або побажання, щоб я міг краще скоригувати план.")
    await state.set_state(UserActionStates.waiting_for_feedback_comment)
    await callback.answer()
@router.message(UserActionStates.waiting_for_feedback_comment)
async def process_feedback_comment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    feedback_data = await state.get_data()
    rating = feedback_data.get('rating')
    comment = message.text
    user_data = await db.get_user_onboarding_data(user_id)
    current_plan = await db.get_user_plan(user_id)
    if not user_data or not current_plan:
        await message.answer("Щось пішло не так, не можу знайти ваш план. Спробуйте /start.")
        await state.clear()
        return
    await message.answer("Аналізую ваш відгук та коригую план... Це може зайняти хвилину.")
    new_plan = await gemini.adjust_fitness_plan(user_data, current_plan, rating, comment)
    await db.save_fitness_plan(user_id, new_plan)
    await message.answer("✅ Ваш план оновлено! Ось нова версія:")
    await answer_message_safely(message, new_plan)
    await state.clear()

