from __future__ import annotations

from typing import Any

from pymongo.asynchronous.mongo_client import AsyncMongoClient

from config import MONGO_URI, MONGO_DB_NAME, OWNER_ID, LOGGER_ID


# ================= MONGO =================
_client = AsyncMongoClient(MONGO_URI)
_db = _client[MONGO_DB_NAME]

_state = _db["bridge_state"]
_sudoers = _db["sudoers"]


# ================= STATE =================

async def get_or_init_state() -> dict[str, Any]:
    doc = await _state.find_one({"_id": "global"})
    if doc:
        return doc

    default = {
        "_id": "global",
        "recorder_joined": False,
        "control_vc": None,
        "level": 0,
        "bass": 0,
    }

    await _state.replace_one({"_id": "global"}, default, upsert=True)
    return default


async def get_startup_state() -> dict[str, Any]:
    doc = await get_or_init_state()

    control = doc.get("control_vc")

    return {
        "recorder_joined": bool(doc.get("recorder_joined", False)),
        "control_vc": int(control) if control is not None else None,
        "level": int(doc.get("level", 0)),
        "bass": int(doc.get("bass", 0)),
    }


async def set_recorder_joined(joined: bool) -> None:
    await _state.update_one(
        {"_id": "global"},
        {"$set": {"recorder_joined": bool(joined)}},
        upsert=True,
    )


async def set_control_vc(chat_id: int | None) -> None:
    await _state.update_one(
        {"_id": "global"},
        {"$set": {"control_vc": int(chat_id) if chat_id else None}},
        upsert=True,
    )


async def set_audio_levels(
    level: int | None = None,
    bass: int | None = None,
) -> None:

    update = {}

    if level is not None:
        update["level"] = max(
            0,
            min(int(level), 200)
        )

    if bass is not None:
        update["bass"] = max(
            0,
            min(int(bass), 50)
        )

    if update:

        await _state.update_one(
            {"_id": "global"},
            {"$set": update},
            upsert=True,
        )

# ================= SUDO SYSTEM =================

async def add_sudoer(user_id: int) -> bool:
    user_id = int(user_id)

    if user_id in (OWNER_ID, LOGGER_ID):
        return False

    await _sudoers.update_one(
        {"_id": user_id},
        {"$set": {"_id": user_id}},
        upsert=True,
    )
    return True


async def del_sudoer(user_id: int) -> bool:
    user_id = int(user_id)

    if user_id == OWNER_ID:
        return False

    res = await _sudoers.delete_one({"_id": user_id})
    return res.deleted_count > 0


async def get_sudoers() -> list[int]:
    docs = await _sudoers.find({}, {"_id": 1}).sort("_id", 1).to_list(length=None)
    return [int(d["_id"]) for d in docs]


async def is_sudoer(user_id: int) -> bool:
    user_id = int(user_id)

    if user_id == OWNER_ID:
        return True

    return await _sudoers.count_documents({"_id": user_id}) > 0
