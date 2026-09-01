import pytest
import numpy as np
from src.telephony.dtmf import DTMFGenerator, DTMF_FREQUENCIES
from src.telephony.fluency_drop import FluencyDropSink
from src.telephony.sip_dialer import SipVoipSink, SipConfig


def test_single_dtmf_digit_frequencies():
    gen = DTMFGenerator(sample_rate=8000, tone_duration=0.2)
    
    # Test digit '1' (frequencies 697 Hz and 1209 Hz)
    tone_1 = gen.generate_single_digit('1')
    assert len(tone_1) == int(8000 * 0.2)
    
    # Perform FFT to verify spectral peaks
    fft_vals = np.abs(np.fft.rfft(tone_1))
    freqs = np.fft.rfftfreq(len(tone_1), d=1/8000)
    
    # Find top 2 spectral peaks
    peak_indices = np.argsort(fft_vals)[-2:]
    peak_freqs = sorted(freqs[peak_indices])
    
    # Verify frequencies match ITU-T within +/- 15 Hz resolution
    assert any(abs(f - 697) < 15 for f in peak_freqs)
    assert any(abs(f - 1209) < 15 for f in peak_freqs)


def test_dtmf_sequence_generation():
    gen = DTMFGenerator(sample_rate=8000, tone_duration=0.1, pause_duration=0.05)
    seq = "1234#"
    audio = gen.generate_digit_sequence(seq)
    
    # Total duration = 5 digits * 0.1s + 4 pauses * 0.05s = 0.7s
    expected_samples = int(8000 * 0.7)
    assert abs(len(audio) - expected_samples) < 50


def test_ivr_payload_generation():
    gen = DTMFGenerator(sample_rate=8000)
    dummy_speech = np.zeros(8000 * 3, dtype=np.float32)  # 3 seconds of speech
    
    payload = gen.generate_ivr_payload(
        provider_id="1234",
        work_type="01",
        mrn="987654",
        dictation_audio=dummy_speech,
        dictation_sr=8000,
        initial_wait=1.0,
        inter_step_wait=1.0,
        pre_speech_wait=1.0
    )
    
    assert len(payload) > len(dummy_speech)
    assert np.max(np.abs(payload)) > 0  # DTMF tones are present


def test_fluency_drop_sink(tmp_path):
    drop_sink = FluencyDropSink(drop_directory=tmp_path)
    dummy_audio = np.zeros(24000 * 2, dtype=np.float32)
    
    meta = {
        "job_id": "TEST-JOB-001",
        "provider_id": "DR_SMITH",
        "work_type": "01",
        "mrn": "123456",
        "patient_name": "TEST, PATIENT"
    }
    
    res = drop_sink.emit(dummy_audio, sample_rate=24000, metadata=meta)
    
    assert res["job_id"] == "TEST-JOB-001"
    assert (tmp_path / "TEST-JOB-001.wav").exists()
    assert (tmp_path / "TEST-JOB-001.xml").exists()
    assert (tmp_path / "TEST-JOB-001.json").exists()


def test_sip_voip_sink_dry_run():
    config = SipConfig(
        sip_server="sip.voip.ms",
        caller_id="8075551234",
        target_dictation_number="8076846000",
        dry_run=True
    )
    sip_sink = SipVoipSink(config=config)
    dummy_speech = np.zeros(8000 * 2, dtype=np.float32)
    
    res = sip_sink.emit(dummy_speech, sample_rate=8000, metadata={"provider_id": "1234", "mrn": "987654"})
    assert res["status"] == "success"
    assert res["mode"] == "dry_run"
    assert res["target_number"] == "8076846000"
