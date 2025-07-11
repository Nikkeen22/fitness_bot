import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER")
GROUP_ID = os.getenv("GROUP_ID")
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK")

