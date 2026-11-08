"""
Script to synthesize full oral clinical dictation for 'sample note.md'
======================================================================
Preprocesses the clinical note with:
1. Spoken unit conversion (e.g. 1g -> 1 gram, 104/62 mmHg -> 104 over 62 millimeters of mercury)
2. Unhyphenated natural pronunciations without pausing
3. Explicit spoken punctuation ('period', 'comma', 'colon', 'new line', 'new paragraph')
4. Transcriptionist proper noun spelling (Dr. Jenkins, Dr. Reed)
5. Clean spoken letter acronyms (PO, BID, IV, CKD, COPD, etc.)
6. Chunked neural Kokoro-82M synthesis into 'outputs/sample_note_dictation.wav'
"""

import os
import sys
import time
import logging
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tts.engine import KokoroClinicalEngine
from tts.preprocessor import ClinicalTextPreprocessor
from tts.sinks import WavFileSink

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("generate_sample_note")


def main():
    note_path = project_root / "sample note.md"
    if not note_path.exists():
        logger.error(f"Sample note not found at {note_path}")
        sys.exit(1)

    with open(note_path, "r", encoding="utf-8") as f:
        raw_note = f.read()

    logger.info(f"Loaded 'sample note.md' ({len(raw_note)} characters, {len(raw_note.splitlines())} lines).")

    # 1. Preprocess the clinical note for oral dictation
    preprocessor = ClinicalTextPreprocessor(explicit_punctuation=True, spell_ambiguities=True)
    oral_script = preprocessor.preprocess(raw_note)

    outputs_dir = project_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Save the generated script for inspection
    script_path = outputs_dir / "sample_note_oral_script.txt"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(oral_script)
    logger.info(f"Saved oral dictation script to: {script_path}")

    # 2. Synthesize using KokoroClinicalEngine
    engine = KokoroClinicalEngine.get_instance()
    logger.info(f"Synthesizing audio on device: {engine.device} with voice preset: am_adam...")

    start_time = time.time()
    audio = engine.synthesize(
        oral_script,
        voice="am_adam",
        speed=1.18,  # Crisp, confident clinical dictation speed
        preprocess=False,  # Already preprocessed

        explicit_punctuation=True
    )
    synth_duration = time.time() - start_time

    audio_duration_sec = len(audio) / engine.sample_rate
    audio_duration_min = audio_duration_sec / 60.0
    rtf = synth_duration / audio_duration_sec if audio_duration_sec > 0 else 0

    # 3. Save WAV file
    output_wav = str(outputs_dir / "sample_note_dictation.wav")
    sink = WavFileSink(output_path=output_wav)
    sink.play(audio, sample_rate=engine.sample_rate)

    file_size_mb = os.path.getsize(output_wav) / (1024 * 1024)

    logger.info("=" * 60)
    logger.info("SYNTHESIS COMPLETE!")
    logger.info(f"Output File:     {output_wav}")
    logger.info(f"File Size:       {file_size_mb:.2f} MB")
    logger.info(f"Audio Duration:  {audio_duration_min:.2f} minutes ({audio_duration_sec:.1f} seconds)")
    logger.info(f"Synthesis Time:  {synth_duration:.2f} seconds")
    logger.info(f"Real-Time Ratio: {rtf:.3f}x ({(1.0/rtf if rtf > 0 else 0):.1f}x faster than real-time)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
