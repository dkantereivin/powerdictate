"""
Clinical OCR and Lab Ingestion Package
"""

from widget.ocr.engine import OcrEngine, OcrResult, OcrLine
from widget.ocr.capture import ScreenSnipper, ClipboardGrabber
from widget.ocr.meditech_parser import MeditechLabParser, ClinicalLabValue
from widget.ocr.llm_structurer import LLMStructurer
from widget.ocr.service import ClinicalOcrService

__all__ = [
    "OcrEngine",
    "OcrResult",
    "OcrLine",
    "ScreenSnipper",
    "ClipboardGrabber",
    "MeditechLabParser",
    "ClinicalLabValue",
    "LLMStructurer",
    "ClinicalOcrService",
]
