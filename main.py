import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TELEGRAM_BOT_TOKEN
from handlers import common, onboarding, user_commands, community_handler, group_handler, tools_handler, menu_handler, nutrition_handler
from database import init_db
from scheduler import setup_scheduler
from middlewares.subscription import SubscriptionMiddleware
from bot_commands import set_bot_commands  # імпорт функції

async def main():
    await init_db()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await set_bot_commands(bot)  # <-- тут правильно

    dp = Dispatcher(bot=bot)

    # Реєструємо middleware
    dp.message.middleware(SubscriptionMiddleware())
    
    # Реєструємо роутери
    dp.include_router(menu_handler.router)
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(user_commands.router)
    dp.include_router(community_handler.router)
    dp.include_router(group_handler.router)
    dp.include_router(tools_handler.router)
    dp.include_router(nutrition_handler.router)

    # Планувальник
    scheduler = setup_scheduler(bot)  # старт тут виконується всередині setup_scheduler
    
    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинено.")
