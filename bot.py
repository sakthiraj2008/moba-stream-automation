import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# --- CONFIGURATION ---
# Read secrets from environment variables (Required for Render/GitHub deployment)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

if not BOT_TOKEN or not MONGO_URI:
    raise ValueError("CRITICAL ERROR: Missing BOT_TOKEN or MONGO_URI environment variables.")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Connect to Database
client = AsyncIOMotorClient(MONGO_URI)
db = client.anime_db
animes_col = db.animes
episodes_col = db.episodes

# Conversation States
TITLE, IMDB, DESC, POSTER, BANNER, EP_COUNT = range(6)
EP_NUM, EP_TITLE, EP_URL, AUDIO_URL, SUB_URL = range(6, 11)

# ==========================================
# FLOW 1: CREATE ANIME
# ==========================================
async def create_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Let's add a new anime! Send me the **Title**:")
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Got it. Send the **IMDb Rating or Link**:")
    return IMDB

async def get_imdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['imdb'] = update.message.text
    await update.message.reply_text("Great. Send the **Description**:")
    return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    await update.message.reply_text("Send the **Poster Image URL**:")
    return POSTER

async def get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['poster'] = update.message.text
    await update.message.reply_text("Send the **Banner Image URL**:")
    return BANNER

async def get_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['banner'] = update.message.text
    await update.message.reply_text("Send the **Total Episode Count** (number):")
    return EP_COUNT

async def get_ep_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_count'] = update.message.text
    
    # Save to MongoDB
    await animes_col.insert_one({
        "title": context.user_data['title'],
        "imdb": context.user_data['imdb'],
        "description": context.user_data['desc'],
        "poster": context.user_data['poster'],
        "banner": context.user_data['banner'],
        "ep_count": context.user_data['ep_count']
    })
    
    await update.message.reply_text(f"✅ Anime '{context.user_data['title']}' saved successfully!")
    return ConversationHandler.END


# ==========================================
# FLOW 2: UPLOAD EPISODE MENU
# ==========================================
async def upload_episode_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fetch recent animes from DB
    animes = await animes_col.find().to_list(length=50)
    if not animes:
        await update.message.reply_text("No animes found. Use /create_anime first.")
        return
        
    keyboard = []
    for anime in animes:
        # Pass the MongoDB ObjectId in the callback data
        keyboard.append([InlineKeyboardButton(anime['title'], callback_data=f"sel_{str(anime['_id'])}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select an anime to manage episodes:", reply_markup=reply_markup)

async def manage_episodes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # 1. User selected an anime
    if data.startswith("sel_"):
        anime_id = data.split("_")[1]
        episodes = await episodes_col.find({"anime_id": anime_id}).sort("ep_num", 1).to_list(length=100)
        
        keyboard = []
        for ep in episodes:
            keyboard.append([
                InlineKeyboardButton(f"Ep {ep.get('ep_num', '?')} - {ep['title']}", callback_data="ignore"),
                InlineKeyboardButton("❌ Delete", callback_data=f"del_{str(ep['_id'])}")
            ])
            
        keyboard.append([InlineKeyboardButton("➕ Add Episode", callback_data=f"add_{anime_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Manage Episodes:", reply_markup=reply_markup)
        
    # 2. User clicked delete on an episode
    elif data.startswith("del_"):
        ep_id = data.split("_")[1]
        await episodes_col.delete_one({"_id": ObjectId(ep_id)})
        await query.edit_message_text("✅ Episode deleted! Send /upload_episode to manage again.")


# ==========================================
# FLOW 3: ADD EPISODE CONVERSATION
# ==========================================
async def add_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Extract anime ID from the 'Add Episode' button's callback data
    context.user_data['anime_id'] = query.data.split("_")[1]
    
    # Send a new message so the user can easily reply
    await query.message.reply_text("Send the **Episode Number** (e.g., 1):")
    return EP_NUM

async def get_ep_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_num'] = update.message.text
    await update.message.reply_text("Send the **Video Title**:")
    return EP_TITLE

async def get_ep_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_title'] = update.message.text
    await update.message.reply_text("Send the **Video URL**:")
    return EP_URL

async def get_ep_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_url'] = update.message.text
    await update.message.reply_text("Send the **Audio URL** (or type 'skip'):")
    return AUDIO_URL

async def get_audio_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['audio_url'] = text if text.lower() != 'skip' else None
    await update.message.reply_text("Send the **Subtitle URL** (or type 'skip'):")
    return SUB_URL

async def get_sub_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    sub_url = text if text.lower() != 'skip' else None
    
    # Save episode to MongoDB
    await episodes_col.insert_one({
        "anime_id": context.user_data['anime_id'],
        "ep_num": int(context.user_data['ep_num']),
        "title": context.user_data['ep_title'],
        "video_url": context.user_data['ep_url'],
        "audio_url": context.user_data['audio_url'],
        "subtitle_url": sub_url
    })
    
    await update.message.reply_text("✅ Episode added successfully! Use /upload_episode to see it.")
    return ConversationHandler.END


# ==========================================
# CANCEL HANDLER
# ==========================================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Action cancelled. You can start over.")
    return ConversationHandler.END


# ==========================================
# MAIN APPLICATION
# ==========================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Define the Create Anime Conversation
    create_anime_conv = ConversationHandler(
        entry_points=[CommandHandler("create_anime", create_anime_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            IMDB: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_imdb)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            POSTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_poster)],
            BANNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_banner)],
            EP_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ep_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Define the Add Episode Conversation (Triggered via Inline Button)
    add_ep_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_episode_start, pattern="^add_")],
        states={
            EP_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ep_num)],
            EP_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ep_title)],
            EP_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ep_url)],
            AUDIO_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_audio_url)],
            SUB_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sub_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add handlers to the app
    app.add_handler(create_anime_conv)
    app.add_handler(add_ep_conv)
    
    # Independent handlers for menus and deletion
    app.add_handler(CommandHandler("upload_episode", upload_episode_menu))
    app.add_handler(CallbackQueryHandler(manage_episodes_callback, pattern="^(sel_|del_)"))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
