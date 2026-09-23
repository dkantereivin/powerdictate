"""
Clinical TTS CLI & Testing Tool
===============================
Direct command-line tool to test Kokoro medical dictation synthesis,
transcriptionist name spelling, lab expansions, and live audio playback.

Usage examples:
    python -m tts.cli "Patient seen by Dr. Vandermeer for chest pain. BP 138/84. Labs: Na 140, K 4.4, Cr 84.2."
    python -m tts.cli --voice michael --output outputs/demo.wav "Patient admitted under Dr. Kaczynski."
"""

import sys
import argparse
import logging
from tts.engine import KokoroClinicalEngine
from tts.presets import CLINICAL_VOICE_PRESETS, DEFAULT_VOICE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tts.cli")


def main():
    parser = argparse.ArgumentParser(description="PowerDictate Kokoro Clinical Text-to-Speech")
    parser.add_argument("text", nargs="?", help="Clinical text to synthesize")
    parser.add_argument("--voice", "-v", default=DEFAULT_VOICE, choices=list(CLINICAL_VOICE_PRESETS.keys()) + [p.id for p in CLINICAL_VOICE_PRESETS.values()], help="Voice preset or ID")
    parser.add_argument("--speed", "-s", type=float, default=1.0, help="Speech speed multiplier (0.8 - 1.3)")
    parser.add_argument("--play", "-p", action="store_true", default=True, help="Play output live to default sound device")
    parser.add_argument("--no-play", action="store_false", dest="play", help="Do not play audio to speakers")
    parser.add_argument("--output", "-o", help="Save synthesized audio to WAV file path")
    parser.add_argument("--explicit-punct", action="store_true", help="Speak explicit punctuation ('period', 'comma', 'new paragraph')")
    parser.add_argument("--llm", action="store_true", help="Use local LLM (Ollama) to detect and spell ambiguous proper nouns")

    args = parser.parse_args()

    sample_text = (
        args.text or
        "Patient John Kaczynski was evaluated by Dr. Vandermeer at Tillsonburg Memorial Hospital. "
        "He reports persistent dyspnea and pruritus. "
        "Vital signs: BP 138/82, HR 74, SpO2 96% on room air, Temp 37.1 C. "
        "Labs (1/11/25 08:03): Na 140, K 4.4, Cl 105, HCO3 27, BUN 8.6 (H), Cr 84.2, eGFR 102, Glu 6.3. "
        "Plan: Start metoprolol 25 mg PO BID and ceftriaxone 1 g IV daily."
    )

    engine = KokoroClinicalEngine.get_instance()

    print("\n" + "="*70)
    print(" 🏥 PowerDictate Clinical Text-to-Speech (Kokoro-82M)")
    print("="*70)
    print(f"• Input Text:\n  {sample_text}\n")

    preprocessed = engine.preprocess_text(
        sample_text,
        use_llm=args.llm,
        explicit_punctuation=args.explicit_punct
    )
    print(f"• Preprocessed Script (with transcriptionist spelling & medical dictionary):\n  {preprocessed}\n")

    if args.output:
        print(f"• Generating and saving to WAV: {args.output}...")
        saved_file = engine.synthesize_to_file(
            sample_text,
            output_path=args.output,
            voice=args.voice,
            speed=args.speed,
            use_llm=args.llm,
            explicit_punctuation=args.explicit_punct
        )
        print(f"✓ Saved WAV audio to: {saved_file}")

    if args.play:
        print(f"• Synthesizing and playing live through default sound device (voice={args.voice}, speed={args.speed})...")
        engine.synthesize_and_play(
            sample_text,
            voice=args.voice,
            speed=args.speed,
            wait=True,
            use_llm=args.llm,
            explicit_punctuation=args.explicit_punct
        )
        print("✓ Playback finished.")

    print("="*70 + "\n")


if __name__ == "__main__":
    main()
