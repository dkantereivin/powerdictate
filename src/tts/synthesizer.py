"""
Medical Neural Text-to-Speech Engine
====================================
High-fidelity local medical speech synthesis using Kokoro-82M with
pharmacological phonetic overrides and decoupled audio sinks.
"""

import time
from pathlib import Path
from typing import List, Optional, Tuple, Union, Generator

import numpy as np

from kokoro import KPipeline
from src.tts.medical_lexicon import register_medical_lexicon
from src.tts.normalizer import ClinicalTextNormalizer, NormalizationMode
from src.tts.sinks import AudioSink, LocalSpeakerSink, FileAudioSink, TelephonyAudioSink


DEFAULT_VOICE = "af_heart"  # Clear, professional, high-intelligibility voice
# Other popular high-quality voices in Kokoro:
# "am_adam", "af_bella", "am_michael", "bm_george", "bf_emma", "af_sky"


class MedicalTTSSynthesizer:
    """
    Main TTS Engine for CTU Dictation & Clinical Documentation.
    """

    def __init__(
        self,
        lang_code: str = "a",
        default_voice: str = DEFAULT_VOICE,
        sample_rate: int = 24000
    ):
        self.lang_code = lang_code
        self.default_voice = default_voice
        self.sample_rate = sample_rate

        # Initialize Kokoro Pipeline
        self.pipeline = KPipeline(lang_code=self.lang_code, repo_id="hexgrad/Kokoro-82M")

        # Register medical phonetic dictionary overrides
        self.num_lexicon_overrides = register_medical_lexicon(self.pipeline)

        # Normalizers for both operating modes
        self.dictation_normalizer = ClinicalTextNormalizer(mode=NormalizationMode.DICTATION)
        self.ward_normalizer = ClinicalTextNormalizer(mode=NormalizationMode.WARD_REVIEW)

    def normalize_text(self, text: str, mode: NormalizationMode = NormalizationMode.DICTATION) -> str:
        """Normalizes clinical text according to selected mode."""
        if mode == NormalizationMode.DICTATION:
            return self.dictation_normalizer.normalize(text)
        else:
            return self.ward_normalizer.normalize(text)

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        mode: NormalizationMode = NormalizationMode.DICTATION,
        speed: float = 1.0,
        sink: Optional[AudioSink] = None,
    ) -> Tuple[np.ndarray, int]:
        """
        Synthesizes clinical text into a complete audio numpy array.
        Optionally emits the audio to the provided AudioSink.
        """
        voice = voice or self.default_voice
        normalized_text = self.normalize_text(text, mode=mode)

        if not normalized_text.strip():
            empty_audio = np.array([], dtype=np.float32)
            return empty_audio, self.sample_rate

        # Split text into clean paragraph sections for optimal prosody & cadence
        if mode == NormalizationMode.DICTATION:
            raw_paras = [p.strip() for p in normalized_text.split(" new paragraph ") if p.strip()]
            # Re-attach the spoken words "new paragraph" clearly
            para_texts = []
            for i, p in enumerate(raw_paras):
                if i > 0:
                    para_texts.append(f"new paragraph. {p}")
                else:
                    para_texts.append(p)
        else:
            para_texts = [p.strip() for p in normalized_text.split("\n\n") if p.strip()]

        audio_chunks: List[np.ndarray] = []
        pause_samples = int(self.sample_rate * 0.35)  # 350ms pause between paragraphs
        pause_chunk = np.zeros(pause_samples, dtype=np.float32)

        for i, p_text in enumerate(para_texts):
            generator = self.pipeline(p_text, voice=voice, speed=speed)
            for _, _, audio in generator:
                if audio is not None and len(audio) > 0:
                    audio_chunks.append(audio)
            if i < len(para_texts) - 1:
                audio_chunks.append(pause_chunk)

        if not audio_chunks:
            full_audio = np.array([], dtype=np.float32)
        else:
            full_audio = np.concatenate(audio_chunks, axis=0)

        # If a sink is provided, dispatch the generated audio
        if sink is not None:
            metadata = {
                "voice": voice,
                "mode": mode.value,
                "speed": speed,
                "original_text": text,
                "normalized_text": normalized_text
            }
            sink.emit(full_audio, self.sample_rate, metadata)

        return full_audio, self.sample_rate

    def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        mode: NormalizationMode = NormalizationMode.DICTATION,
        speed: float = 1.0
    ) -> Generator[Tuple[str, str, np.ndarray], None, None]:
        """
        Streaming generator yielding (graphemes, phonemes, audio_chunk) in real-time.
        """
        voice = voice or self.default_voice
        normalized_text = self.normalize_text(text, mode=mode)
        generator = self.pipeline(normalized_text, voice=voice, speed=speed)
        for gs, ps, audio in generator:
            yield gs, ps, audio

    def synthesize_to_file(
        self,
        text: str,
        output_path: Union[str, Path],
        voice: Optional[str] = None,
        mode: NormalizationMode = NormalizationMode.DICTATION,
        telephony_8khz: bool = False,
        speed: float = 1.0
    ) -> Path:
        """
        Convenience method to synthesize text directly to a file (24kHz WAV or 8kHz Telephony WAV).
        """
        if telephony_8khz:
            sink = TelephonyAudioSink(output_path=output_path, target_sample_rate=8000)
        else:
            sink = FileAudioSink(output_path=output_path)

        self.synthesize(text, voice=voice, mode=mode, speed=speed, sink=sink)
        return Path(output_path)

    def synthesize_and_play(
        self,
        text: str,
        voice: Optional[str] = None,
        mode: NormalizationMode = NormalizationMode.WARD_REVIEW,
        speed: float = 1.0,
        blocking: bool = True
    ) -> np.ndarray:
        """
        Convenience method to synthesize and play directly to room speakers/headphones.
        """
        speaker_sink = LocalSpeakerSink(blocking=blocking)
        audio, _ = self.synthesize(text, voice=voice, mode=mode, speed=speed, sink=speaker_sink)
        return audio
