from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter # <-- ДОДАНО ПРАВИЛЬНИЙ ІМПОРТ
from .common import cmd_myplan
from .user_commands import cmd_progress
from .tools_handler import show_tools_menu, start_ai_chat

router = Router()

# Фільтр state=None гарантує, що ці кнопки працюватимуть, лише коли користувач не в активному діалозі
@router.message(F.chat.type == "private", F.text == "📝 Мій план", StateFilter(None))
async def handle_my_plan_button(message: Message, state: FSMContext):
    await cmd_myplan(message)

@router.message(F.chat.type == "private", F.text == "📊 Прогрес", StateFilter(None))
async def handle_progress_button(message: Message, state: FSMContext):
    await cmd_progress(message)

@router.message(F.chat.type == "private", F.text == "💬 Чат з AI-тренером", StateFilter(None))
async def handle_ai_chat_button(message: Message, state: FSMContext):
    await start_ai_chat(message, state)

@router.message(F.chat.type == "private", F.text == "⚙️ Інструменти", StateFilter(None))
async def handle_tools_button(message: Message, state: FSMContext):
    await show_tools_menu(message)
