import logging
import os # Add this import
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# --- CONFIGURATION ---
# Read secrets from the environment variables securely
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

if not BOT_TOKEN or not MONGO_URI:
    raise ValueError("Missing BOT_TOKEN or MONGO_URI environment variables.")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Connect to Database
client = AsyncIOMotorClient(MONGO_URI)
db = client.anime_db
animes_col = db.animes
episodes_col = db.episodes

# ... [The rest of the bot code remains exactly the same] ...
