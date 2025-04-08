import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials (get these from my.telegram.org)
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# SUDO_USERS: list of admin user IDs (space-separated integers)
SUDO_USER = [int(x) for x in os.getenv("SUDO_USER", "").split() if x.isdigit()]

# Log group ID (for group-mode message forwarding)
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "0"))

# Welcome message for private chat
PRIVATE_START_MESSAGE = os.getenv("PRIVATE_START_MESSAGE", "Hello! Welcome to my Personal Assistant Bot.")

# MongoDB connection string
MONGO_DB_URI = os.getenv("MONGO_DB_URI", None)