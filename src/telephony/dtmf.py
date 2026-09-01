"""
ITU-T Q.23 Dual-Tone Multi-Frequency (DTMF) Generator & IVR Traversal
=====================================================================
Generates standard telephony DTMF audio waveforms (frequencies 697-1633 Hz)
for automated IVR navigation on hospital dictation phone lines.
"""

from typing import List, Tuple, Union, Optional
import numpy as np
import soundfile as sf
from pathlib import Path


# Standard ITU-T Q.23 DTMF Frequencies (Hz)
DTMF_FREQUENCIES = {
    '1': (697, 1209),
    '2': (697, 1336),
    '3': (697, 1477),
    'A': (697, 1633),
    '4': (770, 1209),
    '5': (770, 1336),
    '6': (770, 1477),
    'B': (770, 1633),
    '7': (852, 1209),
    '8': (852, 1336),
    '9': (852, 1477),
    'C': (852, 1633),
    '*': (941, 1209),
    '0': (941, 1336),
    '#': (941, 1477),
    'D': (941, 1633),
}


class DTMFGenerator:
    """
    Generates standard DTMF audio waveforms and IVR dialing sequences.
    """

    def __init__(
        self,
        sample_rate: int = 8000,
        tone_duration: float = 0.15,   # 150ms tone burst
        pause_duration: float = 0.10,  # 100ms inter-digit silence
    ):
        self.sample_rate = sample_rate
        self.tone_duration = tone_duration
        self.pause_duration = pause_duration

    def generate_single_digit(self, digit: str) -> np.ndarray:
        """Generates audio array for a single DTMF digit."""
        digit_char = digit.upper()
        if digit_char not in DTMF_FREQUENCIES:
            # Return silence for unrecognized characters
            num_samples = int(self.sample_rate * self.tone_duration)
            return np.zeros(num_samples, dtype=np.float32)

        f_low, f_high = DTMF_FREQUENCIES[digit_char]
        num_samples = int(self.sample_rate * self.tone_duration)
        t = np.linspace(0, self.tone_duration, num_samples, endpoint=False)

        # Dual tone sum with gentle 5ms raised cosine window to prevent clicking
        tone = 0.5 * (np.sin(2 * np.pi * f_low * t) + np.sin(2 * np.pi * f_high * t))
        
        # Apply 5ms attack/decay envelope
        fade_samples = int(self.sample_rate * 0.005)
        if fade_samples > 0 and len(tone) > 2 * fade_samples:
            window = np.ones_like(tone)
            fade_in = np.sin(np.linspace(0, np.pi / 2, fade_samples)) ** 2
            fade_out = np.cos(np.linspace(0, np.pi / 2, fade_samples)) ** 2
            window[:fade_samples] = fade_in
            window[-fade_samples:] = fade_out
            tone = tone * window

        return tone.astype(np.float32)

    def generate_digit_sequence(self, digits: str) -> np.ndarray:
        """Generates full DTMF audio sequence with inter-digit pauses."""
        chunks = []
        pause_samples = int(self.sample_rate * self.pause_duration)
        pause_chunk = np.zeros(pause_samples, dtype=np.float32)

        for i, char in enumerate(digits):
            if char.upper() in DTMF_FREQUENCIES:
                tone = self.generate_single_digit(char)
                chunks.append(tone)
                if i < len(digits) - 1:
                    chunks.append(pause_chunk)

        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks, axis=0)

    def generate_ivr_payload(
        self,
        provider_id: str,
        work_type: str,
        mrn: str,
        dictation_audio: np.ndarray,
        dictation_sr: int = 8000,
        initial_wait: float = 2.0,
        inter_step_wait: float = 2.0,
        pre_speech_wait: float = 3.0,
        save_disconnect_key: str = "8"
    ) -> np.ndarray:
        """
        Creates a single unified audio payload that executes the complete hospital IVR state sequence:
        1. Wait for connection greeting
        2. Dial Provider ID + '#' + Pause
        3. Dial Work Type + '#' + Pause
        4. Dial MRN + '#' + Pause for record tone
        5. Stream normalized dictation speech
        6. Dial Save/Disconnect Key ('8' / '#')
        """
        # Resample dictation audio to DTMF sample rate if needed
        if dictation_sr != self.sample_rate:
            from scipy.signal import resample_poly
            import math
            gcd = math.gcd(dictation_sr, self.sample_rate)
            up = self.sample_rate // gcd
            down = dictation_sr // gcd
            speech = resample_poly(dictation_audio, up, down).astype(np.float32)
        else:
            speech = dictation_audio.astype(np.float32)

        payload_chunks: List[np.ndarray] = []

        # 1. Initial wait after call answer
        payload_chunks.append(np.zeros(int(self.sample_rate * initial_wait), dtype=np.float32))

        # 2. Provider ID
        clean_provider = provider_id.strip() + ("#" if not provider_id.endswith("#") else "")
        payload_chunks.append(self.generate_digit_sequence(clean_provider))
        payload_chunks.append(np.zeros(int(self.sample_rate * inter_step_wait), dtype=np.float32))

        # 3. Work Type
        clean_work_type = work_type.strip() + ("#" if not work_type.endswith("#") else "")
        payload_chunks.append(self.generate_digit_sequence(clean_work_type))
        payload_chunks.append(np.zeros(int(self.sample_rate * inter_step_wait), dtype=np.float32))

        # 4. MRN
        clean_mrn = mrn.strip() + ("#" if not mrn.endswith("#") else "")
        payload_chunks.append(self.generate_digit_sequence(clean_mrn))
        payload_chunks.append(np.zeros(int(self.sample_rate * pre_speech_wait), dtype=np.float32))

        # 5. Dictation Speech
        payload_chunks.append(speech)

        # 6. Final Save Key & Disconnect Tone
        if save_disconnect_key:
            payload_chunks.append(np.zeros(int(self.sample_rate * 1.0), dtype=np.float32))
            payload_chunks.append(self.generate_digit_sequence(save_disconnect_key))
            payload_chunks.append(np.zeros(int(self.sample_rate * 0.5), dtype=np.float32))

        return np.concatenate(payload_chunks, axis=0)
