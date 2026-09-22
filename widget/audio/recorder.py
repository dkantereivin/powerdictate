"""
Microphone Audio Recorder & WAV File Exporter
==============================================
Captures 16kHz audio with real-time VU meter calculation, phrase-level
pause segmentation for live transcription, and clean WAV file exports.
"""

import time
import wave
import logging
from pathlib import Path
from typing import Optional, Callable, List
import numpy as np
import sounddevice as sd

logger = logging.getLogger("widget.recorder")

RECORDINGS_DIR = Path("recordings")


class AudioRecorder:
    """
    Manages live microphone capture, real-time VU levels, pause segmentation, and WAV recording.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device: Optional[str] = None,
        on_vu_meter: Optional[Callable[[float], None]] = None,
        on_segment_ready: Optional[Callable[[np.ndarray], None]] = None
    ):
        self.sample_rate = sample_rate
        self.device = device
        self.on_vu_meter = on_vu_meter or (lambda v: None)
        self.on_segment_ready = on_segment_ready

        self.is_recording = False
        self.stream: Optional[sd.InputStream] = None
        self.audio_chunks: List[np.ndarray] = []
        self.phrase_chunks: List[np.ndarray] = []
        self.speech_active = False
        self.silence_blocks = 0
        self.start_time = 0.0

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """Starts live microphone recording."""
        if self.is_recording:
            return True

        self.audio_chunks = []
        self.phrase_chunks = []
        self.speech_active = False
        self.silence_blocks = 0
        self.is_recording = True
        self.start_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            if not self.is_recording:
                return

            # Compute RMS for smooth VU meter
            rms = np.sqrt(np.mean(indata ** 2))
            vu = min(100.0, float(rms * 450.0))
            self.on_vu_meter(vu)

            # Store copy of audio frames for total recording
            chunk = indata.copy()
            self.audio_chunks.append(chunk)

            # Phrase-level segmentation for live dictation & command interruption
            if self.on_segment_ready is not None:
                self.phrase_chunks.append(chunk)

                if rms > 0.012:  # Speech detected
                    self.speech_active = True
                    self.silence_blocks = 0
                else:  # Silence
                    if self.speech_active:
                        self.silence_blocks += 1
                        # ~450ms of silence (7 blocks @ 64ms) triggers phrase boundary
                        if self.silence_blocks >= 7:
                            if self.phrase_chunks:
                                phrase_data = np.concatenate(self.phrase_chunks, axis=0).flatten()
                                self.phrase_chunks = []
                                self.speech_active = False
                                self.silence_blocks = 0
                                # Require at least 0.35s of audio to avoid noise blips
                                if len(phrase_data) >= int(self.sample_rate * 0.35):
                                    self.on_segment_ready(phrase_data)

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

        # Emit any trailing phrase chunk that hadn't met silence threshold yet
        if self.on_segment_ready is not None and self.phrase_chunks:
            phrase_data = np.concatenate(self.phrase_chunks, axis=0).flatten()
            self.phrase_chunks = []
            if len(phrase_data) >= int(self.sample_rate * 0.3):
                self.on_segment_ready(phrase_data)

        if not self.audio_chunks:
            logger.warning("No audio recorded.")
            return None

        # Concatenate full session audio into 1D float32 array
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
