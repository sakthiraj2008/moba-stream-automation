"""
/create_anime conversation flow:
title -> imdb -> poster -> banner -> description -> year -> save to MongoDB
Poster/Banner accept either a photo upload (stores telegram file_id) or a
pasted image URL (stores the URL directly).
"""
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
)

import database as db
from utils import is_admin

TITLE, IMDB, POSTER, BANNER, DESCRIPTION, YEAR = range(6)


async def create_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return ConversationHandler.END
    context.user_data["new_anime"] = {}
    await update.message.reply_text(
        "🎬 Let's add a new anime.\n\nSend the *title*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TITLE


async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_anime"]["title"] = update.message.text.strip()
    await update.message.reply_text("Send the *IMDB* id/link (or `-` to skip):",
                                     parse_mode="Markdown")
    return IMDB


async def get_imdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    context.user_data["new_anime"]["imdb"] = "" if val == "-" else val
    await update.message.reply_text(
        "Send the *poster* — upload a photo, or paste an image URL:",
        parse_mode="Markdown",
    )
    return POSTER


async def get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["new_anime"]["poster"] = update.message.photo[-1].file_id
    else:
        context.user_data["new_anime"]["poster"] = update.message.text.strip()
    await update.message.reply_text(
        "Send the *banner* — upload a photo, or paste an image URL:",
        parse_mode="Markdown",
    )
    return BANNER


async def get_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["new_anime"]["banner"] = update.message.photo[-1].file_id
    else:
        context.user_data["new_anime"]["banner"] = update.message.text.strip()
    await update.message.reply_text("Send the *description*:", parse_mode="Markdown")
    return DESCRIPTION


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_anime"]["description"] = update.message.text.strip()
    await update.message.reply_text("Send the *release year*:", parse_mode="Markdown")
    return YEAR


async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_anime"]["year"] = update.message.text.strip()
    data = context.user_data["new_anime"]

    anime_id = await db.create_anime(data)

    await update.message.reply_text(
        f"✅ *{data['title']}* was created and saved to MongoDB.\n"
        f"ID: `{anime_id}`\n\n"
        f"Now click /upload_episode to start uploading episodes for it.",
        parse_mode="Markdown",
    )
    context.user_data.pop("new_anime", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("new_anime", None)
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def build_create_anime_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("create_anime", create_anime_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            IMDB: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_imdb)],
            POSTER: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, get_poster)],
            BANNER: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, get_banner)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="create_anime_conversation",
    )
