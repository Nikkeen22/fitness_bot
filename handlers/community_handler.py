# community_handlers.py

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Video
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Локальні імпорти
import database as db
import keyboards as kb
from utils.safe_sender import send_message_safely
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
    # ПОВЕРНУТО ДОСТУП ЗА ІНДЕКСАМИ (tuple), оскільки db повертає кортежі
    challenge_details = await db.get_public_challenge_details(challenge_id)
    
    if not challenge_details:
        await callback.answer("Цей челендж більше неактуальний.", show_alert=True)
        await callback.message.edit_text("Цей челендж було видалено або він завершився.", reply_markup=None)
        return

    # Розпакування даних з кортежу
    _, _, title, description, duration, _, _ = challenge_details
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
    """Повертає користувача до списку челенджів."""
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
    await view_challenge(callback)

@router.callback_query(F.data.startswith("do_challenge:"))
async def do_challenge_handler(callback: CallbackQuery, state: FSMContext):
    """Запускає процес підтвердження виконання челенджу."""
    challenge_id = int(callback.data.split(":")[1])
    await state.update_data(item_id=challenge_id, proof_type='challenge')
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
        parse_mode="HTML"
    )
    await state.set_state(CommunityStates.creating_challenge_title)

@router.message(CommunityStates.creating_challenge_title, F.chat.type == "private")
async def process_challenge_title(message: Message, state: FSMContext):
    """Обробляє назву челенджу."""
    await state.update_data(title=message.text)
    await message.answer(
        "Гарна назва! \n\n<b>Крок 2:</b> Тепер опишіть суть челенджу (1-2 речення):",
        parse_mode="HTML"
    )
    await state.set_state(CommunityStates.creating_challenge_desc)

@router.message(CommunityStates.creating_challenge_desc, F.chat.type == "private")
async def process_challenge_description(message: Message, state: FSMContext):
    """Обробляє опис челенджу."""
    await state.update_data(description=message.text)
    await message.answer(
        "Майже готово. \n\n<b>Крок 3:</b> Вкажіть тривалість челенджу в днях (наприклад, 7 або 30):",
        parse_mode="HTML"
    )
    await state.set_state(CommunityStates.creating_challenge_duration)

@router.message(CommunityStates.creating_challenge_duration, F.chat.type == "private")
async def process_challenge_duration(message: Message, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    """Завершує створення челенджу і планує його автоматичне видалення."""
    try:
        duration = int(message.text)
        if not (1 <= duration <= 100):
            raise ValueError
    except ValueError:
        await message.answer("Будь ласка, введіть ціле число від 1 до 100.")
        return

    data = await state.get_data()
    await state.clear()
    
    challenge_id = await db.create_public_challenge(
        message.from_user.id, data['title'], data['description'], duration
    )
    
    run_date = datetime.now() + timedelta(days=duration)
    
    scheduler.add_job(
        db.delete_challenge, 
        trigger='date', 
        run_date=run_date, 
        args=[challenge_id],
        id=f"delete_challenge_{challenge_id}",
        replace_existing=True
    )
    print(f"✅ Заплановано видалення для челенджу ID: {challenge_id} на {run_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    await message.answer(
        f"✅ Ваш челендж успішно створено! Він буде активний {duration} днів."
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

# --- Створення дуелі ---

@router.message(Command("duel"), F.chat.type == "private")
async def create_duel_start(message: Message, bot: Bot):
    """Починає створення дуелі через команду /duel @username <опис>."""
    args = message.text.split(maxsplit=2)
    if len(args) < 3 or not args[1].startswith('@'):
        await message.answer("Неправильний формат. Використовуйте: `/duel @username <опис виклику>`")
        return

    opponent_username = args[1][1:]
    description = args[2]

    # ПОВЕРНУТО ДОСТУП ЗА ІНДЕКСАМИ (tuple)
    opponent = await db.get_user_by_username(opponent_username)
    if not opponent:
        await message.answer(f"Користувача @{opponent_username} не знайдено. Можливо, він/вона ще не спілкувався з ботом.")
        return
    
    opponent_id = opponent[0] # Доступ за індексом
    if opponent_id == message.from_user.id:
        await message.answer("Ви не можете викликати на дуель самого себе :)")
        return

    await send_duel_invitation(bot, message.from_user.id, opponent_id, opponent_username, description)
    await message.answer(f"Виклик надіслано користувачу @{opponent_username}. Очікуйте на його відповідь.")

async def send_duel_invitation(bot: Bot, initiator_id: int, opponent_id: int, opponent_username: str, description: str):
    """Створює дуель в БД та надсилає запрошення."""
    duel_id = await db.create_duel(initiator_id, opponent_id, description)
    
    initiator_info = await bot.get_chat(initiator_id)
    initiator_name = f"@{initiator_info.username}" if initiator_info.username else initiator_info.full_name

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Прийняти", callback_data=f"duel_accept:{duel_id}")
    builder.button(text="❌ Відхилити", callback_data=f"duel_reject:{duel_id}")

    await send_message_safely(
        bot, opponent_id,
        f"🤺 **Вас викликали на дуель!**\n\n"
        f"{initiator_name} кидає вам виклик:\n*«{description}»*\n\nПриймаєте?",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("duel_accept:"))
async def accept_duel(callback: CallbackQuery, bot: Bot):
    """Обробник прийняття дуелі."""
    duel_id = int(callback.data.split(":")[1])
    # ПОВЕРНУТО ДОСТУП ЗА ІНДЕКСАМИ (tuple)
    duel = await db.get_duel_by_id(duel_id)

    # Припускаємо, що статус знаходиться в 5-му елементі (індекс 4)
    if not duel or duel[4] != 'pending':
        await callback.message.edit_text("Цей виклик вже неактуальний.")
        await callback.answer()
        return

    # Розпакування даних з кортежу
    initiator_id, opponent_id, description = duel[1], duel[2], duel[3]

    if callback.from_user.id != opponent_id:
        await callback.answer("Це не ваш виклик.", show_alert=True)
        return

    await db.update_duel_status(duel_id, 'active')
    
    duel_message = f"✅ Ви прийняли виклик! Дуель «{description}» розпочато."
    action_kb = kb.get_duel_action_kb(duel_id)
    
    await callback.message.edit_text(duel_message, reply_markup=action_kb)
    await send_message_safely(bot, initiator_id, f"✅ Ваш суперник прийняв виклик! Дуель «{description}» розпочато.", reply_markup=action_kb)

    if GROUP_ID:
        try:
            initiator_info = await bot.get_chat(initiator_id)
            opponent_info = await bot.get_chat(opponent_id)
            initiator_name = f"@{initiator_info.username}" if initiator_info.username else initiator_info.full_name
            opponent_name = f"@{opponent_info.username}" if opponent_info.username else opponent_info.full_name
            
            group_message = (
                f"⚔️ <b>Нова дуель розпочато!</b> ⚔️\n\n"
                f"{initiator_name} кинув(ла) виклик {opponent_name}!\n\n"
                f"<b>Умова:</b> <i>«{description}»</i>\n\n"
                f"Слідкуємо за результатами! 🍿"
            )
            await send_message_safely(bot, int(GROUP_ID), group_message, parse_mode="HTML")
        except Exception as e:
            print(f"Помилка публікації дуелі в групу: {e}")

    await callback.answer()

@router.callback_query(F.data.startswith("duel_reject:"))
async def reject_duel(callback: CallbackQuery, bot: Bot):
    """Обробник відхилення дуелі."""
    # Тут можна додати логіку сповіщення ініціатора та видалення дуелі з БД
    await callback.message.edit_text("Ви відхилили виклик.")
    await callback.answer()

@router.callback_query(F.data.startswith("complete_duel:"))
async def complete_duel_handler(callback: CallbackQuery, state: FSMContext):
    """Запускає процес підтвердження виконання дуелі."""
    duel_id = int(callback.data.split(":")[1])
    await state.update_data(item_id=duel_id, proof_type='duel')
    await callback.message.answer("Чудово! Щоб підтвердити виконання, надішліть мені відео.")
    await state.set_state(CommunityStates.waiting_for_video_proof)
    await callback.answer()

# --- ОБРОБКА ПІДТВЕРДЖЕННЯ З ВІДЕО (ВИПРАВЛЕНА ЛОГІКА) ---
@router.message(CommunityStates.waiting_for_video_proof, F.video, F.chat.type == "private")
async def process_video_confirmation(message: Message, state: FSMContext, bot: Bot):
    """
    Обробляє надіслане відео як доказ виконання завдання (челендж або дуель)
    і пересилає його в групу спільноти з коректною логікою.
    """
    data = await state.get_data()
    proof_type = data.get("proof_type")
    item_id = data.get("item_id")
    
    await state.clear()
    await message.answer("✅ Відео отримано! Ваш доказ опубліковано в групі.", reply_markup=kb.main_menu_kb)
    
    if not GROUP_ID:
        print("GROUP_ID не встановлено. Публікація в групу неможлива.")
        return

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name

    try:
        if proof_type == 'challenge':
            await db.update_challenge_progress(message.from_user.id, item_id)
            challenge_details = await db.get_public_challenge_details(item_id)
            challenge_title = challenge_details[2] if challenge_details else "невідомого челенджу"
            
            caption_text = (
                f"🏆 <b>Прогрес у челенджі!</b>\n\n"
                f"Користувач {username} ділиться успіхом у виклику «{challenge_title}»!"
            )
            await bot.send_video(
                chat_id=int(GROUP_ID),
                video=message.video.file_id,
                caption=caption_text,
                parse_mode="HTML"
            )

        elif proof_type == 'duel':
            # 1. Відмічаємо виконання для поточного користувача
            await db.mark_duel_completed(message.from_user.id, item_id)
            
            # 2. Отримуємо ОНОВЛЕНИЙ стан дуелі, щоб прийняти рішення
            duel = await db.get_duel_by_id(item_id)
            if not duel:
                return

            # 3. Розпаковуємо дані, використовуючи імена полів для надійності
            initiator_id = duel['initiator_id']
            opponent_id = duel['opponent_id']
            description = duel['description']
            initiator_completed = duel['initiator_completed']
            opponent_completed = duel['opponent_completed']
            # 4. Отримуємо імена
            initiator_info = await bot.get_chat(initiator_id)
            opponent_info = await bot.get_chat(opponent_id)
            initiator_name = f"@{initiator_info.username}" if initiator_info.username else initiator_info.full_name
            opponent_name = f"@{opponent_info.username}" if opponent_info.username else opponent_info.full_name
            
            # 5. Перевіряємо, чи обидва виконали
            if initiator_completed and opponent_completed:
                # Це було друге відео.
                # Спочатку надсилаємо саме відео з відповідним підписом
                caption_text = (
                    f"🤺 <b>Прогрес у дуелі!</b>\n\n"
                    f"Учасник {username} також виконав(ла) свою частину завдання у дуелі між {initiator_name} та {opponent_name}!"
                )
                await bot.send_video(
                    chat_id=int(GROUP_ID),
                    video=message.video.file_id,
                    caption=caption_text,
                    parse_mode="HTML"
                )
                
                # Потім надсилаємо фінальний пост
                await db.update_duel_status(item_id, 'completed')
                final_post_text = (
                    f"⚔️ <b>Дуель завершено!</b> ⚔️\n\n"
                    f"Обидва учасники, {initiator_name} та {opponent_name}, виконали умову:\n"
                    f"<i>«{description}»</i>\n\n"
                    f"Перегляньте їхні відео вище та пишіть в коментарях, хто, на вашу думку, був кращим! 👇"
                )
                await send_message_safely(bot, int(GROUP_ID), final_post_text, parse_mode="HTML")

            else:
                # Це було перше відео
                caption_text = (
                    f"🤺 <b>Прогрес у дуелі!</b>\n\n"
                    f"Учасник {username} виконав(ла) свою частину завдання у дуелі між {initiator_name} та {opponent_name}.\n\n"
                    f"Очікуємо на відео від другого учасника!"
                )
                await bot.send_video(
                    chat_id=int(GROUP_ID),
                    video=message.video.file_id,
                    caption=caption_text,
                    parse_mode="HTML"
                )

    except Exception as e:
        print(f"ПОМИЛКА: Не вдалося відправити підтвердження в групу: {e}")

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
    
    job_id = f"delete_challenge_{challenge_id}"
    if scheduler.get_job(job_id):
        try:
            scheduler.remove_job(job_id)
            print(f"Заплановане видалення для челенджу {challenge_id} скасовано.")
        except Exception as e:
            print(f"Помилка скасування завдання {job_id}: {e}")

    await db.delete_challenge(challenge_id)
    await message.answer(f"Челендж з ID {challenge_id} та пов'язані з ним дані видалено.")

# --- Створення дуелі через FSM (для кнопки) ---
async def create_duel_start_from_button(message: Message, state: FSMContext):
    """Починає процес створення дуелі через кнопку (FSM)."""
    await message.answer("Ви вирішили кинути виклик! 🤺\n\nВведіть юзернейм вашого суперника (наприклад, @username):")
    await state.set_state(CommunityStates.creating_duel_opponent)

@router.message(CommunityStates.creating_duel_opponent, F.chat.type == "private")
async def process_duel_opponent(message: Message, state: FSMContext):
    """Обробляє юзернейм суперника для дуелі."""
    if not message.text or not message.text.startswith('@'):
        await message.answer("Неправильний формат. Будь ласка, введіть юзернейм, що починається з @.")
        return
    
    opponent_username = message.text[1:]
    # ПОВЕРНУТО ДОСТУП ЗА ІНДЕКСАМИ (tuple)
    opponent = await db.get_user_by_username(opponent_username)
    if not opponent:
        await message.answer(f"Користувача з юзернеймом @{opponent_username} не знайдено.")
        return
    
    opponent_id = opponent[0] # Доступ за індексом
    if opponent_id == message.from_user.id:
        await message.answer("Ви не можете викликати на дуель самого себе :)")
        return
        
    await state.update_data(opponent_id=opponent_id, opponent_username=opponent_username)
    await message.answer("Чудово! Тепер напишіть умову вашої дуелі (наприклад, 'Присісти 50 разів за хвилину'):")
    await state.set_state(CommunityStates.creating_duel_desc)

@router.message(CommunityStates.creating_duel_desc, F.chat.type == "private")
async def process_duel_description_and_send(message: Message, state: FSMContext, bot: Bot):
    """Обробляє опис дуелі та надсилає запрошення."""
    description = message.text
    data = await state.get_data()
    opponent_id = data.get('opponent_id')
    opponent_username = data.get('opponent_username')

    await state.clear()
    
    await send_duel_invitation(
        bot=bot,
        initiator_id=message.from_user.id,
        opponent_id=opponent_id,
        opponent_username=opponent_username,
        description=description
    )
    
    await message.answer(f"Виклик надіслано користувачу @{opponent_username}. Очікуйте на його відповідь.")
