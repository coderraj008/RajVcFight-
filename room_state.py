from dataclasses import dataclass
import threading


@dataclass
class Room:
    chat_id: int
    muted: bool = False
    force_muted: bool = False
    admin_muted: bool = False
    admin_muted_until: float | None = None   # timestamp when admin mute expires


_rooms = {}
_play_rooms = []
_lock = threading.Lock()


def get_or_create_room(chat_id):
    with _lock:
        if chat_id not in _rooms:
            _rooms[chat_id] = Room(chat_id=chat_id)
        return _rooms[chat_id]


def get_room(chat_id):
    with _lock:
        return _rooms.get(chat_id)


def delete_room(chat_id):
    with _lock:
        _rooms.pop(chat_id, None)


def add_play_room(chat_id):
    with _lock:
        if chat_id not in _play_rooms:
            _play_rooms.append(chat_id)


def remove_play_room(chat_id):
    with _lock:
        if chat_id in _play_rooms:
            _play_rooms.remove(chat_id)


def get_play_rooms():
    with _lock:
        return list(_play_rooms)


def get_recent_play_room():
    with _lock:
        if _play_rooms:
            return _play_rooms[-1]
        return None


# ================= AUDIO SETTINGS (compatibility) =================
_audio_settings = {
    "volume": 0,
    "gain": 1.0,
    "bass": 0,
}


def set_audio_levels(volume=None, gain=None, bass=None):
    with _lock:
        if volume is not None:
            _audio_settings["volume"] = float(volume)
        if gain is not None:
            _audio_settings["gain"] = float(gain)
        if bass is not None:
            _audio_settings["bass"] = int(bass)


def get_audio_levels():
    with _lock:
        return _audio_settings.copy()


def set_manual_gain(value):
    set_audio_levels(gain=value)


def set_manual_bass(value):
    set_audio_levels(bass=value)


def get_audio_settings():
    return get_audio_levels()
