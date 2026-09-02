import wave
import time
import numpy as np
import pytest
from pathlib import Path
from widget.audio.recorder import AudioRecorder


def test_audio_recorder_simulated_stream():
    vu_values = []
    recorder = AudioRecorder(sample_rate=16000, on_vu_meter=lambda v: vu_values.append(v))

    # Simulate manual recording injection
    recorder.is_recording = True
    recorder.start_time = time.time()

    # Feed simulated 16kHz sine wave audio chunks (0.5s duration)
    t = np.linspace(0, 0.5, 8000, endpoint=False, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)
    recorder.audio_chunks.append(sine[:, np.newaxis])

    # Stop and export WAV
    saved_path = recorder.stop()
    assert saved_path is not None
    assert saved_path.exists()

    # Verify WAV properties
    with wave.open(str(saved_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        n_frames = wf.getnframes()
        assert n_frames == 8000

    # Clean up test file
    saved_path.unlink()
