"""
One-time import of your existing JSON anime database into MongoDB, using the
same schema the bot uses (see database.py docstring).

Usage:
    python migrate_json_to_mongo.py path/to/your_database.json

Expected/flexible JSON shape (a list of anime objects). Adjust the FIELD_MAP
below if your existing JSON uses different key names — no other code needs
to change.

Example input shape this script understands out of the box:
[
  {
    "title": "Naruto",
    "imdb": "tt0409591",
    "poster": "https://.../poster.jpg",
    "banner": "https://.../banner.jpg",
    "description": "...",
    "year": "2002",
    "seasons": [
      {
        "season_number": 1,
        "episodes": [
          {"episode_number": 1, "title": "Enter Naruto", "video": "https://.../ep1.mp4"}
        ]
      }
    ]
  },
  ...
]
"""
import sys
import json
import asyncio
from datetime import datetime, timezone

import database as db

# If your existing JSON uses different key names, map them here:
# old_key -> new_key (new_key must match the schema in database.py)
FIELD_MAP = {
    "name": "title",
    "imdb_id": "imdb",
    "poster_url": "poster",
    "banner_url": "banner",
    "desc": "description",
    "release_year": "year",
}


def _remap(obj: dict) -> dict:
    return {FIELD_MAP.get(k, k): v for k, v in obj.items()}


def _normalize_anime(raw: dict) -> dict:
    raw = _remap(raw)
    seasons = []
    for s in raw.get("seasons", []):
        s = _remap(s)
        episodes = []
        for e in s.get("episodes", []):
            e = _remap(e)
            episodes.append({
                "episode_number": int(e.get("episode_number", 0)),
                "title": e.get("title", ""),
                "video": e.get("video", e.get("url", "")),
                "added_at": datetime.now(timezone.utc),
            })
        seasons.append({
            "season_number": int(s.get("season_number", 1)),
            "episodes": episodes,
        })

    return {
        "title": raw.get("title", "Untitled"),
        "imdb": raw.get("imdb", ""),
        "poster": raw.get("poster", ""),
        "banner": raw.get("banner", ""),
        "description": raw.get("description", ""),
        "year": str(raw.get("year", "")),
        "created_at": datetime.now(timezone.utc),
        "seasons": seasons,
    }


async def main(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Support either a bare list, or {"animes": [...]}
    items = raw_data if isinstance(raw_data, list) else raw_data.get("animes", [])
    if not items:
        print("No anime entries found in JSON file.")
        return

    inserted = 0
    for raw in items:
        doc = _normalize_anime(raw)
        existing = await db.animes.find_one({"title": doc["title"]})
        if existing:
            print(f"Skipping (already exists): {doc['title']}")
            continue
        await db.animes.insert_one(doc)
        inserted += 1
        print(f"Imported: {doc['title']} "
              f"({len(doc['seasons'])} season(s))")

    print(f"\nDone. Imported {inserted} of {len(items)} anime into MongoDB.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python migrate_json_to_mongo.py path/to/your_database.json")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
