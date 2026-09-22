"""
Base Interface for STT Transcription Engines
============================================
"""

from abc import ABC, abstractmethod
from typing import Tuple, List
import numpy as np


class BaseSttEngine(ABC):
    """
    Abstract base class for all STT transcription engines.
    """

    def __init__(self, name: str, device: str = "cuda"):
        self.name = name
        self.device = device

    @abstractmethod
    def load_model(self) -> bool:
        """Loads model weights into memory/VRAM."""
        pass

    @abstractmethod
    def transcribe(
        self,
        pcm_float32: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, List[dict]]:
        """
        Transcribes 1D float32 audio chunk into text.
        Returns (formatted_text, segments_list).
        """
        pass
