import pytest
from pathlib import Path
from src.stt.transcriber import MedicalTranscriber


@pytest.fixture(scope="module")
def stt_engine():
    return MedicalTranscriber(model_size_or_path="large-v3-turbo")


def test_stt_transcription_on_cardiology_audio(stt_engine):
    audio_path = Path("output/cardiology_consult_pbx_master_24k.wav")
    if not audio_path.exists():
        pytest.skip("Sample audio file not found. Run sample_generator.py first.")
    
    transcript, segments = stt_engine.transcribe_file(audio_path, apply_lexer=True)
    
    assert len(transcript) > 50
    assert len(segments) > 0
    
    transcript_lower = transcript.lower()
    
    # Verify critical clinical terminology was accurately recognized
    assert "eleanor mcpherson" in transcript_lower or "mcpherson" in transcript_lower
    assert "dyspnea" in transcript_lower
    assert "palpitations" in transcript_lower
    assert "amlodipine" in transcript_lower
    assert "metformin" in transcript_lower
    assert "empagliflozin" in transcript_lower
    assert "ramipril" in transcript_lower
    assert "pantoprazole" in transcript_lower
