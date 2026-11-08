"""
MP3 File Audio Sink
===================
Exports synthesized clinical speech directly to high-quality compressed MP3
using ffmpeg libmp3lame.
"""

import os
import time
import shutil
import logging
import subprocess
from typing import Optional
from pathlib import Path
import numpy as np
import soundfile as sf

from tts.sinks.base import BaseAudioSink

logger = logging.getLogger("tts.sinks.mp3_file")


class Mp3FileSink(BaseAudioSink):
    """
    Saves synthesized audio chunks to an MP3 file on disk using ffmpeg.
    """

    def __init__(
        self,
        output_path: Optional[str] = None,
        output_dir: str = "outputs",
        bitrate: str = "192k"
    ):
        self.output_dir = output_dir
        self.output_path = output_path
        self.bitrate = bitrate
        self._last_saved_file: Optional[str] = None

    def play(self, audio: np.ndarray, sample_rate: int = 24000) -> None:
        """Encodes and saves the audio numpy array to the specified MP3 file path."""
        if audio is None or len(audio) == 0:
            return

        if not self.output_path:
            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.output_path = os.path.join(self.output_dir, f"dictation_{timestamp}.mp3")

        # Ensure .mp3 extension
        if not self.output_path.lower().endswith(".mp3"):
            self.output_path = f"{self.output_path}.mp3"

        parent_dir = os.path.dirname(self.output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Normalize float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val

        # Convert to 16-bit integer PCM bytes
        pcm16 = (audio * 32767.0).astype(np.int16)
        raw_bytes = pcm16.tobytes()

        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-y",  # Overwrite
                "-f", "s16le",  # Input raw format
                "-ar", str(sample_rate),  # Sample rate
                "-ac", "1",  # Mono
                "-i", "pipe:0",  # Read from stdin
                "-codec:a", "libmp3lame",
                "-b:a", self.bitrate,
                self.output_path
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    input=raw_bytes,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                self._last_saved_file = self.output_path
                duration = len(audio) / sample_rate
                logger.info(f"Saved {duration:.2f}s MP3 file to {self.output_path} via ffmpeg")
                return
            except subprocess.CalledProcessError as e:
                logger.warning(f"ffmpeg conversion failed ({e}), falling back to WAV...")

        # Fallback if ffmpeg is missing or failed: save as WAV
        fallback_wav = str(Path(self.output_path).with_suffix(".wav"))
        sf.write(fallback_wav, audio, sample_rate, subtype="PCM_16")
        self._last_saved_file = fallback_wav
        logger.warning(f"Saved WAV fallback to {fallback_wav}")

    def stop(self) -> None:
        pass

    def is_playing(self) -> bool:
        return False

    @property
    def last_saved_file(self) -> Optional[str]:
        return self._last_saved_file
