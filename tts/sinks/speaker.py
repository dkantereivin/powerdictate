"""
Default Speaker Audio Sink
==========================
Outputs synthesized clinical dictation directly to the user's default PC sound device
(Speakers, Headphones, or USB Audio Output).
"""

import logging
from typing import Optional
import numpy as np
import sounddevice as sd
from tts.sinks.base import BaseAudioSink

logger = logging.getLogger("tts.sinks.speaker")


class DefaultSpeakerSink(BaseAudioSink):
    """
    Direct live playback sink to the default system audio output.
    """

    def __init__(self, device: Optional[int] = None):
        self.device = device
        self._is_active = False

    def play(self, audio: np.ndarray, sample_rate: int = 24000) -> None:
        """Plays audio through the system default output device."""
        if audio is None or len(audio) == 0:
            return

        # Ensure float32 normalized between -1.0 and 1.0
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val

        try:
            self._is_active = True
            sd.play(audio, samplerate=sample_rate, device=self.device)
            logger.info(f"Playing {len(audio) / sample_rate:.2f}s audio on speaker sink (samplerate={sample_rate}Hz)")
        except Exception as e:
            self._is_active = False
            logger.error(f"Error playing audio on default sound device: {e}", exc_info=True)
            raise

    def stop(self) -> None:
        """Immediately stops sounddevice playback."""
        try:
            sd.stop()
        except Exception as e:
            logger.warning(f"Error stopping sounddevice: {e}")
        finally:
            self._is_active = False

    def is_playing(self) -> bool:
        """Checks if sounddevice stream is active."""
        try:
            stream = sd.get_stream()
            return stream is not None and stream.active
        except Exception:
            return False

    def wait(self) -> None:
        """Blocks until audio finishes playing."""
        try:
            sd.wait()
        except Exception as e:
            logger.warning(f"Error waiting for sounddevice playback: {e}")
        finally:
            self._is_active = False
