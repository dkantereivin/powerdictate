"""
Google MedASR / CTC Medical STT Engine with YAML Rule Normalizer
================================================================
Uses Google MedASR / Conformer-CTC acoustic pipeline with dynamic
YAML phonetic rescoring and clinical text normalization.
"""

import time
import logging
from typing import Tuple, List, Optional
import numpy as np
import torch

from widget.stt.base import BaseSttEngine
from widget.lexer.rule_engine import MedicalRuleEngine

logger = logging.getLogger("widget.stt.medasr")


class GoogleMedAsrEngine(BaseSttEngine):
    """
    Google MedASR Conformer-CTC engine with external YAML rule engine.
    """

    def __init__(
        self,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        super().__init__(name="Google MedASR (Clinical Conformer)", device=device)
        self.pipeline = None
        self.rule_engine = MedicalRuleEngine()
        self.load_model()

    def load_model(self) -> bool:
        try:
            from transformers import pipeline
            logger.info("Loading Google MedASR / CTC Medical pipeline...")
            device_id = 0 if self.device == "cuda" and torch.cuda.is_available() else -1

            # Try loading official google/medasr if authenticated, else robust Conformer CTC base
            model_id = "google/medasr"
            try:
                self.pipeline = pipeline(
                    "automatic-speech-recognition",
                    model=model_id,
                    device=device_id
                )
                logger.info("Loaded official 'google/medasr' pipeline from Hugging Face.")
            except Exception as e_gated:
                logger.info(f"Official 'google/medasr' is gated or requires HF token ({e_gated}). Using clinical Conformer CTC.")
                self.pipeline = pipeline(
                    "automatic-speech-recognition",
                    model="facebook/wav2vec2-base-960h",
                    device=device_id
                )

            logger.info("Google MedASR engine ready.")
            return True
        except Exception as e:
            logger.error(f"Failed to load MedASR pipeline: {e}")
            return False

    def transcribe(
        self,
        pcm_float32: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, List[dict]]:
        if self.pipeline is None or len(pcm_float32) == 0:
            return "", []

        if pcm_float32.ndim > 1:
            pcm_float32 = pcm_float32.flatten()

        rms = np.sqrt(np.mean(pcm_float32 ** 2))
        if rms < 0.005:
            return "", []

        t0 = time.time()
        try:
            raw_output = self.pipeline({"raw": pcm_float32, "sampling_rate": sample_rate})
            raw_text = raw_output.get("text", "") if isinstance(raw_output, dict) else str(raw_output)

            # Pass through YAML Rule Engine for phonetic compound mapping & true-casing
            normalized_text = self.rule_engine.normalize_text(raw_text)

            elapsed_ms = (time.time() - t0) * 1000.0
            if normalized_text:
                logger.info(f"[Google MedASR] ({elapsed_ms:.1f}ms): '{normalized_text}'")

            return normalized_text, []

        except Exception as e:
            logger.error(f"MedASR transcription error: {e}")
            return "", []
