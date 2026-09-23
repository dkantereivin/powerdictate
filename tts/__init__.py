"""
PowerDictate Clinical TTS Package
=================================
High-fidelity medical speech synthesis using Kokoro-82M, clinical pronunciation
dictionaries, transcriptionist spelling expansions, and audio sinks.
"""

from tts.engine import KokoroClinicalEngine
from tts.preprocessor import ClinicalTextPreprocessor, spell_out_word, format_spelled_out_name
from tts.llm_transcription_prep import LLMTranscriptionPrep
from tts.medical_dict import apply_medical_dictionary, MEDICAL_PRONUNCIATION_MAP, CLINICAL_ACRONYMS_MAP
from tts.presets import CLINICAL_VOICE_PRESETS, DEFAULT_VOICE, KOKORO_SAMPLE_RATE, VoiceProfile
from tts.sinks import BaseAudioSink, DefaultSpeakerSink, WavFileSink, VirtualCableSink

__all__ = [
    "KokoroClinicalEngine",
    "ClinicalTextPreprocessor",
    "spell_out_word",
    "format_spelled_out_name",
    "LLMTranscriptionPrep",
    "apply_medical_dictionary",
    "MEDICAL_PRONUNCIATION_MAP",
    "CLINICAL_ACRONYMS_MAP",
    "CLINICAL_VOICE_PRESETS",
    "DEFAULT_VOICE",
    "KOKORO_SAMPLE_RATE",
    "VoiceProfile",
    "BaseAudioSink",
    "DefaultSpeakerSink",
    "WavFileSink",
    "VirtualCableSink",
]
