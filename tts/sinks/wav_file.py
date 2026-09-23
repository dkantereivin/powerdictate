"""
WAV File Audio Sink
===================
Exports synthesized speech directly to a standard WAV audio file on disk.
"""

import os
import time
import logging
from typing import Optional
import numpy as np
import soundfile as sf
from tts.sinks.base import BaseAudioSink

logger = logging.getLogger("tts.sinks.wav_file")


class WavFileSink(BaseAudioSink):
    """
    Saves synthesized audio chunks to a clean WAV file on disk.
    """

    def __init__(self, output_path: Optional[str] = None, output_dir: str = "outputs"):
        self.output_dir = output_dir
        self.output_path = output_path
        self._last_saved_file: Optional[str] = None

    def play(self, audio: np.ndarray, sample_rate: int = 24000) -> None:
        """Saves the audio numpy array to the specified WAV file path."""
        if audio is None or len(audio) == 0:
            return

        if not self.output_path:
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.output_path = os.path.join(self.output_dir, f"dictation_{timestamp}.wav")

        parent_dir = os.path.dirname(self.output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Normalize float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val

        sf.write(self.output_path, audio, sample_rate, subtype="PCM_16")
        self._last_saved_file = self.output_path
        logger.info(f"Saved {len(audio) / sample_rate:.2f}s WAV file to {self.output_path}")

    def stop(self) -> None:
        pass

    def is_playing(self) -> bool:
        return False

    @property
    def last_saved_file(self) -> Optional[str]:
        return self._last_saved_file
