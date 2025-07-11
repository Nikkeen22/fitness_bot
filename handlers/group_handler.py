from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.enums import ChatMemberStatus
import database as db

router = Router()

@router.my_chat_member(F.chat.type.in_({"group", "supergroup"}))
async def on_user_join_group(event: ChatMemberUpdated):
    # Коли користувач приєднується до групи, відмічаємо це в базі
    if event.new_chat_member.status not in [ChatMemberStatus.KICKED, ChatMemberStatus.LEFT, ChatMemberStatus.RESTRICTED]:
        await db.set_user_in_group(event.new_chat_member.user.id)

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_messages(message: Message):
    # Порожній обробник, щоб бот не реагував на звичайні повідомлення в групі
    pass
