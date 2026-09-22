"""
Unified Dictation State Controller & STT Coordinator
====================================================
Coordinates microphone recording, modular STT engine dispatching,
lookahead command interception, voice command execution, and dual-target routing.
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
    model_switched = Signal(str)                  # New model name

    def __init__(self, config: Optional[WidgetConfig] = None):
        super().__init__()
        self.config = config or WidgetConfig.load()
        self.state = DictationState.IDLE

        # Audio Recorder
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            device=self.config.audio_device,
            on_vu_meter=lambda v: self.vu_meter_updated.emit(v)
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

        # Capture audio chunks before reset
        recorded_chunks = list(self.recorder.audio_chunks)
        saved_path = self.recorder.stop()
        self.state = DictationState.IDLE
        self.state_changed.emit(self.state)
        self.vu_meter_updated.emit(0.0)
        logger.info("Dictation state: IDLE")

        if recorded_chunks:
            # Send full utterance to STT worker
            audio_arr = np.concatenate(recorded_chunks, axis=0).flatten()
            self.audio_queue.put(audio_arr)

        if saved_path and saved_path.exists():
            duration = time.time() - self.recorder.start_time
            self.recording_saved.emit(saved_path.name, max(0.1, duration))

        return saved_path

    def _stt_worker_loop(self):
        """Background thread running GPU medical transcription, lexer & command execution."""
        while self.is_worker_running:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if audio_data is None:
                break

            try:
                raw_text, _ = self.stt_manager.transcribe(audio_data, self.config.sample_rate)
                if raw_text:
                    # Pass through lookahead lexer to intercept commands & spoken punctuation
                    actions = self.lexer.process_transcription(raw_text)

                    for action in actions:
                        if action.action_type == "COMMAND_TRIGGERED":
                            # 1. Trigger visual 3-second toast & notify UI
                            self.command_recognized.emit(
                                action.command_name,
                                action.hotkey,
                                action.description
                            )

                            # 2. Execute voice command on active window or Dictation Box
                            self.command_executor.execute_command(
                                trigger=action.trigger,
                                target=self.config.dictation_target
                            )
                            self.command_executed.emit(action.trigger)

                        elif action.action_type in ("TYPE_TEXT", "PASTE_TEXT"):
                            formatted_text = action.text
                            # Route to active cursor or dictation box
                            if self.config.dictation_target == "cursor":
                                self.injector.inject_text(formatted_text)

                            self.transcription_received.emit(formatted_text)

            except Exception as e:
                logger.error(f"Worker transcription error: {e}")
            finally:
                self.audio_queue.task_done()
