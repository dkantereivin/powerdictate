import pytest
from pathlib import Path
import soundfile as sf
from src.tts.synthesizer import MedicalTTSSynthesizer
from src.tts.normalizer import NormalizationMode


@pytest.fixture(scope="module")
def tts_engine():
    return MedicalTTSSynthesizer()


def test_lexicon_overrides_loaded(tts_engine):
    assert tts_engine.num_lexicon_overrides > 100
    # Check that tazobactam and empagliflozin are present in lexicon
    golds = tts_engine.pipeline.g2p.lexicon.golds
    assert "tazobactam" in golds
    assert "empagliflozin" in golds
    assert "ceftriaxone" in golds
    assert "pantoprazole" in golds


def test_full_consult_synthesis(tts_engine, tmp_path):
    consult_text = """
    Reason for consultation: Progressive exertional dyspnea and orthopnea.
    Past Medical History: Heart failure with reduced ejection fraction, stage 3 chronic kidney disease.
    Medications: Tazocin 3.375g IV q8h, empagliflozin 10mg PO daily, ramipril 10mg PO daily, and pantoprazole 40mg PO daily.
    Examination: BP 138/74, HR 82 regular, JVP 4cm, lungs bibasilar crackles.
    Assessment and Plan: Acute decompensated heart failure. Increase Lasix to 80mg IV BID.
    """
    
    # 1. Synthesize 24kHz master WAV (Dictation mode)
    master_path = tmp_path / "consult_master.wav"
    tts_engine.synthesize_to_file(consult_text, master_path, mode=NormalizationMode.DICTATION, telephony_8khz=False)
    assert master_path.exists()
    
    master_data, master_sr = sf.read(str(master_path))
    assert master_sr == 24000
    assert len(master_data) > master_sr * 5  # At least 5 seconds of spoken audio
    
    # 2. Synthesize 8kHz Telephony WAV (PBX mode)
    telephony_path = tmp_path / "consult_telephony_8k.wav"
    tts_engine.synthesize_to_file(consult_text, telephony_path, mode=NormalizationMode.DICTATION, telephony_8khz=True)
    assert telephony_path.exists()
    
    tel_data, tel_sr = sf.read(str(telephony_path))
    assert tel_sr == 8000
    assert len(tel_data) > tel_sr * 5
