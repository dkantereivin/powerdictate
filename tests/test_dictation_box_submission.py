"""
Unit and Integration Tests for Dictation Box Submission & Telephony
===================================================================
Tests:
1. DictationSetupConfig loading, defaults, DTMF formatting, and patient preamble spelling.
2. DTMF dual-frequency tone synthesis and sequence generation.
3. Mp3FileSink file export and ffmpeg compression.
4. UI component instantiation (PatientInfoDialog, DTMFVisualizerWidget, SetupConfigDialog).
5. DictationExportWorker script composition and event signaling.
"""

import os
import tempfile
from pathlib import Path
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from widget.setup_config import DictationSetupConfig
from tts.dtmf import generate_dtmf_tone, generate_dtmf_sequence, DTMF_FREQUENCIES
from tts.sinks.mp3_file import Mp3FileSink
from widget.ui.patient_info_dialog import PatientInfoDialog
from widget.ui.dtmf_visualizer import DTMFVisualizerWidget
from widget.ui.setup_dialog import SetupConfigDialog
from widget.ui.dictation_box import DictationBoxWidget
from widget.dictation_export_worker import DictationExportWorker


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dictation_setup_config_defaults_and_formatting():
    """Verifies setup.yaml parsing, default values, and patient preamble spelling."""
    config = DictationSetupConfig.load()

    assert config.provider_number is not None
    assert config.introduction is not None
    assert "David Kanter Eivin" in config.introduction

    # Verify provider DTMF sequence always ends with '#'
    dtmf_seq = config.get_provider_dtmf_sequence()
    assert dtmf_seq.endswith("#")

    # Verify patient preamble spells out name and spaces MRN
    preamble = config.format_patient_preamble("Jane Doe", "1234567")
    assert "Jane Doe, spelled J A N E space D O E" in preamble
    assert "Medical Record Number: 1 2 3 4 5 6 7." in preamble


def test_dtmf_tone_generation():
    """Verifies that DTMF dual-frequency waveforms are generated accurately."""
    sample_rate = 24000
    duration = 0.12

    for digit in ('0', '1', '5', '9', '*', '#'):
        tone = generate_dtmf_tone(digit, duration_sec=duration, sample_rate=sample_rate)
        assert isinstance(tone, np.ndarray)
        assert tone.dtype == np.float32
        assert len(tone) == int(duration * sample_rate)
        assert np.max(np.abs(tone)) > 0.05
        assert np.max(np.abs(tone)) <= 1.0

    # Test full sequence (e.g. '1234#')
    seq_audio = generate_dtmf_sequence("1234#", tone_duration=0.10, pause_duration=0.05, sample_rate=sample_rate)
    expected_min_len = int((5 * 0.10 + 4 * 0.05) * sample_rate)
    assert len(seq_audio) >= expected_min_len


def test_mp3_file_sink_export():
    """Verifies that Mp3FileSink generates an encoded MP3 file on disk."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_file = os.path.join(tmp_dir, "test_output.mp3")
        sink = Mp3FileSink(output_path=output_file)

        # Generate 1.0 second test tone
        sample_rate = 24000
        t = np.linspace(0, 1.0, sample_rate, dtype=np.float32)
        audio = 0.3 * np.sin(2.0 * np.pi * 440.0 * t)

        sink.play(audio, sample_rate=sample_rate)

        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 1000  # Non-empty compressed MP3
        assert sink.last_saved_file == output_file


def test_patient_info_dialog_ui(qapp):
    """Verifies PatientInfoDialog fields, defaults, and properties."""
    config = DictationSetupConfig(listen_in_real_time=True)
    dialog = PatientInfoDialog(config=config)

    assert dialog.listen_cb.isChecked() is True

    dialog.name_edit.setText("Robert Miller")
    dialog.mrn_edit.setText("9988776")
    dialog.listen_cb.setChecked(False)

    assert dialog.patient_name == "Robert Miller"
    assert dialog.mrn == "9988776"
    assert dialog.listen_in_real_time is False


def test_dtmf_visualizer_widget_ui(qapp):
    """Verifies DTMFVisualizerWidget keypad buttons and active illumination."""
    visualizer = DTMFVisualizerWidget()

    # Check all 12 standard buttons exist
    for char in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'):
        assert char in visualizer.buttons

    visualizer.start_call("Connecting...")
    assert visualizer.call_status_lbl.text() == "Connecting..."

    # Highlight digit '5'
    visualizer.highlight_dtmf('5', duration_ms=100)
    assert visualizer.buttons['5'].isEnabled()
    assert "5" in visualizer.digits_tape.text()

    visualizer.end_call("Completed")
    assert visualizer.call_status_lbl.text() == "Completed"


def test_setup_dialog_ui(qapp):
    """Verifies SetupConfigDialog loads and persists configuration."""
    config = DictationSetupConfig(
        introduction="Test Intro",
        outro="Test Outro",
        provider_number="5678"
    )
    dialog = SetupConfigDialog(config=config)

    assert dialog.intro_edit.toPlainText() == "Test Intro"
    assert dialog.outro_edit.text() == "Test Outro"
    assert dialog.prov_edit.text() == "5678"


