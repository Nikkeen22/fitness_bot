from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
import keyboards as kb
from utils.safe_sender import answer_message_safely, send_message_safely
import gemini
import json

router = Router()

class NutritionStates(StatesGroup):
    waiting_for_meal_description = State()
    waiting_for_meal_confirmation = State()

# Обробка ручного додавання та з нагадувань
@router.message(F.chat.type == "private", F.text == "🥑 Додати їжу")
@router.message(Command("add_meal"), F.chat.type == "private")
@router.callback_query(F.data.startswith("log_meal:"))
async def start_meal_logging(event: Message | CallbackQuery, state: FSMContext):
    message = event if isinstance(event, Message) else event.message
    await answer_message_safely(message, "Чудово! Що саме ви з'їли? Опишіть страву якомога детальніше.")
    await state.set_state(NutritionStates.waiting_for_meal_description)
    if isinstance(event, CallbackQuery):
        await event.answer()

@router.message(NutritionStates.waiting_for_meal_description, F.chat.type == "private")
async def process_meal_description(message: Message, state: FSMContext, bot: Bot):
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    response_json_str = await gemini.analyze_meal(message.text)
    
    try:
        meal_data = json.loads(response_json_str)
        await state.update_data(meal_data=meal_data)
        
        confirmation_text = (
            f"Я розпізнав вашу страву як **'{meal_data['meal_name']}'**.\n\n"
            f"Орієнтовна калорійність: **{meal_data['calories']} ккал**\n"
            f"(Б: {meal_data.get('proteins', 0)}г, Ж: {meal_data.get('fats', 0)}г, В: {meal_data.get('carbs', 0)}г)\n\n"
            f"Записати цей прийом їжі?"
        )
        await answer_message_safely(message, confirmation_text, reply_markup=kb.get_meal_confirmation_kb())
        await state.set_state(NutritionStates.waiting_for_meal_confirmation)
    except (json.JSONDecodeError, KeyError):
        await message.answer("На жаль, не вдалося розпізнати страву. Спробуйте описати її простіше.")
        await state.clear()

@router.callback_query(NutritionStates.waiting_for_meal_confirmation, F.data == "confirm_meal")
async def confirm_meal_logging(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    meal_data = data.get('meal_data')
    
    await db.log_meal(
        user_id=callback.from_user.id,
        description=meal_data['meal_name'],
        calories=meal_data['calories'],
        proteins=meal_data.get('proteins', 0),
        fats=meal_data.get('fats', 0),
        carbs=meal_data.get('carbs', 0)
    )
    
    await callback.message.edit_text("✅ Прийом їжі успішно записано!")
    await state.clear()
    await callback.answer()

@router.callback_query(NutritionStates.waiting_for_meal_confirmation, F.data == "cancel_meal")
async def cancel_meal_logging(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Дію скасовано.")
    await state.clear()
    await callback.answer()

# Денний звіт
@router.message(Command("summary"), F.chat.type == "private")
async def get_summary_command(message: Message, bot: Bot):
    await send_daily_summary(message.from_user.id, bot)

async def send_daily_summary(user_id: int, bot: Bot):
    summary_data = await db.get_daily_food_summary(user_id)
    if not summary_data:
        # Не надсилаємо нічого, якщо користувач нічого не їв
        return

    report_lines = ["**Ваш раціон за сьогодні:**\n"]
    total_calories = 0
    
    for meal in summary_data:
        report_lines.append(f"- {meal[0]}: {meal[1]} ккал")
        total_calories += meal[1]
    
    # Тут логіка отримання спалених калорій та цілі
    # Для прикладу, використаємо заглушки
    burned_calories = 300 # Потрібно буде парсити з плану
    target_calories = 2200 # Потрібно буде брати з даних користувача
    activity_level = await db.get_daily_activity(user_id)
    
    report_lines.append(f"\n---")
    report_lines.append(f"**🔥 Всього спожито: {total_calories} ккал**")
    report_lines.append(f"*Рекомендована норма: ~{target_calories} ккал*")

    await send_message_safely(bot, user_id, "\n".join(report_lines))

    # Запит до Gemini для фінального аналізу
    analysis_data = {
        "goal": "Набрати масу", # Потрібно брати з даних користувача
        "consumed_calories": total_calories,
        "target_calories": target_calories,
        "burned_calories": burned_calories,
        "activity_level": activity_level
    }
    analysis_text = await gemini.get_daily_analysis(analysis_data)
    await send_message_safely(bot, user_id, analysis_text)
