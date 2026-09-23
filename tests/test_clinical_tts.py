"""
Unit Tests for Kokoro Clinical TTS Pipeline
===========================================
Tests medical pronunciation dictionary, transcriptionist proper noun spelling,
clinical lab and vital sign expansions, audio sinks, and neural Kokoro inference.
"""

import os
import pytest
import numpy as np

from tts.medical_dict import apply_medical_dictionary, MEDICAL_PRONUNCIATION_MAP, CLINICAL_ACRONYMS_MAP
from tts.preprocessor import ClinicalTextPreprocessor, spell_out_word, format_spelled_out_name
from tts.presets import CLINICAL_VOICE_PRESETS, DEFAULT_VOICE, KOKORO_SAMPLE_RATE
from tts.sinks import WavFileSink, DefaultSpeakerSink, VirtualCableSink
from tts.engine import KokoroClinicalEngine


def test_spell_out_word_and_name():
    """Verifies letter-by-letter spelling for medical transcriptionists."""
    assert spell_out_word("Kaczynski") == "K A C Z Y N S K I"
    assert spell_out_word("Vandermeer") == "V A N D E R M E E R"
    assert spell_out_word("Tillsonburg") == "T I L L S O N B U R G"

    formatted = format_spelled_out_name("Dr. Vandermeer")
    assert formatted == "Dr. Vandermeer, spelled V A N D E R M E E R"


def test_transcriptionist_proper_noun_disambiguation():
    """
    Verifies that clinician names, patient surnames, and explicit tags are spelled out,
    while standard medications and common disease names are preserved cleanly.
    """
    preprocessor = ClinicalTextPreprocessor(spell_ambiguities=True)

    input_text = (
        "Patient seen by Dr. Vandermeer and admitted under Dr. Kaczynski. "
        "Transferred from [spell:Tillsonburg] General Hospital. "
        "Diagnosed with acute cholecystitis and diverticulitis. "
        "Started on ceftriaxone and metoprolol."
    )

    output = preprocessor.preprocess(input_text)

    # 1. Names of individuals MUST be spelled out
    assert "Dr. Vandermeer, spelled V A N D E R M E E R" in output
    assert "Dr. Kaczynski, spelled K A C Z Y N S K I" in output

    # 2. Explicit place tag MUST be spelled out
    assert "Tillsonburg, spelled T I L L S O N B U R G" in output

    # 3. Standard clinical diseases and medications must NOT be spelled out letter-by-letter
    assert "C E F T R I A X O N E" not in output
    assert "M E T O P R O L O L" not in output
    assert "C H O L E C Y S T I T I S" not in output


def test_medical_dictionary_phonetics_and_acronyms():
    """Verifies phonetic substitutions and clinical acronym expansions."""
    # Test tricky drug pronunciations
    text1 = "Patient prescribed metoprolol, atorvastatin, and ceftriaxone."
    res1 = apply_medical_dictionary(text1)
    assert "meh-toe-pro-lol" in res1
    assert "uh-tor-vuh-stat-in" in res1
    assert "sef-try-axe-own" in res1

    # Test Greek/Latin clinical symptoms
    text2 = "Patient presents with dyspnea, cachexia, and pruritus."
    res2 = apply_medical_dictionary(text2)
    assert "disp-nee-uh" in res2
    assert "kuh-kex-ee-uh" in res2
    assert "proo-rye-tus" in res2

    # Test clinical acronyms (PO/BID/IV stay as clean spoken letters, NOT over-expanded)
    text3 = "Patient with COPD and CHF on PO medications BID and IV fluids."
    res3 = apply_medical_dictionary(text3)
    assert "C O P D" in res3
    assert "C H F" in res3
    assert "P O" in res3
    assert "B I D" in res3
    assert "I V" in res3
    assert "by mouth" not in res3
    assert "twice daily" not in res3


def test_clinical_vitals_and_labs_normalization():
    """Verifies that vitals and lab values are expanded into natural spoken cadence."""
    preprocessor = ClinicalTextPreprocessor()

    # Vitals
    vitals_text = "BP 138/82, HR 74, SpO2 96%, RR 16, Temp 37.1 C"
    vitals_res = preprocessor.preprocess(vitals_text)
    assert "blood pressure 138 over 82" in vitals_res
    assert "heart rate 74" in vitals_res
    assert "oxygen saturation 96 percent" in vitals_res
    assert "respiratory rate 16" in vitals_res
    assert "temperature 37.1 degrees" in vitals_res

    # Labs
    labs_text = "Labs (1/11/25 08:03): Na 140, K 4.4, BUN 8.6 (H), Cr 84.2, eGFR 102, Glu 6.3."
    labs_res = preprocessor.preprocess(labs_text)
    assert "January 11, 2025" in labs_res
    assert "Sodium 140" in labs_res
    assert "Potassium 4.4" in labs_res
    assert "B U N 8.6 high" in labs_res
    assert "Creatinine 84.2" in labs_res
    assert "E G F R 102" in labs_res
    assert "Glucose 6.3" in labs_res


def test_explicit_punctuation_mode():
    """Verifies explicit spoken punctuation for traditional transcription archives."""
    prep = ClinicalTextPreprocessor(explicit_punctuation=True)
    text = "Patient alert. Lungs clear, no wheezing.\nPlan: Continue current meds."
    res = prep.preprocess(text)

    assert "period" in res
    assert "comma" in res
    assert "new line" in res
    assert "colon" in res


def test_wav_file_sink(tmp_path):
    """Verifies saving synthesized audio to standard WAV file."""
    output_wav = str(tmp_path / "test_dictation.wav")
    sink = WavFileSink(output_path=output_wav)

    # 1 second of 24kHz audio (sine wave)
    sample_rate = 24000
    t = np.linspace(0, 1.0, sample_rate, dtype=np.float32)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)

    sink.play(sine, sample_rate=sample_rate)
    assert os.path.exists(output_wav)
    assert os.path.getsize(output_wav) > 1000


def test_speaker_sink_interface():
    """Verifies DefaultSpeakerSink interface and state management."""
    sink = DefaultSpeakerSink()
    assert not sink.is_playing()
    # Stopping an idle sink should not error
    sink.stop()


def test_kokoro_neural_inference_and_synthesis(tmp_path):
    """Verifies end-to-end Kokoro-82M neural inference on clinical text."""
    engine = KokoroClinicalEngine.get_instance()

    clinical_sentence = "Patient John Kaczynski evaluated by Dr. Vandermeer. Started on metoprolol 25 mg PO BID."
    preprocessed = engine.preprocess_text(clinical_sentence)

    assert "Dr. Vandermeer, spelled V A N D E R M E E R" in preprocessed
    assert "meh-toe-pro-lol" in preprocessed
    assert "P O" in preprocessed
    assert "B I D" in preprocessed
    assert "by mouth" not in preprocessed
    assert "twice daily" not in preprocessed

    # Synthesize audio with Kokoro
    audio = engine.synthesize(clinical_sentence, voice="am_adam", speed=1.0)
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.float32
    assert len(audio) > 0

    # Minimum duration check: sentence should take at least 2 seconds (48,000 samples @ 24kHz)
    duration_sec = len(audio) / engine.sample_rate
    assert duration_sec >= 2.0

    # Test file output
    out_file = str(tmp_path / "kokoro_out.wav")
    saved = engine.synthesize_to_file(clinical_sentence, output_path=out_file, voice="am_adam")
    assert os.path.exists(saved)
    assert os.path.getsize(saved) > 10000
