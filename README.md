# Anime DB Telegram Bot

Manage your anime streaming site's database (stored in MongoDB) entirely
through a Telegram bot.

## Features

- `/create_anime` — asks for title, IMDB, poster, banner, description, year,
  then saves it to MongoDB and tells you to run `/upload_episode` next.
- `/upload_episode` —
  1. pick an anime (tap a button, or type to search)
  2. see its seasons, or tap **➕ New Season** to add one (e.g. Season 2)
  3. see that season's episodes (`Ep 1 - Title` with a **🗑 Delete** button
     next to each), plus an **➕ Add Episode** button
  4. adding an episode asks episode number → title → video (upload a
     video/file, or paste a URL) and saves straight to MongoDB
- Every create/upload/delete action writes to MongoDB immediately.
- `migrate_json_to_mongo.py` — one-time importer for your existing JSON
  database.

## 1. Install

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
- `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `MONGO_URI` — local MongoDB (`mongodb://localhost:27017`) or an Atlas
  connection string
- `ADMIN_IDS` — your Telegram numeric user ID(s), comma separated, so only
  you can manage the database. Get your ID from [@userinfobot](https://t.me/userinfobot).
  Leave blank while testing to allow anyone.

## 3. Import your existing JSON database (optional, one-time)

```bash
python migrate_json_to_mongo.py path/to/your_database.json
```

If your JSON uses different field names than `title/imdb/poster/banner/
description/year/seasons/episodes`, edit the `FIELD_MAP` dictionary near the
top of `migrate_json_to_mongo.py` — map your key names to the ones on the
right, no other code needs to change.

## 4. Run the bot

```bash
python bot.py
```

Message your bot on Telegram:
- `/create_anime` to add a new title
- `/upload_episode` to upload episodes for it
- `/cancel` at any point to abort what you're doing

## Data model (MongoDB `animes` collection)

```jsonc
{
  "_id": "...",
  "title": "Naruto",
  "imdb": "tt0409591",
  "poster": "<telegram file_id or URL>",
  "banner": "<telegram file_id or URL>",
  "description": "...",
  "year": "2002",
  "created_at": "2026-08-09T00:00:00Z",
  "seasons": [
    {
      "season_number": 1,
      "episodes": [
        {
          "episode_number": 1,
          "title": "Enter Naruto",
          "video": "<telegram file_id, or URL>",
          "added_at": "2026-08-09T00:00:00Z"
        }
      ]
    }
  ]
}
```

The bot stores videos as Telegram `file_id`s when you upload the file
directly to the bot (fast, free, served by Telegram's CDN) or as a plain
URL if you paste a link instead — your site's backend can read whichever
one it finds in the `video` field.

## Deploying on Koyeb

Koyeb's **free Instance can't run Worker services** — Workers require a paid
Eco instance or higher (~$1.61+/mo). If you're on the free tier, deploy the
bot as a **Web Service** instead: `bot.py` already includes a tiny built-in
HTTP server that answers on `$PORT`, purely so Koyeb's Web Service health
check has something to talk to. The actual bot still works the same way,
polling Telegram in the background.

**MongoDB:** Koyeb doesn't host MongoDB itself — use
[MongoDB Atlas](https://www.mongodb.com/atlas) (free tier is fine) and put
its connection string in `MONGO_URI`.

### Free tier (Web Service)

Via the dashboard:
1. Push this project to a GitHub repo (the included `Dockerfile` is
   detected automatically).
2. In Koyeb: **Create App → Create Service → GitHub** → select the repo.
3. Leave **Service type = Web**. Under **Port**, set it to `8000` (matches
   the default in `bot.py`) — or set an env var `PORT` to whatever you
   prefer.
4. Under **Environment variables**, add `BOT_TOKEN`, `MONGO_URI`,
   `MONGO_DB_NAME`, `ADMIN_IDS` (mark `BOT_TOKEN`/`MONGO_URI` as secrets).
5. Deploy.

Or via CLI:
```bash
koyeb deploy . anime-bot/bot --archive-builder docker --ports 8000:http \
  --env BOT_TOKEN=<your_token> \
  --env MONGO_URI=<your_atlas_uri> \
  --env MONGO_DB_NAME=anime_streaming \
  --env ADMIN_IDS=<your_telegram_id>
```

**Free-tier caveat:** the free Instance scales to zero after 1 hour with no
incoming HTTP traffic. Since this bot doesn't receive external requests
(only Telegram polling, which is outbound), it may go to sleep and Telegram
messages will stop being processed until it wakes back up. To keep it
always on, either:
- ping the app's public URL every ~30–50 minutes with a free scheduler
  (e.g. cron-job.org, UptimeRobot, or Runhooks), or
- upgrade to an **Eco instance** (from about $1.61/mo) and deploy as a real
  **Worker** service instead — no health-check hack needed, and it never
  sleeps due to lack of traffic:
  ```bash
  koyeb deploy . anime-bot/bot --type worker --archive-builder docker \
    --instance-type eco-nano \
    --env BOT_TOKEN=<your_token> \
    --env MONGO_URI=<your_atlas_uri> \
    --env MONGO_DB_NAME=anime_streaming \
    --env ADMIN_IDS=<your_telegram_id>
  ```

## Notes

- Uses `python-telegram-bot` v21 (async) + `motor` (async MongoDB driver).
- Deleting an episode only removes it from the `episodes` array — the
  season and anime documents stay intact.
- To wipe an anime entirely, call `database.delete_anime(anime_id)` (not
  wired to a command by default — add one if you want it in-bot).
