"""
Medical Speech-to-Text Transcriber
==================================
High-accuracy clinical STT using Faster-Whisper (Large-v3-Turbo / Large-v3)
accelerated via GPU CTranslate2 with medical vocabulary priming.
"""

import os
import site
import sys
from pathlib import Path
from typing import List, Optional, Union, Tuple, Generator
import numpy as np
import torch

# Automatically ensure nvidia CUDA runtime library directories (cublas, cudnn) are in LD_LIBRARY_PATH
def _setup_nvidia_cuda_libs():
    try:
        nvidia_dirs = []
        for p in site.getsitepackages():
            nv_base = os.path.join(p, "nvidia")
            if os.path.exists(nv_base):
                for sub in os.listdir(nv_base):
                    sub_lib = os.path.join(nv_base, sub, "lib")
                    if os.path.exists(sub_lib):
                        nvidia_dirs.append(sub_lib)
        if nvidia_dirs:
            cur_ld = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = ":".join(nvidia_dirs) + (":" + cur_ld if cur_ld else "")
    except Exception:
        pass

_setup_nvidia_cuda_libs()

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

from src.stt.lexer import PowerPhraseLexer, LexerResult


# Hospital & CTU Medical Priming Prompt
MEDICAL_INITIAL_PROMPT = (
    "Internal Medicine and CTU clinical consultation note. "
    "Patient presents with dyspnea, orthopnea, JVP, troponin, HFrEF, HFpEF, "
    "ceftriaxone, piperacillin-tazobactam, Tazocin, amlodipine, metformin, "
    "atorvastatin, empagliflozin, ramipril, pantoprazole, Lasix, furosemide, "
    "apixaban, rivaroxaban, bisoprolol, CT head, CBC, lytes, BUN, Cr, eGFR, "
    "Wells score, PERC rule, CTA chest, GCS, bibasilar crackles, atrial fibrillation."
)


class MedicalTranscriber:
    """
    Faster-Whisper Medical STT Engine with GPU acceleration and clinical vocabulary priming.
    """

    def __init__(
        self,
        model_size_or_path: str = "large-v3-turbo",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        initial_prompt: str = MEDICAL_INITIAL_PROMPT,
        enable_lexer: bool = True
    ):
        if not HAS_FASTER_WHISPER:
            raise RuntimeError("faster-whisper is not installed. Install via pip install faster-whisper.")

        # Determine optimal device and precision
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        if compute_type is None:
            self.compute_type = "float16" if self.device == "cuda" else "int8"
        else:
            self.compute_type = compute_type

        self.initial_prompt = initial_prompt
        self.model_size = model_size_or_path

        # Initialize Faster-Whisper Model
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type
        )

        self.enable_lexer = enable_lexer
        self.lexer = PowerPhraseLexer() if enable_lexer else None

    def transcribe_file(
        self,
        audio_path: Union[str, Path],
        beam_size: int = 5,
        vad_filter: bool = True,
        apply_lexer: Optional[bool] = None
    ) -> Tuple[str, List[dict]]:
        """
        Transcribes an audio file on disk (.wav, .mp3, .flac, etc.).
        Returns (full_transcript, segment_info_list).
        """
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=beam_size,
            initial_prompt=self.initial_prompt,
            vad_filter=vad_filter,
            language="en"
        )

        segment_list = []
        raw_text_parts = []

        for seg in segments:
            seg_dict = {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "confidence": seg.avg_logprob
            }
            segment_list.append(seg_dict)
            raw_text_parts.append(seg.text.strip())

        raw_transcript = " ".join(raw_text_parts)

        should_apply_lexer = self.enable_lexer if apply_lexer is None else apply_lexer
        if should_apply_lexer and self.lexer:
            lexer_res = self.lexer.process(raw_transcript)
            return lexer_res.text, segment_list
        else:
            return raw_transcript, segment_list

    def transcribe_audio(
        self,
        audio_array: np.ndarray,
        beam_size: int = 5,
        vad_filter: bool = True,
        apply_lexer: Optional[bool] = None
    ) -> Tuple[str, List[dict]]:
        """
        Transcribes a 16kHz float32 audio numpy array.
        """
        segments, info = self.model.transcribe(
            audio_array,
            beam_size=beam_size,
            initial_prompt=self.initial_prompt,
            vad_filter=vad_filter,
            language="en"
        )

        segment_list = []
        raw_text_parts = []

        for seg in segments:
            seg_dict = {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "confidence": seg.avg_logprob
            }
            segment_list.append(seg_dict)
            raw_text_parts.append(seg.text.strip())

        raw_transcript = " ".join(raw_text_parts)

        should_apply_lexer = self.enable_lexer if apply_lexer is None else apply_lexer
        if should_apply_lexer and self.lexer:
            lexer_res = self.lexer.process(raw_transcript)
            return lexer_res.text, segment_list
        else:
            return raw_transcript, segment_list
