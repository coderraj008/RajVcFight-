import numpy as np
from audio_engine import get_audio_levels, VOLUME_LEVELS, BASS_LEVELS, TREBLE_LEVELS
from room_state import get_room, get_recent_play_room

def make_silent_frame(size=3840):
    return np.zeros(size // 2, dtype=np.int16).tobytes()

def process_audio(raw_frames):
    if not raw_frames:
        return b""

    active_chat = get_recent_play_room()
    room = get_room(active_chat) if active_chat else None
    if room and room.muted:
        return make_silent_frame(len(raw_frames[0]))

    frame_len = len(raw_frames[0]) // 2
    mixed = np.zeros(frame_len, dtype=np.float32)

    for frame in raw_frames:
        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        min_len = min(frame_len, len(samples))
        mixed[:min_len] += samples[:min_len]

    # Get levels
    levels = get_audio_levels()
    volume_mult = levels["volume_multiplier"]
    bass_blend = levels["bass_blend"]
    treble_blend = levels["treble_blend"]

    # Bass boost (IIR low-pass)
    if bass_blend > 0:
        lp_alpha = 0.85
        lp_filtered = np.zeros_like(mixed)
        prev_lp = 0.0
        for i in range(len(mixed)):
            lp_filtered[i] = lp_alpha * prev_lp + (1.0 - lp_alpha) * mixed[i]
            prev_lp = lp_filtered[i]
        mixed = mixed + bass_blend * lp_filtered

    # Treble boost (IIR high-pass)
    if treble_blend > 0:
        hp_alpha = 0.9
        hp_filtered = np.zeros_like(mixed)
        prev_in = 0.0
        prev_out = 0.0
        for i in range(len(mixed)):
            curr = mixed[i]
            hp_filtered[i] = hp_alpha * (prev_out + curr - prev_in)
            prev_in = curr
            prev_out = hp_filtered[i]
        mixed = mixed + treble_blend * hp_filtered

    # Volume scaling and saturation
    mixed = np.tanh(mixed / 32768.0 * volume_mult) * 32767.0

    mixed = np.clip(mixed, -32767, 32767)
    return mixed.astype(np.int16).tobytes()
