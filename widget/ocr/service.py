"""
Unified Clinical OCR Service
============================
Coordinates ScreenSnipper, ClipboardGrabber, RapidOCR, LLMStructurer,
and MeditechTabNavigator. Supports single snips, multi-page batch queues,
and automated multi-tab crawling.
"""

import os
import time
import logging
from typing import Callable, List, Optional, Tuple, Set
from PIL import Image

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtGui import QGuiApplication

from widget.ocr.engine import OcrEngine, OcrResult
from widget.ocr.capture import ScreenSnipper, ClipboardGrabber
from widget.ocr.meditech_parser import MeditechLabParser, ParsedLabReport
from widget.ocr.tab_navigator import MeditechTabNavigator, MeditechTab
from widget.ocr.llm_structurer import LLMStructurer

logger = logging.getLogger("widget.ocr.service")


class OcrWorker(QThread):
    """Background worker for OCR inference and clinical structuring."""

    finished_parsing = Signal(str, str, object)  # (formatted_result, raw_ocr, parsed_report)
    error_occurred = Signal(str)

    def __init__(self, image: Image.Image, parent=None):
        super().__init__(parent)
        self.image = image
        self.source_path = getattr(image, "_source_file_path", None)

    def run(self):
        try:
            engine = OcrEngine.get_instance()
            ocr_result = engine.recognize(self.image)
            if ocr_result.is_empty:
                self.finished_parsing.emit("", "", None)
                return

            # Deterministic report parse
            report = MeditechLabParser.parse_report(ocr_result.raw_text)

            # Check if LLM structuring is available/preferred
            structurer = LLMStructurer()
            if structurer._is_ollama_available() or structurer.openai_api_key:
                formatted = structurer.structure_clinical_text(ocr_result.raw_text)
            else:
                formatted = report.to_audio_dictation()

            self.finished_parsing.emit(formatted, ocr_result.raw_text, report)
        except Exception as e:
            logger.error(f"Error in OCR Worker: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            self._cleanup_source_file()

    def _cleanup_source_file(self):
        """Securely deletes any temporary screenshot file once parsing is completed."""
        if self.source_path and os.path.exists(self.source_path):
            try:
                os.remove(self.source_path)
                logger.info(f"Deleted temporary screenshot after parsing: {self.source_path}")
            except Exception as e:
                logger.warning(f"Could not delete temporary screenshot {self.source_path}: {e}")


class CrawlWorker(QThread):
    """Background worker for automated Meditech tab crawling and aggregation."""

    progress_updated = Signal(str)
    crawl_completed = Signal(str)
    crawl_failed = Signal(str)

    def __init__(self, target_tabs: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.target_tabs = target_tabs or ["Chemistry", "Hematology", "Coagulation"]

    def run(self):
        try:
            import pyautogui
        except ImportError:
            self.crawl_failed.emit("PyAutoGUI is required for automated tab crawling.")
            return

        try:
            # 1. Grab initial full screen
            self.progress_updated.emit("Scanning screen for Meditech tabs...")
            screen = QGuiApplication.primaryScreen()
            if not screen:
                self.crawl_failed.emit("Could not access primary display screen.")
                return

            qimg = screen.grabWindow(0).toImage()
            buffer = qimg.bits()
            img = Image.frombytes("RGBA", (qimg.width(), qimg.height()), bytes(buffer), "raw", "BGRA").convert("RGB")

            # 2. OCR initial screen to find tabs
            engine = OcrEngine.get_instance()
            res = engine.recognize(img)
            tabs = MeditechTabNavigator.detect_tabs(res, img)

            if not tabs:
                self.crawl_failed.emit("No Meditech tabs detected on screen.")
                return

            available_tabs = [t for t in self.target_tabs if t in tabs]
            if not available_tabs:
                self.crawl_failed.emit(f"None of target tabs {self.target_tabs} found on screen.")
                return

            reports: List[ParsedLabReport] = []

            for tab_name in available_tabs:
                tab = tabs[tab_name]
                self.progress_updated.emit(f"Opening tab '{tab_name}'...")

                # Click tab
                pyautogui.click(tab.center_x, tab.center_y)
                time.sleep(0.4)

                # Capture updated screen
                qimg_tab = screen.grabWindow(0).toImage()
                buf_tab = qimg_tab.bits()
                img_tab = Image.frombytes("RGBA", (qimg_tab.width(), qimg_tab.height()), bytes(buf_tab), "raw", "BGRA").convert("RGB")

                # Recognize and parse
                res_tab = engine.recognize(img_tab)
                rep = MeditechLabParser.parse_report(res_tab.raw_text)
                if rep.panels:
                    reports.append(rep)

            if not reports:
                self.crawl_failed.emit("No lab data found across crawled tabs.")
                return

            merged = MeditechLabParser.merge_reports(reports)
            formatted = merged.to_audio_dictation()
            self.crawl_completed.emit(formatted)

        except Exception as e:
            logger.error(f"Error during tab crawl: {e}", exc_info=True)
            self.crawl_failed.emit(str(e))


class ClinicalOcrService(QObject):
    """
    High-level OCR controller for the Dictation Canvas.
    Supports single snip, clipboard parse, multi-page batch mode, and tab crawling.
    """

    parsing_started = Signal()
    parsing_completed = Signal(str)  # Emits formatted text ready for cursor injection
    parsing_failed = Signal(str)
    batch_updated = Signal(int, str)  # (count, latest_summary)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snipper = ScreenSnipper()
        self.snipper.snip_completed.connect(self._on_snip_completed)
        self.snipper.snip_cancelled.connect(self._on_snip_cancelled)

        self._current_worker: Optional[OcrWorker] = None
        self._crawl_worker: Optional[CrawlWorker] = None

        self._batch_mode = False
        self._batch_reports: List[ParsedLabReport] = []
        self._tracked_screenshot_files: Set[str] = set()

    @property
    def is_batch_mode(self) -> bool:
        return self._batch_mode

    @property
    def batch_count(self) -> int:
        return len(self._batch_reports)

    def trigger_screen_snip(self):
        """Starts interactive full-screen marquee snip."""
        self.snipper.start_snip()

    def start_batch_mode(self):
        """Activates multi-page batch ingestion mode."""
        self._batch_mode = True
        self._batch_reports.clear()
        self.trigger_screen_snip()

    def finish_batch_mode(self):
        """Merges all accumulated reports and emits final formatted dictation."""
        self._batch_mode = False
        self._cleanup_all_tracked_files()
        if not self._batch_reports:
            self.parsing_failed.emit("No batch pages were captured.")
            return

        merged = MeditechLabParser.merge_reports(self._batch_reports)
        formatted = merged.to_audio_dictation()
        self._batch_reports.clear()

        if formatted:
            self.parsing_completed.emit(formatted)
        else:
            self.parsing_failed.emit("No clinical labs extracted from batch.")

    def cancel_batch_mode(self):
        """Aborts batch mode without inserting."""
        self._batch_mode = False
        self._batch_reports.clear()
        self._cleanup_all_tracked_files()

    def _cleanup_all_tracked_files(self):
        for path in list(self._tracked_screenshot_files):
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Cleaned up tracked temporary screenshot: {path}")
                except Exception as e:
                    logger.warning(f"Failed to delete {path}: {e}")
        self._tracked_screenshot_files.clear()

    def parse_clipboard_image(self) -> bool:
        """Parses image currently on clipboard if available."""
        img = ClipboardGrabber.get_clipboard_image()
        if img is None:
            return False

        self._process_image(img)
        return True

    def trigger_auto_crawl(self, target_tabs: Optional[List[str]] = None):
        """Autonomously crawls Meditech tabs on screen and compiles lab report."""
        self.parsing_started.emit()
        self._crawl_worker = CrawlWorker(target_tabs=target_tabs, parent=self)
        self._crawl_worker.progress_updated.connect(lambda msg: logger.info(f"Crawl progress: {msg}"))
        self._crawl_worker.crawl_completed.connect(self.parsing_completed.emit)
        self._crawl_worker.crawl_failed.connect(self.parsing_failed.emit)
        self._crawl_worker.start()

    def _on_snip_completed(self, pil_image: Image.Image):
        source_path = getattr(pil_image, "_source_file_path", None)
        if source_path:
            self._tracked_screenshot_files.add(source_path)
        self._process_image(pil_image)

    def _on_snip_cancelled(self):
        logger.info("Screen snip was cancelled by user.")
        if self._batch_mode and not self._batch_reports:
            self._batch_mode = False

    def _process_image(self, img: Image.Image):
        self.parsing_started.emit()

        self._current_worker = OcrWorker(img, self)
        self._current_worker.finished_parsing.connect(self._on_worker_finished)
        self._current_worker.error_occurred.connect(self._on_worker_error)
        self._current_worker.start()

    def _on_worker_finished(self, formatted: str, raw_ocr: str, report: Optional[ParsedLabReport]):
        if self._batch_mode:
            if report and report.panels:
                self._batch_reports.append(report)
                panel_summary = ", ".join(report.panels.keys())
                self.batch_updated.emit(len(self._batch_reports), panel_summary)
            else:
                self.parsing_failed.emit("No labs detected in snip. You can try again.")
        else:
            if formatted:
                self.parsing_completed.emit(formatted)
            else:
                self.parsing_failed.emit("No clinical text or labs detected in image.")

    def _on_worker_error(self, err_msg: str):
        self.parsing_failed.emit(f"OCR Error: {err_msg}")
