import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import pytest

from src.tts.sinks import FileAudioSink, TelephonyAudioSink, MultiSink


def test_file_audio_sink():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "test_out.wav"
        sink = FileAudioSink(output_path=out_file)
        
        sample_rate = 24000
        # 0.5s dummy sine wave
        t = np.linspace(0, 0.5, int(sample_rate * 0.5), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        
        sink.emit(audio, sample_rate)
        
        assert out_file.exists()
        data, sr = sf.read(str(out_file))
        assert sr == 24000
        assert len(data) == len(audio)


def test_telephony_audio_sink_resampling():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "test_telephony.wav"
        sink = TelephonyAudioSink(output_path=out_file, target_sample_rate=8000)
        
        sample_rate = 24000
        # 1.0s dummy sine wave
        t = np.linspace(0, 1.0, int(sample_rate * 1.0), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        
        sink.emit(audio, sample_rate)
        
        assert out_file.exists()
        data, sr = sf.read(str(out_file))
        assert sr == 8000
        assert len(data) == 8000  # Exactly 1 second at 8000 Hz


def test_multi_sink():
    with tempfile.TemporaryDirectory() as tmpdir:
        f1 = Path(tmpdir) / "out1.wav"
        f2 = Path(tmpdir) / "out2.wav"
        
        sink1 = FileAudioSink(output_path=f1)
        sink2 = TelephonyAudioSink(output_path=f2, target_sample_rate=8000)
        multi = MultiSink(sinks=[sink1, sink2])
        
        sample_rate = 24000
        t = np.linspace(0, 0.5, int(sample_rate * 0.5), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        
        results = multi.emit(audio, sample_rate)
        assert len(results) == 2
        assert f1.exists()
        assert f2.exists()
        
        d1, sr1 = sf.read(str(f1))
        d2, sr2 = sf.read(str(f2))
        assert sr1 == 24000
        assert sr2 == 8000
