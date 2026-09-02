"""
Unified Dictation State Controller
==================================
Central coordinator for microphone recording, state transitions (IDLE vs RECORDING),
and dispatching actions uniformly between UI mouse events and global hotkeys.
"""

import time
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from widget.config import WidgetConfig
from widget.audio.recorder import AudioRecorder

logger = logging.getLogger("widget.controller")


class DictationState:
    IDLE = "IDLE"
    RECORDING = "RECORDING"


class DictationController(QObject):
    """
    Unified controller guaranteeing identical behavior for UI clicks and global hotkeys.
    """

    state_changed = Signal(str)           # "IDLE" or "RECORDING"
    vu_meter_updated = Signal(float)      # 0.0 .. 100.0
    recording_saved = Signal(str, float)  # (file_name, duration_seconds)

    def __init__(self, config: Optional[WidgetConfig] = None):
        super().__init__()
        self.config = config or WidgetConfig.load()
        self.state = DictationState.IDLE

        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            device=self.config.audio_device,
            on_vu_meter=lambda v: self.vu_meter_updated.emit(v)
        )

    @Slot()
    def toggle(self):
        """Unified toggle: Invoked by BOTH UI button click and hotkey press."""
        if self.state == DictationState.IDLE:
            self.start_recording()
        else:
            self.stop_recording()

    @Slot()
    def ptt_press(self):
        """Unified PTT Press: Invoked by BOTH UI button mouse-down and hotkey key-down."""
        if self.state == DictationState.IDLE:
            self.start_recording()

    @Slot()
    def ptt_release(self):
        """Unified PTT Release: Invoked by BOTH UI button mouse-up and hotkey key-up."""
        if self.state == DictationState.RECORDING:
            self.stop_recording()

    def start_recording(self) -> bool:
        if self.state == DictationState.RECORDING:
            return True

        success = self.recorder.start()
        if success:
            self.state = DictationState.RECORDING
            self.state_changed.emit(self.state)
            logger.info("Dictation state: RECORDING")
            return True
        return False

    def stop_recording(self) -> Optional[Path]:
        if self.state == DictationState.IDLE:
            return None

        saved_path = self.recorder.stop()
        self.state = DictationState.IDLE
        self.state_changed.emit(self.state)
        self.vu_meter_updated.emit(0.0)
        logger.info("Dictation state: IDLE")

        if saved_path and saved_path.exists():
            duration = time.time() - self.recorder.start_time
            self.recording_saved.emit(saved_path.name, max(0.1, duration))

        return saved_path
