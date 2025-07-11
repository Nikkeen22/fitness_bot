from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Розпочати роботу або оновити дані"),
        BotCommand(command="myplan", description="Переглянути ваш поточний план"),
        BotCommand(command="progress", description="Ваша статистика тренувань"),
        BotCommand(command="achievements", description="Мої досягнення"),
        BotCommand(command="challenges", description="Виклики спільноти"),
        BotCommand(command="create_challenge", description="Створити публічний виклик"),
        BotCommand(command="duel", description="Кинути дуель іншому учаснику"),
        BotCommand(command="food", description="Рецепт з продуктів"),
        BotCommand(command="tip", description="Корисна порада"),
        BotCommand(command="subscribe", description="Керування підпискою"),
        BotCommand(command="cancel", description="Скасувати поточну дію"),
        BotCommand(command="help", description="Перелік доступних команд"),
    ]
    
    # Підказки доступні лише в особистих чатах
    await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
