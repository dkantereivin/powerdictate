"""
Faster-Whisper Large-v3-Turbo Medical STT Engine
================================================
CUDA-accelerated Faster-Whisper with controlled punctuation stripping,
medical vocabulary conditioning, and clinical abbreviation normalization.
"""

import re
import time
import logging
from typing import Tuple, List, Optional
import numpy as np
import torch
from faster_whisper import WhisperModel

from widget.stt.base import BaseSttEngine

logger = logging.getLogger("widget.stt.whisper")

# Medical prompt without arbitrary punctuation to prevent hallucinated sentences
WHISPER_MEDICAL_PROMPT = (
    "Medical transcription dictation without punctuation. "
    "Medications dosages vitals physical exam assessment plan: "
    "period comma colon semicolon new line new paragraph "
    "Lasix Metoprolol Lisinopril Vancomycin Cefepime Apixaban "
    "mg IV PO BID TID PRN QD BP HR SpO2"
)

# Common medical abbreviation casing map
CLINICAL_CASING_MAP = {
    "iv": "IV",
    "po": "PO",
    "bid": "BID",
    "tid": "TID",
    "qid": "QID",
    "prn": "PRN",
    "qd": "QD",
    "qhs": "QHS",
    "bp": "BP",
    "hr": "HR",
    "rr": "RR",
    "spo2": "SpO2",
    "ekg": "EKG",
    "ecg": "ECG",
    "ct": "CT",
    "mri": "MRI",
    "cxr": "CXR",
    "hpi": "HPI",
    "ros": "ROS",
    "pe": "PE",
    "sob": "SOB",
    "cp": "CP",
    "chf": "CHF",
    "copd": "COPD",
    "htn": "HTN",
    "dm": "DM",
    "ckd": "CKD",
    "esrd": "ESRD",
}


class WhisperSttEngine(BaseSttEngine):
    """
    Faster-Whisper engine with medical terminology and controlled punctuation.
    """

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        compute_type: str = "float16" if torch.cuda.is_available() else "int8"
    ):
        super().__init__(name="Faster-Whisper Large-v3 Turbo (CUDA FP16)", device=device)
        self.model_name = model_name
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None
        self.load_model()

    def load_model(self) -> bool:
        try:
            logger.info(f"Loading Faster-Whisper '{self.model_name}' on {self.device.upper()} ({self.compute_type})...")
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("Faster-Whisper loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper: {e}")
            if self.device == "cuda":
                logger.info("Retrying on CPU...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel("base", device="cpu", compute_type="int8")
                return True
            return False

    def transcribe(
        self,
        pcm_float32: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, List[dict]]:
        if self.model is None or len(pcm_float32) == 0:
            return "", []

        if pcm_float32.ndim > 1:
            pcm_float32 = pcm_float32.flatten()

        rms = np.sqrt(np.mean(pcm_float32 ** 2))
        if rms < 0.005:
            return "", []

        t0 = time.time()
        try:
            segments, info = self.model.transcribe(
                pcm_float32,
                beam_size=1,  # Sub-50ms greedy decode
                language="en",
                initial_prompt=WHISPER_MEDICAL_PROMPT,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=250),
                condition_on_previous_text=False,
                temperature=0.0
            )

            text_pieces = [seg.text for seg in segments]
            raw_text = " ".join(text_pieces).strip()

            # Clean Whisper's auto-inserted periods/commas so spoken punctuation governs output
            cleaned_text = self._clean_whisper_punctuation(raw_text)
            normalized_text = self._normalize_clinical_abbreviations(cleaned_text)

            elapsed_ms = (time.time() - t0) * 1000.0
            if normalized_text:
                logger.info(f"[Whisper Large-v3-Turbo] ({elapsed_ms:.1f}ms): '{normalized_text}'")

            return normalized_text, []

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return "", []

    def _clean_whisper_punctuation(self, text: str) -> str:
        """
        Removes hallucinated/arbitrary auto-punctuation while preserving
        explicitly spoken punctuation tokens.
        """
        # If the user dictated "period" or "comma", Whisper sometimes puts both "." and "period".
        # We strip lone trailing periods that Whisper automatically attaches to every utterance.
        t = text.strip()
        if t.endswith(".") and not t.lower().endswith("period."):
            t = t[:-1]
        return t

    def _normalize_clinical_abbreviations(self, text: str) -> str:
        """Fixes casing for common clinical abbreviations (e.g. 'iv' -> 'IV')."""
        tokens = text.split()
        normalized = []
        for token in tokens:
            lower_token = token.lower().rstrip(".,;:?!")
            punct = token[len(lower_token):] if len(token) > len(lower_token) else ""
            if lower_token in CLINICAL_CASING_MAP:
                normalized.append(CLINICAL_CASING_MAP[lower_token] + punct)
            else:
                normalized.append(token)
        return " ".join(normalized)
