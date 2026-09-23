"""
Base Audio Sink Interface
=========================
Defines the standard interface for all audio submission targets
(Default speakers, PipeWire/PulseAudio virtual cables, WAV file exporters).
"""

from abc import ABC, abstractmethod
import numpy as np


class BaseAudioSink(ABC):
    """Abstract base class for audio submission sinks."""

    @abstractmethod
    def play(self, audio: np.ndarray, sample_rate: int = 24000) -> None:
        """Plays or sends audio chunk to the sink."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Immediately interrupts playback / transmission."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Returns True if the sink is currently outputting audio."""
        pass

    def wait(self) -> None:
        """Blocks until current audio playback has finished."""
        pass
