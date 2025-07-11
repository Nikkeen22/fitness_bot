from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
import database as db
import keyboards as kb
from config import ADMIN_ID

PUBLIC_COMMANDS = ['start', 'help', 'newplan', 'subscribe', 'grant']

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id

        if str(user_id) == ADMIN_ID:
            return await handler(event, data)

        if event.text and event.text.startswith('/'):
            command = event.text[1:].split()[0]
            if command in PUBLIC_COMMANDS:
                return await handler(event, data)

        status, expiry_date = await db.get_user_subscription_status(user_id)

        if status in ['trial', 'active']:
            return await handler(event, data)
        else:
            text = "На жаль, ваш доступ до функцій бота обмежено. 😥\n\n"
            if status == 'trial':
                 text = "Ваш безкоштовний 7-денний період закінчився. Щоб продовжити користуватись усіма перевагами, будь ласка, оформіть підписку.\n\n"
            elif status == 'expired':
                text = "Термін дії вашої підписки закінчився. Будь ласка, поновіть її, щоб продовжити.\n\n"
            
            text += "Це дасть вам доступ до персоналізованих планів, порад, челенджів та багато іншого!"
            await event.answer(text, reply_markup=kb.subscribe_kb)
            return

