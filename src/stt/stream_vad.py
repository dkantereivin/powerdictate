"""
VAD-Gated Streaming Speech Buffer
=================================
Performs clean speech-chunking and silence detection on 16kHz microphone streams,
ensuring Whisper transcribes each utterance once upon natural speech pauses
without word repetition, duplication, or out-of-order text.
"""

import numpy as np
from typing import Optional, Tuple, Generator, List


class StreamingAudioProcessor:
    """
    Processes incoming 16kHz PCM audio chunks with energy-based VAD and silence detection.
    Flushes completed utterances to Faster-Whisper upon phrase completion.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        silence_threshold_rms: float = 0.015,
        min_silence_duration: float = 0.45,   # 450ms silence triggers utterance flush
        min_speech_duration: float = 0.35,    # Ignore clicks / noise shorter than 350ms
        max_utterance_duration: float = 8.0,  # Force flush long continuous utterances at 8s
    ):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold_rms
        self.min_silence_samples = int(sample_rate * min_silence_duration)
        self.min_speech_samples = int(sample_rate * min_speech_duration)
        self.max_utterance_samples = int(sample_rate * max_utterance_duration)

        self.audio_buffer: List[float] = []
        self.silence_samples_count: int = 0
        self.is_in_speech: bool = False
        self.lead_in_buffer: List[float] = []
        self.lead_in_max_samples = int(sample_rate * 0.15)  # 150ms pre-speech buffer

    def process_chunk(self, chunk_pcm16: bytes) -> Optional[np.ndarray]:
        """
        Accepts raw 16-bit PCM bytes from WebSocket.
        Returns a float32 numpy array ready for transcription IF a phrase is completed,
        otherwise returns None.
        """
        if not chunk_pcm16:
            return None

        # Convert Int16 bytes to Float32 array [-1.0, 1.0]
        pcm_data = np.frombuffer(chunk_pcm16, dtype=np.int16)
        float_chunk = pcm_data.astype(np.float32) / 32768.0

        # Calculate chunk energy
        rms = np.sqrt(np.mean(float_chunk ** 2)) if len(float_chunk) > 0 else 0.0

        if rms >= self.silence_threshold:
            # Active Speech Detected
            if not self.is_in_speech:
                self.is_in_speech = True
                # Prepend lead-in buffer to avoid clipping the start of speech
                self.audio_buffer.extend(self.lead_in_buffer)
                self.lead_in_buffer.clear()

            self.audio_buffer.extend(float_chunk.tolist())
            self.silence_samples_count = 0

            # If phrase exceeds max duration, force emit to keep latency low
            if len(self.audio_buffer) >= self.max_utterance_samples:
                return self._flush_utterance()

        else:
            # Silence / Ambient Noise
            if self.is_in_speech:
                self.audio_buffer.extend(float_chunk.tolist())
                self.silence_samples_count += len(float_chunk)

                if self.silence_samples_count >= self.min_silence_samples:
                    # Natural pause reached: Emit completed utterance
                    return self._flush_utterance()
            else:
                # Keep rolling pre-speech lead-in buffer
                self.lead_in_buffer.extend(float_chunk.tolist())
                if len(self.lead_in_buffer) > self.lead_in_max_samples:
                    self.lead_in_buffer = self.lead_in_buffer[-self.lead_in_max_samples:]

        return None

    def flush(self) -> Optional[np.ndarray]:
        """Manually flushes whatever audio is in the buffer."""
        if len(self.audio_buffer) >= self.min_speech_samples:
            return self._flush_utterance()
        self.audio_buffer.clear()
        self.is_in_speech = False
        return None

    def _flush_utterance(self) -> Optional[np.ndarray]:
        if len(self.audio_buffer) < self.min_speech_samples:
            self.audio_buffer.clear()
            self.is_in_speech = False
            self.silence_samples_count = 0
            return None

        audio_arr = np.array(self.audio_buffer, dtype=np.float32)
        self.audio_buffer.clear()
        self.is_in_speech = False
        self.silence_samples_count = 0
        return audio_arr
