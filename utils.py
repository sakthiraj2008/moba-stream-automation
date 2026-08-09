from telegram import Update
from config import ADMIN_IDS


async def is_admin(update: Update) -> bool:
    """Restrict database-changing commands to configured admin user IDs.
    If ADMIN_IDS is empty, everyone is allowed (useful for local testing) —
    but you should set ADMIN_IDS in production.
    """
    if not ADMIN_IDS:
        return True
    user = update.effective_user
    if user and user.id in ADMIN_IDS:
        return True
    if update.effective_message:
        await update.effective_message.reply_text(
            "⛔ You're not authorized to manage this database."
        )
    elif update.callback_query:
        await update.callback_query.answer("⛔ Not authorized.", show_alert=True)
    return False
