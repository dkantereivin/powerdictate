"""
Clinical Dictation Export & Telephony Submission Worker
======================================================
Asynchronous background worker handling:
1. MP3 file generation using neural Kokoro-82M and ffmpeg.
2. Hospital telephone line submission with standardized call flow templates:
   (dial number -> wait -> DTMF provider# -> site# -> work_type# -> MRN# -> DICTATE NOW -> #)
   supporting both VoIP.ms SIP trunking and Bluetooth mobile phone gateway,
   waiting for the call to be answered, and providing real-time bi-directional
   audio monitoring and live prompt transcripts.
"""

import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QThread, Signal, Slot

from tts.preprocessor import ClinicalTextPreprocessor
from tts.sinks.mp3_file import Mp3FileSink
from tts.dtmf import generate_dtmf_tone, DTMF_FREQUENCIES
from widget.setup_config import DictationSetupConfig

logger = logging.getLogger("widget.dictation_export_worker")


class DictationExportWorker(QThread):
    """
    Background worker thread for offline audio generation and live telephone submission.
    """

    status_changed = Signal(str)
    progress_updated = Signal(int, str)
    dtmf_digit_emitted = Signal(str, int)          # (digit, duration_ms)
    transcript_emitted = Signal(str, str)          # (speaker, text)
    audio_activity_emitted = Signal(str, float)    # (source, level)
    finished = Signal(str, str)                    # (mode, result_path_or_summary)
    error = Signal(str)

    def __init__(
        self,
        mode: str,  # "mp3" or "dial"
        note_text: str,
        config: DictationSetupConfig,
        patient_name: str = "",
        mrn: str = "",
        work_type: str = "001",
        submission_channel: Optional[str] = None,
        listen_in_real_time: bool = True,
        output_file_path: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.mode = mode.lower()
        self.note_text = note_text
        self.config = config
        self.patient_name = patient_name
        self.mrn = mrn
        self.work_type = work_type or config.work_type or "001"
        self.submission_channel = (submission_channel or getattr(config, "submission_channel", "voip") or "voip").lower()
        self.listen_in_real_time = listen_in_real_time
        self.output_file_path = output_file_path

        self._is_aborted = False
        self._speaker_sink = None
        self._active_telephony = None

    @property
    def speaker_sink(self):
        if self._speaker_sink is None:
            from tts.sinks.speaker import DefaultSpeakerSink
            self._speaker_sink = DefaultSpeakerSink()
        return self._speaker_sink

    def set_listen_in_real_time(self, listen: bool):
        """Allows toggling real-time monitoring on the fly while streaming."""
        self.listen_in_real_time = listen
        if self._active_telephony:
            self._active_telephony.listen_in_real_time = listen
        if not listen and self._speaker_sink:
            self._speaker_sink.stop()

    def abort(self):
        """Aborts current synthesis / call playback."""
        self._is_aborted = True
        if self._active_telephony:
            self._active_telephony.hangup()
        if self._speaker_sink:
            self._speaker_sink.stop()

    def run(self):
        try:
            if self.mode == "mp3":
                self._run_mp3_export()
            elif self.mode == "dial":
                self._run_dial_in_telephony()
            else:
                self.error.emit(f"Unknown submission mode: {self.mode}")
        except Exception as e:
            logger.error(f"Error in DictationExportWorker: {e}", exc_info=True)
            self.error.emit(str(e))

    def _run_mp3_export(self):
        """Generates MP3 audio file from the clinical note."""
        self.status_changed.emit("Preprocessing clinical text for oral dictation...")
        self.progress_updated.emit(10, "Preprocessing text...")

        preprocessor = ClinicalTextPreprocessor(explicit_punctuation=True, spell_ambiguities=True)
        body_script = preprocessor.preprocess(self.note_text)

        script_parts = []
        if self.config.introduction:
            script_parts.append(f"{self.config.introduction.strip()} new paragraph.")
        script_parts.append(body_script)
        if self.config.outro:
            script_parts.append(f"new paragraph. {self.config.outro.strip()}")

        full_script = " ".join(script_parts)

        if self._is_aborted:
            return

        self.status_changed.emit("Synthesizing clinical audio with Kokoro-82M...")
        self.progress_updated.emit(30, "Synthesizing neural audio...")

        from tts.engine import KokoroClinicalEngine
        engine = KokoroClinicalEngine.get_instance()
        audio = engine.synthesize(
            full_script,
            voice=self.config.tts_voice,
            speed=self.config.tts_speed,
            explicit_punctuation=True,
            preprocess=False
        )

        if self._is_aborted:
            return

        self.status_changed.emit("Encoding to MP3 via ffmpeg...")
        self.progress_updated.emit(85, "Encoding MP3...")

        sink = Mp3FileSink(
            output_path=self.output_file_path,
            output_dir=self.config.output_dir
        )
        sink.play(audio, sample_rate=engine.sample_rate)

        saved_path = sink.last_saved_file or self.output_file_path or "outputs/dictation.mp3"
        self.progress_updated.emit(100, "Done")
        self.finished.emit("mp3", saved_path)

    def _run_dial_in_telephony(self):
        """
        Executes the hospital call flow template defined in setup.yaml:
        (e.g. dial number -> wait -> DTMF provider# -> site# -> work_type# -> patient MRN# -> DICTATE NOW -> #)
        strictly waiting for the call to be answered before transmitting DTMF or oral audio.
        """
        # 1. Resolve call flow template with standardized variables
        steps = self.config.resolve_call_flow(
            patient_name=self.patient_name,
            mrn=self.mrn,
            work_type=self.work_type
        )

        # 2. Pre-synthesize oral clinical dictation stream
        self.status_changed.emit("Preparing oral dictation script...")
        self.progress_updated.emit(10, "Preparing script...")

        preprocessor = ClinicalTextPreprocessor(explicit_punctuation=True, spell_ambiguities=True)
        oral_note = preprocessor.preprocess(self.note_text)

        script_segments = []
        if self.patient_name or self.mrn:
            preamble = self.config.format_patient_preamble(self.patient_name, self.mrn)
            script_segments.append(f"{preamble} new paragraph.")
        if self.config.introduction:
            script_segments.append(f"{self.config.introduction.strip()} new paragraph.")
        script_segments.append(oral_note)
        if self.config.outro:
            script_segments.append(f"new paragraph. {self.config.outro.strip()}")

        full_oral_script = " ".join(script_segments)

        self.status_changed.emit("Synthesizing oral speech via Kokoro-82M...")
        self.progress_updated.emit(20, "Synthesizing audio...")

        from tts.engine import KokoroClinicalEngine
        engine = KokoroClinicalEngine.get_instance()
        audio = engine.synthesize(
            full_oral_script,
            voice=self.config.tts_voice,
            speed=self.config.tts_speed,
            explicit_punctuation=True,
            preprocess=False
        )

        if self._is_aborted:
            return

        # 3. Initialize telephony client (VoIP vs Bluetooth)
        if self.submission_channel == "bluetooth":
            from tts.telephony.bluetooth_client import BluetoothClient
            telephony = BluetoothClient(
                device_name=getattr(self.config, "bluetooth_device_name", "Pixel 7 Pro DK"),
                device_mac=getattr(self.config, "bluetooth_device_mac", "D4:3A:2C:A5:93:9D"),
                listen_in_real_time=self.listen_in_real_time,
                status_callback=lambda s: self.status_changed.emit(s),
                transcript_callback=lambda spk, txt: self.transcript_emitted.emit(spk, txt),
                audio_activity_callback=lambda src, lvl: self.audio_activity_emitted.emit(src, lvl)
            )
        else:
            from tts.telephony.voip_client import VoIPMsClient
            telephony = VoIPMsClient(
                server=self.config.voip_server,
                username=self.config.voip_username,
                password=self.config.voip_password,
                port=self.config.voip_port,
                caller_id=self.config.voip_caller_id,
                listen_in_real_time=self.listen_in_real_time,
                status_callback=lambda s: self.status_changed.emit(s),
                transcript_callback=lambda spk, txt: self.transcript_emitted.emit(spk, txt),
                audio_activity_callback=lambda src, lvl: self.audio_activity_emitted.emit(src, lvl)
            )

        self._active_telephony = telephony
        telephony.connect()

        # 4. Sequentially execute call flow template steps
        total_steps = len(steps)
        for idx, step in enumerate(steps):
            if self._is_aborted:
                telephony.hangup()
                return

            action = step.get("action", "").lower()
            progress_pct = 25 + int((idx / total_steps) * 70)

            if action == "dial":
                phone_num = step.get("number") or step.get("value") or self.config.hospital_phone_number
                self.status_changed.emit(f"📞 Dialing: {phone_num}...")
                self.progress_updated.emit(progress_pct, f"Dialing {phone_num}...")

                # CRITICAL: Blocks and strictly WAITS until call is answered
                answered = telephony.dial(phone_num, timeout_sec=60.0)
                if not answered:
                    telephony.hangup()
                    self.error.emit(f"Call to {phone_num} was not answered or failed to connect.")
                    return

                self.progress_updated.emit(progress_pct + 5, "Line Connected & Answered")

            elif action == "wait":
                secs = float(step.get("seconds", 2.0))
                self.status_changed.emit(f"Waiting {secs:.1f}s for line prompt...")
                self.progress_updated.emit(progress_pct, f"Waiting {secs:.1f}s...")
                start_w = time.time()
                while time.time() - start_w < secs:
                    if self._is_aborted:
                        telephony.hangup()
                        return
                    time.sleep(0.1)

            elif action == "dtmf":
                tones = str(step.get("tones", "")).strip()
                if tones:
                    self.status_changed.emit(f"Transmitting DTMF: {tones}")
                    self.progress_updated.emit(progress_pct, f"DTMF: {tones}")
                    # Telephony client transmits tones and plays to monitor stream
                    telephony.send_dtmf(tones)
                    # Highlight keypad in visualizer
                    for ch in tones:
                        self.dtmf_digit_emitted.emit(ch, 140)

            elif action in ("dictate", "dictate_now", "stream_dictation"):
                self.status_changed.emit("🎙️ Streaming oral clinical dictation...")
                self.progress_updated.emit(progress_pct, "Streaming dictation...")

                # Stream audio to active call (and local monitor stream)
                telephony.stream_audio(
                    audio,
                    sample_rate=engine.sample_rate,
                    stop_check=lambda: self._is_aborted
                )

            elif action == "hangup":
                self.status_changed.emit("Concluding call...")
                telephony.hangup()

        telephony.disconnect()
        self.progress_updated.emit(100, "Completed")
        self.status_changed.emit("Dictation successfully submitted via hospital telephone line.")
        self.finished.emit("dial", "Hospital dictation call completed successfully.")
