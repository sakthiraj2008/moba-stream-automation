"""
Configuration loader.
All secrets come from environment variables (.env file), never hard-coded.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "anime_streaming")

# Comma-separated Telegram user IDs allowed to manage the database.
# Example in .env:  ADMIN_IDS=111111111,222222222
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Set it in your .env file.")
