"""
Dual-Tone Multi-Frequency (DTMF) Audio Generator
================================================
Generates standard acoustic telephone touch-tones for telephony dialing,
provider ID submission (#), and IVR menu interactions.
"""

from typing import Dict, Tuple
import numpy as np


# Standard ITU-T Q.23 DTMF Frequencies (Hz)
DTMF_FREQUENCIES: Dict[str, Tuple[int, int]] = {
    '1': (697, 1209),
    '2': (697, 1336),
    '3': (697, 1477),
    '4': (770, 1209),
    '5': (770, 1336),
    '6': (770, 1477),
    '7': (852, 1209),
    '8': (852, 1336),
    '9': (852, 1477),
    '*': (941, 1209),
    '0': (941, 1336),
    '#': (941, 1477),
    'A': (697, 1633),
    'B': (770, 1633),
    'C': (852, 1633),
    'D': (941, 1633),
}


def generate_dtmf_tone(
    digit: str,
    duration_sec: float = 0.12,
    sample_rate: int = 24000,
    amplitude: float = 0.45
) -> np.ndarray:
    """
    Generates a numpy float32 audio waveform for a single DTMF digit.
    Applies a 5ms cosine fade envelope to prevent audible clicks.
    """
    char = str(digit).strip().upper()
    if char not in DTMF_FREQUENCIES:
        # Return silence if invalid character
        num_samples = int(duration_sec * sample_rate)
        return np.zeros(num_samples, dtype=np.float32)

    f_low, f_high = DTMF_FREQUENCIES[char]
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)

    # Standard DTMF: sum of low and high frequency sinusoids
    tone = 0.5 * (np.sin(2.0 * np.pi * f_low * t) + np.sin(2.0 * np.pi * f_high * t))

    # Apply 5ms attack/decay envelope to eliminate pops
    fade_len = min(int(0.005 * sample_rate), num_samples // 4)
    if fade_len > 0:
        envelope = np.ones(num_samples, dtype=np.float32)
        fade_curve = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_len)))
        envelope[:fade_len] = fade_curve
        envelope[-fade_len:] = fade_curve[::-1]
        tone = tone * envelope

    return (tone * amplitude).astype(np.float32)


def generate_dtmf_sequence(
    sequence: str,
    tone_duration: float = 0.12,
    pause_duration: float = 0.08,
    sample_rate: int = 24000
) -> np.ndarray:
    """
    Generates a full audio stream containing a sequence of DTMF touch-tones
    interleaved with short pauses.
    """
    chunks = []
    pause = np.zeros(int(pause_duration * sample_rate), dtype=np.float32)

    for char in sequence:
        if char in DTMF_FREQUENCIES:
            tone = generate_dtmf_tone(char, duration_sec=tone_duration, sample_rate=sample_rate)
            chunks.append(tone)
            chunks.append(pause)
        elif char in (' ', '-', ','):
            # Extra pause for delimiter
            chunks.append(pause)

    if not chunks:
        return np.zeros(0, dtype=np.float32)

    return np.concatenate(chunks).astype(np.float32)
