from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import database as db
import achievements
import keyboards as kb
from config import ADMIN_ID, PAYMENT_CARD_NUMBER
from utils.safe_sender import answer_message_safely, send_message_safely
import random
from datetime import datetime

router = Router()

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "**Основні команди:**\n"
        "/start - Розпочати роботу або оновити дані\n"
        "/myplan - Переглянути ваш поточний план\n"
        "/progress - Ваша статистика тренувань\n"
        "/achievements - Мої досягнення\n\n"
        "**Спільнота та Челенджі (тільки в приватних повідомленнях):**\n"
        "/challenges - Переглянути та приєднатись до викликів\n"
        "/create_challenge - Створити публічний виклик\n"
        "/duel @username <опис> - Кинути виклик іншому учаснику\n\n"
        "**Додаткові утиліти:**\n"
        "/food - Отримати рецепт з продуктів\n"
        "/tip - Отримати корисну пораду\n\n"
        "**Підписка:**\n"
        "/subscribe - Керування підпискою\n\n"
        "**Інше:**\n"
        "/cancel - Скасувати поточну дію"
    )
    if str(message.from_user.id) == ADMIN_ID:
        help_text += "\n\n**Адмін-команди:**\n/grant <user_id> - Надати довічний доступ"
    await answer_message_safely(message, help_text)

# ... (решта файлу без змін, але без /start та /newplan)
@router.message(F.text.casefold() == "скасувати", Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Немає активних дій для скасування.")
        return
    await state.clear()
    await message.answer("Дію скасовано.")
@router.message(Command("myplan"))
async def cmd_myplan(message: Message):
    plan = await db.get_user_plan(message.from_user.id)
    if plan:
        await message.answer("Ось ваш поточний план:")
        await answer_message_safely(message, plan)
    else:
        await message.answer("У вас ще немає плану. Натисніть /start.")
@router.message(Command("achievements"))
async def cmd_achievements(message: Message):
    user_achievements = await db.get_user_achievements(message.from_user.id)
    if not user_achievements:
        await message.answer("У вас поки що немає досягнень. Час починати тренування! 💪")
        return
    response_text = "🏆 **Ваші досягнення:**\n\n"
    for ach_tuple in user_achievements:
        ach_id = ach_tuple[0]
        achievement = achievements.ACHIEVEMENTS.get(ach_id)
        if achievement:
            response_text += f"**{achievement['name']}**: _{achievement['description']}_\n"
    await answer_message_safely(message, response_text)
@router.callback_query(F.data == "workout_done")
async def process_workout_done(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    await db.log_workout_completion(user_id)
    await achievements.check_workout_achievements(user_id, bot)
    await callback.message.edit_text("✅ Чудова робота! Тренування зараховано.")
    await callback.answer()
@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    status, expiry_date = await db.get_user_subscription_status(message.from_user.id)
    if str(message.from_user.id) == ADMIN_ID:
        text = "👑 Ви адміністратор. Вам надано довічний доступ."
    elif status == 'active':
        text = f"✅ Ваша підписка активна до {expiry_date.strftime('%d.%m.%Y')}"
    elif status == 'trial':
        text = f"⏳ У вас активний безкоштовний період до {expiry_date.strftime('%d.%m.%Y')}"
    else:
        text = "❌ У вас немає активної підписки."
    await message.answer(text, reply_markup=kb.subscribe_kb)
@router.callback_query(F.data == "initiate_payment")
async def initiate_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    payment_code = f"{random.randint(100, 999)}-{random.randint(100, 999)}"
    await db.add_pending_payment(user_id, payment_code)
    payment_details = (
        f"Для оплати підписки (49 грн/міс) перекажіть кошти на картку:\n\n"
        f"`{PAYMENT_CARD_NUMBER}`\n\n"
        f"**ОБОВ'ЯЗКОВО** вкажіть в призначенні/коментарі до платежу цей унікальний код:\n\n"
        f"`{payment_code}`\n\n"
        f"Після успішної оплати натисніть кнопку нижче."
    )
    await answer_message_safely(callback.message, payment_details, reply_markup=kb.confirm_user_payment_kb)
    await callback.answer()
@router.callback_query(F.data == "user_confirm_payment")
async def user_confirm_payment(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    payment_code = await db.get_pending_payment_code(user.id)
    if not payment_code:
        await callback.message.edit_text("Ви вже надіслали запит. Будь ласка, очікуйте на підтвердження.")
        await callback.answer()
        return
    admin_notification = (
        f"🔔 **Запит на підтвердження оплати!**\n\n"
        f"Користувач: {user.full_name}\n"
        f"Username: @{user.username}\n"
        f"ID: `{user.id}`\n"
        f"**КОД ПЛАТЕЖУ: `{payment_code}`**\n\n"
        f"Стверджує, що оплатив підписку. Будь ласка, перевірте надходження та підтвердіть або відхиліть платіж."
    )
    try:
        await send_message_safely(bot, int(ADMIN_ID), admin_notification, reply_markup=kb.get_admin_payment_kb(user.id))
        await callback.message.edit_text("Дякуємо! Ваш запит надіслано адміністратору. Перевірка може зайняти деякий час.")
    except Exception as e:
        print(f"Помилка відправки повідомлення адміну: {e}")
        await callback.message.answer("Виникла помилка при відправці запиту.")
    await callback.answer()
@router.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_payment(callback: CallbackQuery, bot: Bot):
    target_user_id = int(callback.data.split(":")[1])
    await db.update_user_subscription(target_user_id, months=1)
    await db.delete_pending_payment(target_user_id)
    receipt_text = (f"🧾 **Квитанція про оплату**\n\n**Послуга:** Підписка на AI Fitness Coach (1 місяць)\n**Сума:** 49.00 грн\n**Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\nДякуємо, що ви з нами!")
    try:
        await send_message_safely(bot, target_user_id, "✅ Вашу оплату підтверджено! Підписку активовано на 1 місяць.")
        await send_message_safely(bot, target_user_id, receipt_text)
        await callback.message.edit_text(f"✅ Оплату для користувача {target_user_id} підтверджено.")
    except Exception as e:
        await callback.message.edit_text(f"Помилка! Не вдалося надіслати повідомлення користувачу {target_user_id}. Помилка: {e}")
    await callback.answer()
@router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject_payment(callback: CallbackQuery, bot: Bot):
    target_user_id = int(callback.data.split(":")[1])
    await db.delete_pending_payment(target_user_id)
    try:
        await send_message_safely(bot, target_user_id, "❌ На жаль, ваш платіж не було знайдено.")
        await callback.message.edit_text(f"❌ Запит на оплату для користувача {target_user_id} відхилено.")
    except Exception as e:
        await callback.message.edit_text(f"Помилка! Не вдалося надіслати повідомлення користувачу {target_user_id}. Помилка: {e}")
    await callback.answer()
@router.message(Command("grant"))
async def cmd_grant(message: Message, bot: Bot):
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer("У вас немає доступу до цієї команди.")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Будь ласка, вкажіть ID користувача. Використання: /grant <user_id>")
        return
    try:
        target_user_id = int(args[1])
        await db.grant_lifetime_access(target_user_id)
        await message.answer(f"✅ Довічний доступ успішно надано користувачу з ID {target_user_id}.")
        await send_message_safely(bot, target_user_id, "🎉 Вітаємо! Адміністратор надав вам довічний безкоштовний доступ.")
    except ValueError:
        await message.answer("Неправильний ID. Будь ласка, введіть число.")
    except Exception as e:
        await message.answer(f"Виникла помилка: {e}")

