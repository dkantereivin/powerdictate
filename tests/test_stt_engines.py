import pytest
from widget.stt.whisper_engine import WhisperSttEngine
from widget.stt.medasr_engine import GoogleMedAsrEngine
from widget.stt.manager import SttEngineManager, AVAILABLE_MODELS
from widget.lexer.rule_engine import MedicalRuleEngine


def test_whisper_punctuation_cleaning_and_abbreviations():
    engine = WhisperSttEngine.__new__(WhisperSttEngine)
    
    # 1. Test trailing auto-period stripping
    cleaned = engine._clean_whisper_punctuation("Patient is alert and oriented.")
    assert cleaned == "Patient is alert and oriented"

    # 2. Test abbreviation casing
    norm = engine._normalize_clinical_abbreviations("patient received lasix 40mg iv and po metoprolol bid")
    assert "IV" in norm
    assert "PO" in norm
    assert "BID" in norm


def test_medasr_user_example_phonetic_compound_rescoring():
    engine = GoogleMedAsrEngine.__new__(GoogleMedAsrEngine)
    engine.rule_engine = MedicalRuleEngine()

    # The exact string outputted in the user's test
    user_input = (
        "THIS IS AN EXAMPLE OF THE TEXT OUTPUT THAT COMES FROM MEDEAS AR "
        "AS YOU CAN SEE IT DOES NOT PROVIDE A OPTIMON TEXTFLO. "
        "FOR EXAMPLE IF I WERE TO TYPE FEROSA MIDE FORTY MELEGRAMS PI O DALY THIS IS THE OUTPUT."
    )

    rescored = engine.rule_engine.normalize_text(user_input)

    # Verify accurate clinical transformation
    assert "MedASR" in rescored
    assert "optimal text flow" in rescored
    assert "furosemide" in rescored
    assert "40 mg" in rescored
    assert "PO" in rescored
    assert "daily" in rescored


def test_stt_manager_model_switching():
    manager = SttEngineManager.__new__(SttEngineManager)
    manager.active_model_key = "whisper_large_v3_turbo"
    manager.engines = {}

    assert "whisper_large_v3_turbo" in AVAILABLE_MODELS
    assert "google_medasr" in AVAILABLE_MODELS
    assert "onnx_conformer" in AVAILABLE_MODELS
