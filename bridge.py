import asyncio
import logging
import time

from pytgcalls import filters as call_filters
from pytgcalls.types import (
    ChatUpdate,
    Device,
    Direction,
    ExternalMedia,
    GroupCallConfig,
    MediaStream,
    RecordStream,
    StreamEnded,
    StreamFrames,
    UpdatedGroupCallParticipant,
)
from pytgcalls.types.raw import AudioParameters

from clients import call
from config import (
    AUDIO_BITRATE,
    AUDIO_CHANNELS,
    LOGGER_ID,
)
from db import (
    set_control_vc,
    set_recorder_joined,
)
from room_state import (
    add_play_room,
    delete_room,
    get_or_create_room,
    get_play_rooms,
    get_recent_play_room,
    get_room,
    remove_play_room,
)
from audio import process_audio

logger = logging.getLogger(__name__)

AUDIO_PARAMS = AudioParameters(
    bitrate=AUDIO_BITRATE,
    channels=AUDIO_CHANNELS,
)

VC_LOCK = asyncio.Lock()

AUTO_MUTE = False
SILENCE_TIMEOUT = 1.0  # seconds of silence before auto‑mute
_last_audio_time = {}   # chat_id -> timestamp of last audio received from record VC

def set_automute(state: bool):
    global AUTO_MUTE
    AUTO_MUTE = state

def get_automute():
    return AUTO_MUTE

# ---------- Status resolution ----------
_MUTE_STATUS_STRINGS = ("MUTED_CALL", "MUTED")
_UNMUTE_STATUS_STRINGS = ("UNMUTED_CALL", "UNMUTED")

def _resolve_statuses(status_strings):
    found = []
    for name in status_strings:
        status = getattr(ChatUpdate.Status, name, None)
        if status is not None:
            found.append(status)
    return tuple(found)

MUTE_STATUSES = _resolve_statuses(_MUTE_STATUS_STRINGS)
UNMUTE_STATUSES = _resolve_statuses(_UNMUTE_STATUS_STRINGS)

def _build_all_status_flags():
    flags = None
    for name in dir(ChatUpdate.Status):
        if name.startswith("_"):
            continue
        value = getattr(ChatUpdate.Status, name)
        if not isinstance(value, type(ChatUpdate.Status.LEFT_CALL)):
            continue
        flags = value if flags is None else (flags | value)
    return flags

ALL_CHAT_UPDATE_FLAGS = _build_all_status_flags()

# ---------- Core functions ----------
async def join_record_vc():
    try:
        if get_room(LOGGER_ID):
            return True
        get_or_create_room(LOGGER_ID)
        await call.record(LOGGER_ID, RecordStream(True, AUDIO_PARAMS))
        await asyncio.sleep(2)
        await set_recorder_joined(True)
        logger.info("Recorder VC joined successfully.")
        return True
    except Exception as e:
        logger.error("record join error: %s", e)
        return False

async def join_play_vc(chat_id: int):
    try:
        async with VC_LOCK:
            get_or_create_room(chat_id)
            await call.play(
                chat_id,
                MediaStream(ExternalMedia.AUDIO, AUDIO_PARAMS),
                config=GroupCallConfig(auto_start=True),
            )
            await asyncio.sleep(3)
            add_play_room(chat_id)
        await set_control_vc(chat_id)
        if AUTO_MUTE:
            await mute_vc(chat_id)
        logger.info("Joined play VC %s", chat_id)
        return True
    except Exception as e:
        logger.error("play join error %s: %s", chat_id, e)
        return False

async def leave_record_vc():
    try:
        await call.leave_call(LOGGER_ID)
    except:
        pass
    delete_room(LOGGER_ID)
    await set_recorder_joined(False)

async def leave_play_vc(chat_id):
    try:
        await call.leave_call(chat_id)
    except:
        pass
    delete_room(chat_id)
    remove_play_room(chat_id)
    recent = get_recent_play_room()
    await set_control_vc(recent if recent else None)

async def leave_recent_play_vc():
    cid = get_recent_play_room()
    if cid:
        await leave_play_vc(cid)

async def leave_all_vcs():
    await leave_record_vc()
    for cid in list(get_play_rooms()):
        await leave_play_vc(cid)
    await set_control_vc(None)

# ---------- Mute / Unmute API ----------
async def mute_vc(chat_id):
    try:
        await call.mute(chat_id)
        room = get_room(chat_id)
        if room:
            room.muted = True
            room.force_muted = True   # permanent until unmute command
            room.silence_muted = False
        return True
    except Exception as e:
        logger.error("mute error %s: %s", chat_id, e)
        return False

async def unmute_vc(chat_id, clear_force=True):
    try:
        room = get_room(chat_id)
        if room and getattr(room, "force_muted", False) and not clear_force:
            logger.info("unmute blocked for %s: force_muted is set", chat_id)
            return False
        await call.unmute(chat_id)
        if room:
            room.muted = False
            if clear_force:
                room.force_muted = False
                room.silence_muted = False
        return True
    except Exception as e:
        logger.error("unmute error %s: %s", chat_id, e)
        return False

# ---------- Watchdog for admin/force mute ----------
async def _is_self_unmuted(chat_id):
    try:
        participants = await call.get_participants(chat_id)
    except Exception as e:
        logger.warning("watchdog: participants fetch failed %s: %s", chat_id, e)
        return None
    for p in participants:
        if getattr(p, "is_self", False):
            return not getattr(p, "muted", False)
    return None

async def mute_watchdog():
    logger.info("Mute watchdog started (checking every 1 sec)")
    while True:
        await asyncio.sleep(1)
        for chat_id in list(get_play_rooms()):
            room = get_room(chat_id)
            if not room:
                continue
            state = await _is_self_unmuted(chat_id)
            if state is None:
                continue
            # If force_muted is True, we must keep the bot muted
            if room.force_muted:
                if state:  # bot is unmuted → re‑mute
                    try:
                        await call.mute(chat_id)
                        room.muted = True
                        logger.info(f"Watchdog re‑muted {chat_id}")
                    except Exception as e:
                        logger.warning(f"Re‑mute failed {chat_id}: {e}")
                # else stay muted
            else:
                # Normal sync: if not force_muted, update room.muted based on actual state
                room.muted = not state

# ---------- Silence watchdog ----------
async def silence_watchdog():
    logger.info("Silence watchdog started (checking every 1 sec)")
    while True:
        await asyncio.sleep(1)
        now = time.time()
        for chat_id in list(get_play_rooms()):
            room = get_room(chat_id)
            if not room:
                continue
            # Do not silence if force_muted is True (admin/command mute)
            if room.force_muted:
                continue
            last_time = _last_audio_time.get(chat_id, 0)
            if now - last_time > SILENCE_TIMEOUT:
                # No audio for timeout → mute if not already muted
                if not room.muted:
                    try:
                        await call.mute(chat_id)
                        room.muted = True
                        room.silence_muted = True
                        logger.info(f"🔇 Auto-muted {chat_id} due to silence")
                    except Exception as e:
                        logger.warning(f"Auto-mute failed {chat_id}: {e}")

# ---------- Audio forwarding + auto‑unmute on audio ----------
@call.on_update(call_filters.stream_frame(Direction.INCOMING, Device.MICROPHONE))
async def on_audio_frame(_, update: StreamFrames):
    if update.chat_id != LOGGER_ID:
        return
    if not update.frames:
        return

    # Update last audio time for all play VCs
    now = time.time()
    for chat_id in list(get_play_rooms()):
        _last_audio_time[chat_id] = now

    raw_frames = [f.frame for f in update.frames]
    processed = process_audio(raw_frames)

    for chat_id in list(get_play_rooms()):
        if chat_id == LOGGER_ID:
            continue
        room = get_room(chat_id)
        if not room:
            continue

        # If force_muted is True (admin or command mute), we keep muted and skip
        if room.force_muted:
            try:
                await call.mute(chat_id)
                room.muted = True
                room.silence_muted = False
            except:
                pass
            continue

        # If we are muted (by silence), auto‑unmute because we have audio
        if room.muted:
            try:
                await call.unmute(chat_id)
                room.muted = False
                room.silence_muted = False
                logger.info(f"🔊 Auto-unmuted {chat_id} due to audio")
            except Exception as e:
                logger.warning(f"Auto-unmute failed {chat_id}: {e}")
                # If unmute fails, skip sending
                continue

        # Now send audio frame
        try:
            await call.send_frame(chat_id, Device.MICROPHONE, processed)
        except Exception as e:
            if "not in a call" in str(e).lower():
                remove_play_room(chat_id)
                delete_room(chat_id)
                continue
            logger.warning("send frame error %s: %s", chat_id, e)

# ---------- Stream end / VC closed ----------
@call.on_update(call_filters.stream_end())
async def on_stream_end(_, update: StreamEnded):
    cid = update.chat_id
    delete_room(cid)
    remove_play_room(cid)
    _last_audio_time.pop(cid, None)
    logger.info("Stream ended for chat: %s", cid)

@call.on_update(
    call_filters.chat_update(
        ChatUpdate.Status.LEFT_CALL
        | ChatUpdate.Status.KICKED
        | ChatUpdate.Status.CLOSED_VOICE_CHAT
    )
)
async def on_vc_closed(_, update: ChatUpdate):
    cid = update.chat_id
    delete_room(cid)
    remove_play_room(cid)
    _last_audio_time.pop(cid, None)
    logger.info("Voice chat closed or bot kicked from: %s", cid)

# ---------- Admin mute/unmute handlers ----------
@call.on_update(call_filters.chat_update(ALL_CHAT_UPDATE_FLAGS))
async def on_chat_update(_, update: ChatUpdate):
    cid = update.chat_id
    room = get_room(cid)
    if not room:
        return
    status = update.status
    logger.debug("Chat update in %s: status=%s", cid, status)

    if status in MUTE_STATUSES:
        room.force_muted = True
        room.muted = True
        room.silence_muted = False
        try:
            await call.mute(cid)
        except:
            pass
        logger.info(f"Admin muted {cid} -> force_muted=True")
        return

    if status in UNMUTE_STATUSES:
        if room.force_muted:
            # Block unmute – re-mute immediately
            try:
                await call.mute(cid)
                room.muted = True
                room.force_muted = True
                logger.info(f"Blocked admin unmute for {cid}")
            except Exception as e:
                logger.warning(f"Re‑mute failed {cid}: {e}")
        else:
            room.muted = False
            room.silence_muted = False

@call.on_update()
async def on_participant_update(_, update):
    if not isinstance(update, UpdatedGroupCallParticipant):
        return

    chat_id = update.chat_id
    if chat_id not in get_play_rooms():
        return

    participant = update.participant
    try:
        self_user_id = await call.get_self_user_id()
    except:
        return
    if participant.user_id != self_user_id:
        return

    room = get_room(chat_id)
    if not room:
        return

    muted_by_admin = getattr(participant, 'muted_by_admin', False)

    if muted_by_admin:
        room.force_muted = True
        room.muted = True
        room.silence_muted = False
        try:
            await call.mute(chat_id)
        except:
            pass
        logger.info(f"🔇 Admin muted bot in {chat_id} (participant update)")
    else:
        if room.force_muted:
            # Block unmute
            try:
                await call.mute(chat_id)
                room.muted = True
                room.force_muted = True
                logger.info(f"⛔ Admin unmute blocked in {chat_id}")
            except Exception as e:
                logger.warning(f"Re‑mute failed {chat_id}: {e}")
        else:
            room.muted = False
            room.silence_muted = False

# ---------- Dependency check ----------
def assert_media_runtime_dependencies():
    try:
        import numpy
        import pytgcalls
    except Exception as e:
        raise RuntimeError(f"Missing dependency: {e}")
    return True
