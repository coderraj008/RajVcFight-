# Volume levels (multipliers)
VOLUME_LEVELS = {
     1:    1.0,  2:    1.5,  3:    2.0,  4:    3.0,  5:    4.0,
     6:    5.0,  7:   10.0,  8:   15.0,  9:   20.0, 10:   30.0,
    11:   50.0, 12:  100.0, 13:  150.0, 14:  200.0, 15:  300.0,
    16:  400.0, 17:  500.0, 18:  750.0, 19: 1000.0, 20: 1500.0,
    21: 2000.0, 22: 2500.0, 23: 3000.0, 24: 4000.0, 25: 5000.0,
    26: 6000.0, 27: 7000.0, 28: 8000.0, 29: 9000.0, 30:10000.0,
    31:12000.0, 32:14000.0, 33:16000.0, 34:18000.0, 35:20000.0,
    36:25000.0, 37:30000.0, 38:35000.0, 39:40000.0, 40:50000.0,
    41: 60000.0, 42: 75000.0, 43: 90000.0, 44:110000.0, 45:130000.0,
    46:160000.0, 47:200000.0, 48:250000.0, 49:350000.0, 50:500000.0,
}

BASS_LEVELS = {
     0: 0.0,  1: 0.1,  2: 0.2,  3: 0.3,  4: 0.4,
     5: 0.5,  6: 0.6,  7: 0.7,  8: 0.8,  9: 0.9,
    10: 1.0, 11: 1.1, 12: 1.2, 13: 1.3, 14: 1.4, 15: 1.5,
}

TREBLE_LEVELS = {
     0: 0.0,  1: 0.1,  2: 0.2,  3: 0.3,  4: 0.4,
     5: 0.5,  6: 0.6,  7: 0.7,  8: 0.8,  9: 0.9,
    10: 1.0, 11: 1.1, 12: 1.2, 13: 1.3, 14: 1.4, 15: 1.5,
}

_volume_level = 10    # default 30x
_bass_level = 0
_treble_level = 5     # 0.5 blend
_voice_mode = "female"

def set_volume_level(level: int):
    global _volume_level
    _volume_level = max(1, min(50, int(level)))

def get_volume_level():
    return _volume_level

def set_bass_level(level: int):
    global _bass_level
    _bass_level = max(0, min(15, int(level)))

def get_bass_level():
    return _bass_level

def set_treble_level(level: int):
    global _treble_level
    _treble_level = max(0, min(15, int(level)))

def get_treble_level():
    return _treble_level

def set_voice_mode(mode: str):
    global _voice_mode, _volume_level, _bass_level, _treble_level
    mode = mode.lower()
    if mode == "female":
        _volume_level = 15   # 300x
        _bass_level = 0
        _treble_level = 10   # 1.0
        _voice_mode = "female"
    elif mode == "male":
        _volume_level = 20   # 1500x
        _bass_level = 10     # 1.0
        _treble_level = 3    # 0.3
        _voice_mode = "male"
    else:  # normal
        _volume_level = 10   # 30x
        _bass_level = 3      # 0.3
        _treble_level = 5    # 0.5
        _voice_mode = "normal"

def get_voice_mode():
    return _voice_mode

def get_audio_levels():
    return {
        "volume_level": _volume_level,
        "bass_level": _bass_level,
        "treble_level": _treble_level,
        "voice_mode": _voice_mode,
        "volume_multiplier": VOLUME_LEVELS.get(_volume_level, 1.0),
        "bass_blend": BASS_LEVELS.get(_bass_level, 0.0),
        "treble_blend": TREBLE_LEVELS.get(_treble_level, 0.0),
    }

# ---------- backward compatibility for old commands ----------
def set_volume(value):
    # map 0-400 to 1-50
    level = int(max(1, min(50, round(value / 400 * 50))))
    set_volume_level(level)

def get_volume():
    return get_volume_level()

def set_gain(value):
    # gain maps to volume level (treat as extra boost)
    # we'll just ignore gain and set volume level based on value? 
    # Better: ignore gain or map to volume. We'll ignore gain.
    pass

def get_gain():
    return 0

def set_bass(value):
    # map 0-100 to 0-15
    level = int(max(0, min(15, round(value / 100 * 15))))
    set_bass_level(level)

def get_bass():
    return get_bass_level()

def set_treble(value):
    level = int(max(0, min(15, round(value / 100 * 15))))
    set_treble_level(level)

def get_treble():
    return get_treble_level()
