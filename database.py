"""
All MongoDB read/write operations live here.
Schema (one document per anime):

{
  _id: ObjectId,
  title: str,
  imdb: str,
  poster: str,        # telegram file_id or URL
  banner: str,         # telegram file_id or URL
  description: str,
  year: str,
  created_at: datetime,
  seasons: [
      {
        season_number: int,
        episodes: [
            { episode_number: int, title: str, video: str, added_at: datetime }
        ]
      },
      ...
  ]
}
"""
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, MONGO_DB_NAME

_client = AsyncIOMotorClient(MONGO_URI)
db = _client[MONGO_DB_NAME]
animes = db["animes"]


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- animes ----

async def create_anime(data: dict) -> str:
    """Insert a new anime document. Returns the new anime's id as a string."""
    doc = {
        "title": data["title"],
        "imdb": data.get("imdb", ""),
        "poster": data.get("poster", ""),
        "banner": data.get("banner", ""),
        "description": data.get("description", ""),
        "year": data.get("year", ""),
        "created_at": _now(),
        "seasons": [],
    }
    result = await animes.insert_one(doc)
    return str(result.inserted_id)


async def list_animes(limit: int = 50) -> list:
    cursor = animes.find({}, {"title": 1}).sort("created_at", -1).limit(limit)
    return [doc async for doc in cursor]


async def search_animes(query: str, limit: int = 20) -> list:
    cursor = animes.find(
        {"title": {"$regex": query, "$options": "i"}}, {"title": 1}
    ).limit(limit)
    return [doc async for doc in cursor]


async def get_anime(anime_id: str) -> dict | None:
    return await animes.find_one({"_id": ObjectId(anime_id)})


async def delete_anime(anime_id: str) -> None:
    await animes.delete_one({"_id": ObjectId(anime_id)})


# --------------------------------------------------------------- seasons ----

async def get_seasons(anime_id: str) -> list:
    doc = await animes.find_one(
        {"_id": ObjectId(anime_id)}, {"seasons.season_number": 1}
    )
    if not doc:
        return []
    return sorted(s["season_number"] for s in doc.get("seasons", []))


async def ensure_season(anime_id: str, season_number: int) -> None:
    """Create the season sub-document if it doesn't already exist (idempotent)."""
    result = await animes.update_one(
        {"_id": ObjectId(anime_id), "seasons.season_number": season_number},
        {"$set": {"seasons.$.season_number": season_number}},
    )
    if result.matched_count == 0:
        await animes.update_one(
            {"_id": ObjectId(anime_id)},
            {"$push": {"seasons": {"season_number": season_number, "episodes": []}}},
        )


# -------------------------------------------------------------- episodes ----

async def get_episodes(anime_id: str, season_number: int) -> list:
    doc = await animes.find_one(
        {"_id": ObjectId(anime_id), "seasons.season_number": season_number},
        {"seasons.$": 1},
    )
    if not doc or not doc.get("seasons"):
        return []
    eps = doc["seasons"][0].get("episodes", [])
    return sorted(eps, key=lambda e: e["episode_number"])


async def add_episode(anime_id: str, season_number: int, episode_number: int,
                       title: str, video: str) -> None:
    await ensure_season(anime_id, season_number)

    # Replace episode if the same episode_number already exists (upsert-style),
    # otherwise push a new one.
    pull_result = await animes.update_one(
        {"_id": ObjectId(anime_id), "seasons.season_number": season_number},
        {"$pull": {"seasons.$.episodes": {"episode_number": episode_number}}},
    )
    await animes.update_one(
        {"_id": ObjectId(anime_id), "seasons.season_number": season_number},
        {
            "$push": {
                "seasons.$.episodes": {
                    "episode_number": episode_number,
                    "title": title,
                    "video": video,
                    "added_at": _now(),
                }
            }
        },
    )
    _ = pull_result  # kept for clarity/debugging


async def delete_episode(anime_id: str, season_number: int, episode_number: int) -> None:
    await animes.update_one(
        {"_id": ObjectId(anime_id), "seasons.season_number": season_number},
        {"$pull": {"seasons.$.episodes": {"episode_number": episode_number}}},
    )
