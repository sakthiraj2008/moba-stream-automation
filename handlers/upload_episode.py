"""
/upload_episode flow:

1. /upload_episode -> pick an anime (buttons, or type to search)
2. Shows season buttons for that anime + "➕ New Season"
3. Pick a season -> shows existing episodes (title + 🗑 delete each)
   with "➕ Add Episode" at the bottom
4. "➕ New Season" -> ask season number -> creates it -> shows its (empty)
   episode list
5. "➕ Add Episode" -> ask episode number -> title -> video -> saved to
   MongoDB -> episode list is refreshed so you can keep adding
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

import database as db
from utils import is_admin

(CHOOSING_ANIME, MANAGING_SEASON, ADD_SEASON_NUM,
 ADD_EP_NUM, ADD_EP_TITLE, ADD_EP_VIDEO) = range(6)


# ------------------------------------------------------------- rendering ----

async def _render_anime_list(update_or_query, text_prefix=""):
    animes = await db.list_animes(30)
    buttons = [
        [InlineKeyboardButton(a["title"], callback_data=f"anime|{a['_id']}")]
        for a in animes
    ]
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    text = (text_prefix +
            "📺 Select an anime to manage episodes for "
            "(or type part of the title to search):")
    if not buttons:
        text = text_prefix + "No anime found yet. Use /create_anime first."
    return text, markup


async def _render_season_list(anime_id: str, anime_title: str):
    seasons = await db.get_seasons(anime_id)
    rows = [
        [InlineKeyboardButton(f"Season {s}", callback_data=f"season|{s}")]
        for s in seasons
    ]
    rows.append([InlineKeyboardButton("➕ New Season", callback_data="newseason")])
    rows.append([InlineKeyboardButton("« Back to anime list", callback_data="backanime")])
    text = f"🎞 *{anime_title}*\n\nSelect a season, or add a new one:"
    return text, InlineKeyboardMarkup(rows)


async def _render_episode_list(anime_id: str, anime_title: str, season_number: int):
    episodes = await db.get_episodes(anime_id, season_number)
    rows = []
    for ep in episodes:
        rows.append([
            InlineKeyboardButton(
                f"Ep {ep['episode_number']} - {ep['title']}",
                callback_data=f"noop",
            ),
            InlineKeyboardButton(
                "🗑 Delete",
                callback_data=f"delep|{season_number}|{ep['episode_number']}",
            ),
        ])
    rows.append([InlineKeyboardButton("➕ Add Episode", callback_data="addepisode")])
    rows.append([InlineKeyboardButton("« Back to seasons", callback_data="backseasons")])
    text = f"🎞 *{anime_title}* — Season {season_number}\n\nCurrent episodes:"
    if not episodes:
        text = f"🎞 *{anime_title}* — Season {season_number}\n\nNo episodes yet."
    return text, InlineKeyboardMarkup(rows)


# ------------------------------------------------------------- entry/nav ----

async def upload_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        return ConversationHandler.END
    context.user_data["upload_ctx"] = {}
    text, markup = await _render_anime_list(update)
    await update.message.reply_text(text, reply_markup=markup)
    return CHOOSING_ANIME


async def search_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = await db.search_animes(query)
    if not results:
        await update.message.reply_text("No matches. Try again, or /cancel.")
        return CHOOSING_ANIME
    buttons = [
        [InlineKeyboardButton(a["title"], callback_data=f"anime|{a['_id']}")]
        for a in results
    ]
    await update.message.reply_text(
        "Results:", reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CHOOSING_ANIME


async def choose_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_id = query.data.split("|", 1)[1]
    anime = await db.get_anime(anime_id)
    if not anime:
        await query.edit_message_text("That anime no longer exists.")
        return ConversationHandler.END

    context.user_data["upload_ctx"] = {
        "anime_id": anime_id,
        "anime_title": anime["title"],
    }
    text, markup = await _render_season_list(anime_id, anime["title"])
    await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return MANAGING_SEASON


async def back_to_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, markup = await _render_anime_list(update)
    await query.edit_message_text(text, reply_markup=markup)
    return CHOOSING_ANIME


async def choose_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_number = int(query.data.split("|", 1)[1])
    ctx = context.user_data["upload_ctx"]
    ctx["season_number"] = season_number
    text, markup = await _render_episode_list(
        ctx["anime_id"], ctx["anime_title"], season_number
    )
    await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return MANAGING_SEASON


async def back_to_seasons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx = context.user_data["upload_ctx"]
    text, markup = await _render_season_list(ctx["anime_id"], ctx["anime_title"])
    await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return MANAGING_SEASON


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return MANAGING_SEASON


# ------------------------------------------------------------ new season ----

async def ask_new_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send the *season number* (e.g. `2`):",
                                   parse_mode="Markdown")
    return ADD_SEASON_NUM


async def save_new_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Please send a number, e.g. 2")
        return ADD_SEASON_NUM
    season_number = int(text)
    ctx = context.user_data["upload_ctx"]
    await db.ensure_season(ctx["anime_id"], season_number)
    ctx["season_number"] = season_number
    text, markup = await _render_episode_list(
        ctx["anime_id"], ctx["anime_title"], season_number
    )
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return MANAGING_SEASON


# ----------------------------------------------------------- add episode ----

async def ask_episode_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send the *episode number* (e.g. `1`):",
                                   parse_mode="Markdown")
    return ADD_EP_NUM


async def get_episode_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Please send a number, e.g. 1")
        return ADD_EP_NUM
    context.user_data["upload_ctx"]["episode_number"] = int(text)
    await update.message.reply_text("Send the *episode title*:", parse_mode="Markdown")
    return ADD_EP_TITLE


async def get_episode_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["upload_ctx"]["episode_title"] = update.message.text.strip()
    await update.message.reply_text(
        "Now send the *video* — upload a video/document, or paste a video URL:",
        parse_mode="Markdown",
    )
    return ADD_EP_VIDEO


async def get_episode_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        video_ref = update.message.video.file_id
    elif update.message.document:
        video_ref = update.message.document.file_id
    elif update.message.text:
        video_ref = update.message.text.strip()
    else:
        await update.message.reply_text("Please send a video, document, or URL.")
        return ADD_EP_VIDEO

    ctx = context.user_data["upload_ctx"]
    await db.add_episode(
        ctx["anime_id"], ctx["season_number"],
        ctx["episode_number"], ctx["episode_title"], video_ref,
    )
    await update.message.reply_text(
        f"✅ Episode {ctx['episode_number']} saved to MongoDB."
    )
    text, markup = await _render_episode_list(
        ctx["anime_id"], ctx["anime_title"], ctx["season_number"]
    )
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return MANAGING_SEASON


# --------------------------------------------------------- delete episode ---

async def delete_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleted")
    _, season_number, episode_number = query.data.split("|")
    ctx = context.user_data["upload_ctx"]
    await db.delete_episode(ctx["anime_id"], int(season_number), int(episode_number))
    text, markup = await _render_episode_list(
        ctx["anime_id"], ctx["anime_title"], int(season_number)
    )
    await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    return MANAGING_SEASON


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("upload_ctx", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_upload_episode_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("upload_episode", upload_episode_start)],
        states={
            CHOOSING_ANIME: [
                CallbackQueryHandler(choose_anime, pattern=r"^anime\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_anime),
            ],
            MANAGING_SEASON: [
                CallbackQueryHandler(choose_season, pattern=r"^season\|"),
                CallbackQueryHandler(ask_new_season, pattern=r"^newseason$"),
                CallbackQueryHandler(ask_episode_number, pattern=r"^addepisode$"),
                CallbackQueryHandler(delete_episode, pattern=r"^delep\|"),
                CallbackQueryHandler(back_to_seasons, pattern=r"^backseasons$"),
                CallbackQueryHandler(back_to_anime_list, pattern=r"^backanime$"),
                CallbackQueryHandler(noop, pattern=r"^noop$"),
            ],
            ADD_SEASON_NUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_season)
            ],
            ADD_EP_NUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_episode_number)
            ],
            ADD_EP_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_episode_title)
            ],
            ADD_EP_VIDEO: [
                MessageHandler(
                    (filters.TEXT | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND,
                    get_episode_video,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="upload_episode_conversation",
    )
