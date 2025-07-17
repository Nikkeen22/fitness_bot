from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Video
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Локальні імпорти
import database as db
import keyboards as kb
from utils.safe_sender import answer_message_safely, send_message_safely
from config import GROUP_ID
import achievements

router = Router()

# Визначення станів для FSM
class CommunityStates(StatesGroup):
    creating_challenge_title = State()
    creating_challenge_desc = State()
    creating_challenge_duration = State()
    waiting_for_video_proof = State()
    creating_duel_opponent = State()
    creating_duel_desc = State()

# --- Перегляд та приєднання до челенджів ---

@router.message(Command("challenges"), F.chat.type == "private")
async def list_challenges(message: Message):
    """Показує список активних публічних челенджів."""
    challenges = await db.get_public_challenges()
    if not challenges:
        await message.answer(
            "Наразі немає активних публічних челенджів. "
            "Ви можете створити свій за допомогою команди /create_challenge!"
        )
        return
    
    await message.answer(
        "Ось список доступних челенджів. Оберіть, щоб дізнатись більше та приєднатись:",
        reply_markup=kb.get_challenges_kb(challenges)
    )

@router.callback_query(F.data.startswith("view_challenge:"))
async def view_challenge(callback: CallbackQuery):
    """Показує детальну інформацію про вибраний челендж."""
    challenge_id = int(callback.data.split(":")[1])
    challenge_details = await db.get_public_challenge_details(challenge_id)
    
    if not challenge_details:
        await callback.answer("Цей челендж більше неактуальний.", show_alert=True)
        await callback.message.edit_text("Цей челендж було видалено або він завершився.", reply_markup=None)
        return

    # Розпакування даних з бази
    _, author_id, title, description, duration, _, _ = challenge_details
    text = (
        f"<b>{title}</b>\n\n"
        f"<i>{description}</i>\n\n"
        f"Тривалість: {duration} днів.\n"
        f"ID челенджу для адміна: <code>{challenge_id}</code>"
    )
    
    is_participant = await db.get_user_challenge_progress(callback.from_user.id, challenge_id) is not None
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.get_challenge_action_kb(challenge_id, is_participant),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_challenges_list")
async def back_to_challenges(callback: CallbackQuery):
    """Повертає користувача до списку челенджів, видаляючи попереднє повідомлення."""
    await list_challenges(callback.message)
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data.startswith("join_challenge:"))
async def join_challenge_handler(callback: CallbackQuery, bot: Bot):
    """Обробляє приєднання користувача до челенджу."""
    challenge_id = int(callback.data.split(":")[1])
    
    if await db.get_user_challenge_progress(callback.from_user.id, challenge_id):
        await callback.answer("Ви вже приєднані до цього челенджу.", show_alert=True)
        return
        
    await db.join_public_challenge(callback.from_user.id, challenge_id)
    await achievements.check_and_grant_achievement(callback.from_user.id, 'challenger', bot)
    await callback.answer("Ви успішно приєднались до челенджу!", show_alert=True)
    await view_challenge(callback)  # Оновлюємо вигляд, щоб показати кнопку "Відмітити"

@router.callback_query(F.data.startswith("do_challenge:"))
async def do_challenge_handler(callback: CallbackQuery, state: FSMContext):
    """Запускає процес підтвердження виконання челенджу."""
    challenge_id = int(callback.data.split(":")[1])
    await state.update_data(challenge_id=challenge_id, proof_type='challenge')
    await callback.message.answer("Чудово! Щоб підтвердити виконання, надішліть мені відео.")
    await state.set_state(CommunityStates.waiting_for_video_proof)
    await callback.answer()

# --- Створення публічного челенджу ---

@router.message(Command("create_challenge"), F.chat.type == "private")
async def create_challenge_start(message: Message, state: FSMContext):
    """Починає процес створення нового челенджу."""
    await message.answer(
        "Чудово! Давайте створимо новий виклик для спільноти.\n\n"
        "<b>Крок 1:</b> Введіть назву челенджу (наприклад, '30 днів без солодкого'):",
        parse_mode="HTML"  # <-- ДОДАНО
    )
    await state.set_state(CommunityStates.creating_challenge_title)

@router.message(CommunityStates.creating_challenge_title, F.chat.type == "private")
async def process_challenge_title(message: Message, state: FSMContext):
    """Обробляє назву челенджу."""
    await state.update_data(title=message.text)
    await message.answer(
        "Гарна назва! \n\n<b>Крок 2:</b> Тепер опишіть суть челенджу (1-2 речення):",
        parse_mode="HTML"  # <-- ДОДАНО
    )
    await state.set_state(CommunityStates.creating_challenge_desc)

@router.message(CommunityStates.creating_challenge_desc, F.chat.type == "private")
async def process_challenge_description(message: Message, state: FSMContext):
    """Обробляє опис челенджу."""
    await state.update_data(description=message.text)
    await message.answer(
        "Майже готово. \n\n<b>Крок 3:</b> Вкажіть тривалість челенджу в днях (наприклад, 7 або 30):",
        parse_mode="HTML"  # <-- ДОДАНО
    )
    await state.set_state(CommunityStates.creating_challenge_duration)



@router.message(CommunityStates.creating_challenge_duration, F.chat.type == "private")
async def process_challenge_duration(message: Message, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    """Завершує створення челенджу і планує його автоматичне видалення."""
    try:
        duration = int(message.text)
        if not (1 <= duration <= 100):  # Дозволяємо від 1 дня
            raise ValueError
    except ValueError:
        await message.answer("Будь ласка, введіть ціле число від 1 до 100.")
        return

    data = await state.get_data()
    
    challenge_id = await db.create_public_challenge(
        message.from_user.id, data['title'], data['description'], duration
    )
    
    run_date = datetime.now() + timedelta(days=duration)
    
    scheduler.add_job(
        db.delete_challenge, 
        trigger='date', 
        run_date=run_date, 
        args=[challenge_id],
        id=f"delete_challenge_{challenge_id}"  # Унікальний ID для завдання
    )
    print(f"✅ Заплановано видалення для челенджу ID: {challenge_id} на {run_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    await state.clear()
    
    await message.answer(
        f"✅ Ваш челендж успішно створено! Він буде активний {duration} днів, а потім автоматично видалиться."
    )

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    group_message = (
        f"🔥 <b>Новий виклик від {username}!</b> 🔥\n\n"
        f"<b>Назва:</b> {data['title']}\n"
        f"<b>Опис:</b> {data['description']}\n"
        f"<b>Тривалість:</b> {duration} днів\n\n"
        f"<i>Приєднуйтесь до виклику в особистих повідомленнях з ботом через команду /challenges!</i>"
    )
    if GROUP_ID:
        await send_message_safely(bot, int(GROUP_ID), group_message, parse_mode="HTML")

# --- Адмін-команди ---

@router.message(Command("delete_challenge"), F.chat.type == "private")
async def delete_challenge_command(message: Message, scheduler: AsyncIOScheduler):
    """Команда для адміністратора для ручного видалення челенджу."""
    if not await db.is_admin(message.from_user.id):
        await message.answer("Ця команда доступна лише адміністратору.")
        return
    
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Неправильний формат. Вкажіть ID челенджу: `/delete_challenge 123`")
        return
        
    challenge_id = int(args[1])
    await db.delete_challenge(challenge_id)
    
    # Спроба скасувати заплановане завдання, якщо воно існує
    try:
        scheduler.remove_job(f"delete_challenge_{challenge_id}")
        await message.answer(f"Челендж з ID {challenge_id} видалено, заплановане видалення скасовано.")
    except Exception:
        await message.answer(f"Челендж з ID {challenge_id} видалено з бази даних.")


# --- Створення дуелі ---
@router.message(Command("duel"), F.chat.type == "private")
async def create_duel_start(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=2)
    if len(args) < 3 or not args[1].startswith('@'):
        await message.answer("Неправильний формат. Використовуйте: `/duel @username <опис виклику>`")
        return

    opponent_username = args[1][1:]
    description = args[2]

    opponent = await db.get_user_by_username(opponent_username)
    if not opponent:
        await message.answer(f"Користувача з юзернеймом @{opponent_username} не знайдено. Можливо, він/вона ще не запускав(ла) нашого бота. Попросіть його/її написати боту /start.")
        return
    
    opponent_id = opponent[0]
    if opponent_id == message.from_user.id:
        await message.answer("Ви не можете викликати на дуель самого себе :)")
        return

    duel_id = await db.create_duel(message.from_user.id, opponent_id, description)
    
    initiator_info = await message.bot.get_chat(message.from_user.id)
    initiator_name = f"@{initiator_info.username}" if initiator_info.username else initiator_info.full_name

    duel_invite_kb = kb.InlineKeyboardBuilder()
    duel_invite_kb.button(text="✅ Прийняти", callback_data=f"duel_accept:{duel_id}")
    duel_invite_kb.button(text="❌ Відхилити", callback_data=f"duel_reject:{duel_id}")

    await send_message_safely(
        message.bot, opponent_id,
        f"🤺 **Вас викликали на дуель!**\n\n"
        f"{initiator_name} кидає вам виклик:\n*«{description}»*\n\nПриймаєте?",
        reply_markup=duel_invite_kb.as_markup()
    )
    await message.answer(f"Виклик надіслано користувачу @{opponent_username}. Очікуйте на його відповідь.")

@router.callback_query(F.data.startswith("duel_accept:"))
async def accept_duel(callback: CallbackQuery, bot: Bot):
    duel_id = int(callback.data.split(":")[1])
    duel = await db.get_duel_by_id(duel_id)
    if not duel or duel[4] != 'pending':
        await callback.message.edit_text("Цей виклик вже неактуальний.")
        return

    initiator_id, opponent_id, description = duel[1], duel[2], duel[3]
    if callback.from_user.id != opponent_id:
        await callback.answer("Це не ваш виклик.", show_alert=True)
        return

    await db.update_duel_status(duel_id, 'active')
    
    duel_message = f"✅ Ви прийняли виклик! Дуель «{description}» розпочато."
    await callback.message.edit_text(duel_message, reply_markup=kb.get_duel_action_kb(duel_id))
    
    await send_message_safely(bot, initiator_id, f"✅ Ваш суперник прийняв виклик! Дуель «{description}» розпочато.", reply_markup=kb.get_duel_action_kb(duel_id))

    # --- Публікація в групу про початок дуелі ---
    if GROUP_ID:
        try:
            initiator_info = await bot.get_chat(initiator_id)
            opponent_info = await bot.get_chat(opponent_id)

            initiator_name = f"@{initiator_info.username}" if initiator_info.username else initiator_info.full_name
            opponent_name = f"@{opponent_info.username}" if opponent_info.username else opponent_info.full_name
            
            group_message = (
                f"⚔️ **Нова дуель розпочато!** ⚔️\n\n"
                f"{initiator_name} кинув(ла) виклик {opponent_name}!\n\n"
                f"**Умова:** *«{description}»*\n\n"
                f"Слідкуємо за результатами! 🍿"
            )
            await send_message_safely(bot, int(GROUP_ID), group_message)
        except Exception as e:
            print(f"Не вдалося опублікувати дуель в групу: {e}")

    await callback.answer()


@router.callback_query(F.data.startswith("complete_duel:"))
async def complete_duel_handler(callback: CallbackQuery, state: FSMContext):
    duel_id = int(callback.data.split(":")[1])
    await state.update_data(duel_id=duel_id, proof_type='duel')
    await callback.message.answer("Чудово! Щоб підтвердити виконання, надішліть мені відео.")
    await state.set_state(CommunityStates.waiting_for_video_proof)
    await callback.answer()

# --- Підтвердження з відео ---
@router.message(CommunityStates.waiting_for_video_proof, F.video, F.chat.type == "private")
async def process_video_confirmation(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    proof_type = data.get("proof_type")
    await state.clear()

    await message.answer("✅ Відео отримано! Ваш доказ опубліковано в групі.", reply_markup=kb.main_menu_kb)

    if GROUP_ID:
        username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
        caption_text = "" # Створимо змінну для підпису до відео

        if proof_type == 'challenge':
            challenge_id = data.get("challenge_id")
            await db.update_challenge_progress(message.from_user.id, challenge_id)
            # Отримаємо назву челенджу для більшої інформативності
            challenge_details = await db.get_public_challenge_details(challenge_id)
            challenge_title = challenge_details[2] if challenge_details else "невідомого челенджу"
            caption_text = f"🏆 **Прогрес у челенджі!**\n\nКористувач {username} ділиться своїм успіхом у виклику «{challenge_title}»!"

        elif proof_type == 'duel':
            duel_id = data.get("duel_id")
            await db.mark_duel_completed(message.from_user.id, duel_id)
            duel = await db.get_duel_by_id(duel_id)
            # Перевірка, чи дуель завершена обома учасниками
            if duel and duel.get('initiator_completed') and duel.get('opponent_completed'):
                await db.update_duel_status(duel_id, 'completed')
            caption_text = f"🤺 **Прогрес у дуелі!**\n\nУчасник {username} виконав завдання!"

        else:
            caption_text = f"🏆 **Підтвердження виконання!**\n\nКористувач {username} ділиться своїм прогресом!"

        # Надійно відправляємо відео з підписом в групу
        try:
            await bot.send_video(
                chat_id=int(GROUP_ID),
                video=message.video.file_id,
                caption=caption_text,
                parse_mode="HTML" # Якщо використовуєте форматування в тексті
            )
        except Exception as e:
            print(f"Помилка при відправці відео в групу: {e}")
            # Можна додати сповіщення адміністратору про помилку
@router.message(Command("delete_challenge"), F.chat.type == "private")
async def delete_challenge_command(message: Message):
    if not await db.is_admin(message.from_user.id):
        await message.answer("Тільки адміністратор може видаляти челенджі.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Вкажіть ID челенджу: /delete_challenge <id>")
        return
    challenge_id = int(args[1])
    await db.delete_challenge(challenge_id)
    await message.answer("Челендж видалено.")

@router.callback_query(F.data == "tool_duel")
async def duel_start_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Ви вирішили кинути виклик! 🤺\n\nВведіть юзернейм вашого суперника (наприклад, @username):")
    await state.set_state(CommunityStates.creating_duel_opponent)
    await callback.answer()

async def create_duel_start_from_button(message: Message, state: FSMContext):
    await message.answer("Ви вирішили кинути виклик! 🤺\n\nВведіть юзернейм вашого суперника (наприклад, @username):")
    await state.set_state(CommunityStates.creating_duel_opponent)

@router.message(CommunityStates.creating_duel_opponent, F.chat.type == "private")
async def process_duel_opponent(message: Message, state: FSMContext):
    if not message.text or not message.text.startswith('@'):
        await message.answer("Неправильний формат. Будь ласка, введіть юзернейм, що починається з @.")
        return
    
    opponent_username = message.text[1:]
    opponent = await db.get_user_by_username(opponent_username)
    if not opponent:
        await message.answer(f"Користувача з юзернеймом @{opponent_username} не знайдено. Можливо, він/вона ще не запускав(ла) нашого бота. Попросіть його/її написати боту /start.")
        return
    
    opponent_id = opponent[0]
    if opponent_id == message.from_user.id:
        await message.answer("Ви не можете викликати на дуель самого себе :)")
        return
        
    await state.update_data(opponent_id=opponent_id, opponent_username=opponent_username)
    await message.answer("Чудово! Тепер напишіть умову вашої дуелі (наприклад, 'Присісти 50 разів за хвилину'):")
    await state.set_state(CommunityStates.creating_duel_desc)

@router.message(CommunityStates.creating_duel_desc, F.chat.type == "private")
async def process_duel_description_and_send(message: Message, state: FSMContext, bot: Bot):
    description = message.text
    data = await state.get_data()
    opponent_id = data.get('opponent_id')
    opponent_username = data.get('opponent_username')

    await state.clear()
    
    duel_id = await db.create_duel(message.from_user.id, opponent_id, description)
    
    initiator_info = await bot.get_chat(message.from_user.id)
    initiator_name = f"@{initiator_info.username}" if initiator_info.username else initiator_info.full_name

    duel_invite_kb = kb.InlineKeyboardBuilder()
    duel_invite_kb.button(text="✅ Прийняти", callback_data=f"duel_accept:{duel_id}")
    duel_invite_kb.button(text="❌ Відхилити", callback_data=f"duel_reject:{duel_id}")

    await send_message_safely(
        bot, opponent_id,
        f"🤺 **Вас викликали на дуель!**\n\n"
        f"{initiator_name} кидає вам виклик:\n*«{description}»*\n\nПриймаєте?",
        reply_markup=duel_invite_kb.as_markup()
    )
    await message.answer(f"Виклик надіслано користувачу @{opponent_username}. Очікуйте на його відповідь.")


#111