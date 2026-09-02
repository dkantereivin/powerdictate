"""
Microphone Audio Recorder & WAV File Exporter
==============================================
Captures 16kHz audio with real-time VU meter calculation and writes
clean WAV files to the recordings/ directory on stop.
"""

import time
import wave
import logging
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import sounddevice as sd

logger = logging.getLogger("widget.recorder")

RECORDINGS_DIR = Path("recordings")


class AudioRecorder:
    """
    Manages live microphone capture, real-time VU levels, and WAV recording.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device: Optional[str] = None,
        on_vu_meter: Optional[Callable[[float], None]] = None
    ):
        self.sample_rate = sample_rate
        self.device = device
        self.on_vu_meter = on_vu_meter or (lambda v: None)

        self.is_recording = False
        self.stream: Optional[sd.InputStream] = None
        self.audio_chunks = []
        self.start_time = 0.0

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """Starts live microphone recording."""
        if self.is_recording:
            return True

        self.audio_chunks = []
        self.is_recording = True
        self.start_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            if self.is_recording:
                # Compute RMS for smooth VU meter
                rms = np.sqrt(np.mean(indata ** 2))
                vu = min(100.0, float(rms * 450.0))
                self.on_vu_meter(vu)

                # Store copy of audio frames
                self.audio_chunks.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                blocksize=1024,
                device=self.device,
                callback=audio_callback
            )
            self.stream.start()
            logger.info("Microphone recording started.")
            return True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self.is_recording = False
            return False

    def stop(self) -> Optional[Path]:
        """Stops recording and saves WAV file to recordings/."""
        if not self.is_recording:
            return None

        self.is_recording = False
        self.on_vu_meter(0.0)

        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if not self.audio_chunks:
            logger.warning("No audio recorded.")
            return None

        # Concatenate audio into 1D float32 array
        audio_data = np.concatenate(self.audio_chunks, axis=0).flatten()
        duration = len(audio_data) / self.sample_rate

        # Convert to 16-bit PCM
        pcm16 = (np.clip(audio_data, -1.0, 1.0) * 32767.0).astype(np.int16)

        # Generate timestamp filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        wav_path = RECORDINGS_DIR / f"recording_{timestamp}.wav"

        try:
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(pcm16.tobytes())

            logger.info(f"Saved recording ({duration:.2f}s) to {wav_path}")
            return wav_path
        except Exception as e:
            logger.error(f"Failed to write WAV file: {e}")
            return None

    def toggle(self) -> tuple[bool, Optional[Path]]:
        """Toggles recording. Returns (is_recording_now, saved_file_path_if_stopped)."""
        if self.is_recording:
            saved_path = self.stop()
            return False, saved_path
        else:
            started = self.start()
            return started, None
