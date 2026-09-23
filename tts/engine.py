"""
Kokoro Clinical Text-to-Speech Engine
=====================================
Orchestrates medical text normalization, ambiguity spelling, pronunciation tuning,
Kokoro-82M neural acoustic synthesis, and audio sink routing.
"""

import os
import time
import logging
from typing import Generator, List, Optional, Tuple, Union
import numpy as np
import torch

from kokoro import KPipeline
from tts.presets import (
    CLINICAL_VOICE_PRESETS,
    DEFAULT_VOICE,
    KOKORO_SAMPLE_RATE,
    VoiceProfile
)
from tts.preprocessor import ClinicalTextPreprocessor
from tts.llm_transcription_prep import LLMTranscriptionPrep
from tts.sinks import BaseAudioSink, DefaultSpeakerSink, WavFileSink

logger = logging.getLogger("tts.engine")


class KokoroClinicalEngine:
    """
    High-performance clinical TTS engine powered by Kokoro-82M.
    Features:
    - Medical dictionary pronunciation correction
    - Ambiguity spelling for medical transcriptionists
    - Direct live audio output to PC default sound device
    - Optional WAV file persistence
    """

    _instance: Optional["KokoroClinicalEngine"] = None

    def __init__(
        self,
        lang_code: str = "a",  # American English
        default_voice: str = DEFAULT_VOICE,
        device: Optional[str] = None
    ):
        self.lang_code = lang_code
        self.default_voice = default_voice
        self.sample_rate = KOKORO_SAMPLE_RATE

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Initializing KokoroClinicalEngine on device: {self.device}...")
        self._pipeline: Optional[KPipeline] = None

        # Preprocessors
        self.deterministic_preprocessor = ClinicalTextPreprocessor(spell_ambiguities=True)
        self.llm_preprocessor = LLMTranscriptionPrep()

        # Default live audio output sink
        self.default_sink = DefaultSpeakerSink()

    @classmethod
    def get_instance(cls) -> "KokoroClinicalEngine":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = KokoroClinicalEngine()
        return cls._instance

    @property
    def pipeline(self) -> KPipeline:
        """Lazily instantiates the Kokoro KPipeline."""
        if self._pipeline is None:
            logger.info("Loading Kokoro-82M pipeline weights...")
            self._pipeline = KPipeline(
                lang_code=self.lang_code,
                repo_id="hexgrad/Kokoro-82M",
                device=self.device
            )
            logger.info("Kokoro pipeline loaded successfully.")
        return self._pipeline

    def preprocess_text(
        self,
        text: str,
        use_llm: bool = False,
        explicit_punctuation: bool = False
    ) -> str:
        """
        Normalizes raw clinical narrative, expands labs/vitals, and spells out
        ambiguous proper nouns (physicians, patients, places) for transcriptionists.
        """
        if use_llm:
            processed = self.llm_preprocessor.prepare_text(text)
        else:
            prep = ClinicalTextPreprocessor(
                explicit_punctuation=explicit_punctuation,
                spell_ambiguities=True
            )
            processed = prep.preprocess(text)
        return processed

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        preprocess: bool = True,
        use_llm: bool = False,
        explicit_punctuation: bool = False
    ) -> np.ndarray:
        """
        Synthesizes text into a clean float32 audio waveform (24kHz).
        Returns a single concatenated 1D numpy array.
        """
        if not text or not text.strip():
            return np.zeros(0, dtype=np.float32)

        voice_id = voice or self.default_voice
        # If passed preset name like 'adam', resolve to 'am_adam'
        if voice_id in CLINICAL_VOICE_PRESETS:
            voice_id = CLINICAL_VOICE_PRESETS[voice_id].id

        script = text
        if preprocess:
            script = self.preprocess_text(
                text,
                use_llm=use_llm,
                explicit_punctuation=explicit_punctuation
            )
            logger.info(f"Preprocessed Script for Kokoro:\n{script}")

        chunks: List[np.ndarray] = []
        generator = self.pipeline(script, voice=voice_id, speed=speed)
        for result in generator:
            if result.audio is not None:
                audio_np = result.audio.cpu().numpy() if isinstance(result.audio, torch.Tensor) else np.array(result.audio)
                chunks.append(audio_np)

        if not chunks:
            return np.zeros(0, dtype=np.float32)

        full_audio = np.concatenate(chunks)
        return full_audio.astype(np.float32)

    def synthesize_and_play(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        sink: Optional[BaseAudioSink] = None,
        wait: bool = False,
        preprocess: bool = True,
        use_llm: bool = False,
        explicit_punctuation: bool = False
    ) -> np.ndarray:
        """
        Synthesizes clinical text and immediately plays it through the specified
        audio sink (defaults to PC speaker).
        """
        target_sink = sink or self.default_sink
        audio = self.synthesize(
            text,
            voice=voice,
            speed=speed,
            preprocess=preprocess,
            use_llm=use_llm,
            explicit_punctuation=explicit_punctuation
        )

        if len(audio) > 0:
            target_sink.play(audio, sample_rate=self.sample_rate)
            if wait:
                target_sink.wait()

        return audio

    def synthesize_to_file(
        self,
        text: str,
        output_path: Optional[str] = None,
        output_dir: str = "outputs",
        voice: Optional[str] = None,
        speed: float = 1.0,
        preprocess: bool = True,
        use_llm: bool = False,
        explicit_punctuation: bool = False
    ) -> str:
        """
        Synthesizes text and saves the resulting audio to a WAV file.
        Returns the path to the saved file.
        """
        audio = self.synthesize(
            text,
            voice=voice,
            speed=speed,
            preprocess=preprocess,
            use_llm=use_llm,
            explicit_punctuation=explicit_punctuation
        )

        sink = WavFileSink(output_path=output_path, output_dir=output_dir)
        sink.play(audio, sample_rate=self.sample_rate)
        return sink.last_saved_file or ""

    def stop_playback(self) -> None:
        """Stops any active playback on the default sink."""
        if self.default_sink:
            self.default_sink.stop()
