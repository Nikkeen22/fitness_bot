from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

async def send_message_safely(bot: Bot, chat_id: int, text: str, **kwargs):
    """
    Безпечно надсилає повідомлення, переходячи на звичайний текст у разі помилки Markdown.
    """
    try:
        await bot.send_message(chat_id, text, parse_mode="Markdown", **kwargs)
    except TelegramBadRequest:
        kwargs.pop('parse_mode', None)
        await bot.send_message(chat_id, text, **kwargs)

async def answer_message_safely(message: Message, text: str, **kwargs):
    """
    Безпечно відповідає на повідомлення, переходячи на звичайний текст у разі помилки Markdown.
    """
    try:
        await message.answer(text, parse_mode="Markdown", **kwargs)
    except TelegramBadRequest:
        kwargs.pop('parse_mode', None)
        await message.answer(text, **kwargs)

