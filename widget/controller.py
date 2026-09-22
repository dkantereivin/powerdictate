"""
Unified Dictation State Controller & STT Coordinator
====================================================
Coordinates microphone recording, live phrase-level transcription,
modular STT engine dispatching, lookahead command interception,
voice command execution, and dual-target routing.
"""

import time
import queue
import logging
import threading
from pathlib import Path
from typing import Optional
import numpy as np

from PySide6.QtCore import QObject, Signal, Slot
from widget.config import WidgetConfig
from widget.audio.recorder import AudioRecorder
from widget.stt.manager import SttEngineManager, AVAILABLE_MODELS
from widget.injector import InputInjector
from widget.lexer.dragon_fsm import DragonLexer, LexerAction
from widget.commands.executor import CommandExecutor

logger = logging.getLogger("widget.controller")


class DictationState:
    IDLE = "IDLE"
    RECORDING = "RECORDING"


class DictationController(QObject):
    """
    Unified controller coordinating recording, STT, command lexing, execution, and UI signals.
    """

    state_changed = Signal(str)                   # "IDLE" or "RECORDING"
    vu_meter_updated = Signal(float)              # 0.0 .. 100.0
    recording_saved = Signal(str, float)          # (file_name, duration_seconds)
    transcription_received = Signal(str)          # Formatted text chunk
    command_recognized = Signal(str, str, str)    # (name, hotkey, description)
    command_executed = Signal(str)                # (trigger)
    execute_command_requested = Signal(str, str)  # (trigger, target) for main-thread GUI dispatch
    model_switched = Signal(str)                  # New model name

    def __init__(self, config: Optional[WidgetConfig] = None):
        super().__init__()
        self.config = config or WidgetConfig.load()
        self.state = DictationState.IDLE

        # Audio Recorder with live phrase pause segmentation
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            device=self.config.audio_device,
            on_vu_meter=lambda v: self.vu_meter_updated.emit(v),
            on_segment_ready=self._on_audio_segment_ready
        )

        # Modular STT Engine Manager, Lexer & Command Executor
        self.stt_manager = SttEngineManager(active_model_key=self.config.stt_model)
        self.lexer = DragonLexer()
        self.injector = InputInjector()
        self.command_executor = CommandExecutor()

        self.audio_queue = queue.Queue()
        self.is_worker_running = True

        self.worker_thread = threading.Thread(target=self._stt_worker_loop, daemon=True)
        self.worker_thread.start()

    def _on_audio_segment_ready(self, audio_data: np.ndarray):
        """Called whenever a phrase pause boundary is detected during recording."""
        if audio_data is not None and len(audio_data) > 0:
            self.audio_queue.put(audio_data)

    def switch_model(self, model_key: str) -> bool:
        """Switches active transcription model dynamically."""
        success = self.stt_manager.switch_model(model_key)
        if success:
            self.config.stt_model = model_key
            self.config.save()
            model_name = AVAILABLE_MODELS.get(model_key, model_key)
            self.model_switched.emit(model_name)
            logger.info(f"Model successfully switched to: {model_name}")
        return success

    @Slot()
    def toggle(self):
        """Unified toggle: Invoked by BOTH UI button click and hotkey press."""
        if self.state == DictationState.IDLE:
            self.start_recording()
        else:
            self.stop_recording()

    @Slot()
    def ptt_press(self):
        """Unified PTT Press."""
        if self.state == DictationState.IDLE:
            self.start_recording()

    @Slot()
    def ptt_release(self):
        """Unified PTT Release."""
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

    def _stt_worker_loop(self):
        """
        Background thread running GPU medical transcription, lexer,
        sequential speech interruption, and command execution.
        """
        while self.is_worker_running:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if audio_data is None:
                break

            try:
                raw_text, _ = self.stt_manager.transcribe(audio_data, self.config.sample_rate)
                if raw_text and raw_text.strip():
                    # Pass through lookahead lexer to intercept commands & spoken punctuation
                    actions = self.lexer.process_transcription(raw_text)

                    for action in actions:
                        if action.action_type in ("TYPE_TEXT", "PASTE_TEXT"):
                            formatted_text = action.text
                            # 1. Stop active transcription: commit currently dictated text
                            if self.config.dictation_target == "cursor":
                                self.injector.inject_text(formatted_text)
                                time.sleep(0.04)  # Allow clipboard paste to settle

                            self.transcription_received.emit(formatted_text)

                        elif action.action_type == "COMMAND_TRIGGERED":
                            # Preceding text has already been committed in the prior action
                            time.sleep(0.04)

                            # 2. Run the command & display visual toast
                            self.command_recognized.emit(
                                action.command_name,
                                action.hotkey,
                                action.description
                            )

                            # Request command execution on target (thread-safe main thread dispatch)
                            self.execute_command_requested.emit(
                                action.trigger,
                                self.config.dictation_target
                            )
                            self.command_executed.emit(action.trigger)

                            # 3. Resume new transcription at wherever the new cursor is
                            # Brief pause allows active window or Dictation Box to move cursor
                            time.sleep(0.06)

            except Exception as e:
                logger.error(f"Worker transcription error: {e}")
            finally:
                self.audio_queue.task_done()
