"""
STT Engine Manager
==================
Coordinates model loading, registry, and dynamic runtime switching
between Whisper, Google MedASR, and Fast Conformer ONNX.
"""

import logging
from typing import Dict, Tuple, List, Optional
import numpy as np

from widget.stt.base import BaseSttEngine
from widget.stt.whisper_engine import WhisperSttEngine
from widget.stt.medasr_engine import GoogleMedAsrEngine
from widget.stt.onnx_engine import OnnxConformerEngine

logger = logging.getLogger("widget.stt.manager")

AVAILABLE_MODELS: Dict[str, str] = {
    "whisper_large_v3_turbo": "Faster-Whisper Large-v3 Turbo (CUDA FP16)",
    "google_medasr": "Google MedASR (Clinical Conformer)",
    "onnx_conformer": "Fast Conformer ONNX (Sub-30ms)",
}


class SttEngineManager:
    """
    Manages active STT engine instance and dynamic model transitions.
    """

    def __init__(self, active_model_key: str = "whisper_large_v3_turbo"):
        self.active_model_key = active_model_key
        self.engines: Dict[str, BaseSttEngine] = {}
        self._init_engine(self.active_model_key)

    def _init_engine(self, model_key: str) -> Optional[BaseSttEngine]:
        if model_key in self.engines:
            return self.engines[model_key]

        engine = None
        if model_key == "whisper_large_v3_turbo":
            engine = WhisperSttEngine()
        elif model_key == "google_medasr":
            engine = GoogleMedAsrEngine()
        elif model_key == "onnx_conformer":
            engine = OnnxConformerEngine()

        if engine:
            self.engines[model_key] = engine

        return engine

    def switch_model(self, model_key: str) -> bool:
        if model_key not in AVAILABLE_MODELS:
            logger.warning(f"Unknown STT model: {model_key}")
            return False

        if model_key == self.active_model_key and model_key in self.engines:
            return True

        logger.info(f"Switching active STT engine to '{AVAILABLE_MODELS[model_key]}'...")
        engine = self._init_engine(model_key)
        if engine:
            self.active_model_key = model_key
            logger.info("STT Engine switched successfully.")
            return True
        return False

    def transcribe(
        self,
        pcm_float32: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, List[dict]]:
        engine = self.engines.get(self.active_model_key)
        if engine is None:
            engine = self._init_engine(self.active_model_key)

        if engine is not None:
            return engine.transcribe(pcm_float32, sample_rate)

        return "", []
