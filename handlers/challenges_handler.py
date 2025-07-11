from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from datetime import datetime
import database as db
import keyboards as kb
import challenges as ch
import achievements

router = Router()

async def show_challenges_list(message_or_callback: Message | CallbackQuery):
    text = "🎯 **Доступні челенджі**\n\nОберіть виклик, щоб дізнатись більше або приєднатись:"
    markup = kb.get_challenges_kb()
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=markup)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=markup)

@router.message(Command("challenges"))
async def cmd_challenges(message: Message):
    await show_challenges_list(message)

@router.callback_query(F.data == "back_to_challenges")
async def back_to_challenges_list(callback: CallbackQuery):
    await show_challenges_list(callback)
    await callback.answer()

@router.callback_query(F.data.startswith("view_challenge:"))
async def view_challenge(callback: CallbackQuery):
    challenge_id = callback.data.split(":")[1]
    challenge_details = ch.CHALLENGES[challenge_id]
    user_id = callback.from_user.id
    
    active_challenge = await db.get_active_challenge(user_id)
    is_this_challenge_active = active_challenge and active_challenge[0] == challenge_id

    text = f"**{challenge_details['name']}**\n\n_{challenge_details['description']}_\n\nТривалість: {challenge_details['duration_days']} днів."

    if is_this_challenge_active:
        start_date = datetime.fromisoformat(active_challenge[1])
        last_completed_day = active_challenge[2]
        current_day_of_challenge = (datetime.now() - start_date).days
        text += f"\n\n**Ваш прогрес:** День {last_completed_day}/{challenge_details['duration_days']}"
        if last_completed_day > current_day_of_challenge:
             text += "\n\nВи вже виконали сьогоднішнє завдання. Так тримати!"

    await callback.message.edit_text(
        text,
        reply_markup=kb.get_challenge_action_kb(challenge_id, is_this_challenge_active),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("join_challenge:"))
async def join_challenge_handler(callback: CallbackQuery, bot: Bot):
    challenge_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    await db.join_challenge(user_id, challenge_id)
    await achievements.check_and_grant_achievement(user_id, 'challenger', bot)
    
    await callback.message.edit_text(
        f"Ви успішно приєднались до челенджу **'{ch.CHALLENGES[challenge_id]['name']}'**! "
        f"Заходьте сюди щодня, щоб відмічати свій прогрес.",
        parse_mode="Markdown",
        reply_markup=kb.get_challenge_action_kb(challenge_id, is_active=True)
    )
    await callback.answer("Успіх!")

@router.callback_query(F.data.startswith("do_challenge:"))
async def do_challenge_handler(callback: CallbackQuery):
    challenge_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    active_challenge = await db.get_active_challenge(user_id)
    if not active_challenge or active_challenge[0] != challenge_id:
        await callback.answer("Це не ваш активний челендж.", show_alert=True)
        return

    start_date = datetime.fromisoformat(active_challenge[1])
    last_completed_day = active_challenge[2]
    current_day_of_challenge = (datetime.now() - start_date).days

    if last_completed_day > current_day_of_challenge:
        await callback.answer("Ви вже виконали сьогоднішнє завдання.", show_alert=True)
        return

    await db.complete_challenge_day(user_id, challenge_id)
    new_progress = last_completed_day + 1
    
    await callback.answer(f"День {new_progress} зараховано!", show_alert=True)

    challenge_details = ch.CHALLENGES[challenge_id]
    if new_progress >= challenge_details['duration_days']:
        await callback.message.edit_text(f"🎉 **Вітаємо!** 🎉\n\nВи успішно завершили челендж **'{challenge_details['name']}'**!")
    else:
        await view_challenge(callback)


