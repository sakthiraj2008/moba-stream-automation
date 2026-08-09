"""
Main entry point. Run with:  python bot.py

Includes a tiny background HTTP server that just returns 200 OK. This is
only needed if you're deploying to a platform (like Koyeb's free tier) that
requires services to be "Web" type and bind to a port — it lets the bot run
as a Web Service even though it doesn't actually need to serve anything.
If your host supports a real Worker/background-service type, you can ignore
this and it's harmless either way.
"""
import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import BOT_TOKEN
from handlers.create_anime import build_create_anime_handler
from handlers.upload_episode import build_upload_episode_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Anime bot is running.")

    def log_message(self, format, *args):
        pass  # silence per-request logging


def _start_health_server():
    port = int(os.getenv("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info(f"Health check server listening on port {port}")
    server.serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Anime DB manager bot.\n\n"
        "/create_anime — add a new anime to MongoDB\n"
        "/upload_episode — manage seasons/episodes for an existing anime\n"
        "/cancel — cancel whatever you're doing"
    )


def main():
    # Health-check server runs in a background thread so Koyeb (or any
    # platform expecting a Web service bound to $PORT) sees the service as
    # up, while the bot itself talks to Telegram via polling.
    threading.Thread(target=_start_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(build_create_anime_handler())
    app.add_handler(build_upload_episode_handler())

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
