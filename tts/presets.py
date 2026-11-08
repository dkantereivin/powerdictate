"""
Kokoro Clinical Voice Presets & Configuration
=============================================
Configured voices and speed presets optimized for medical dictation and transcription.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class VoiceProfile:
    id: str
    name: str
    gender: str
    accent: str
    description: str
    recommended_speed: float = 1.18


CLINICAL_VOICE_PRESETS: Dict[str, VoiceProfile] = {
    "adam": VoiceProfile(
        id="am_adam",
        name="Adam",
        gender="Male",
        accent="American",
        description="Crisp, clear clinical cadence. Recommended default for telephone dictation.",
        recommended_speed=1.18,
    ),
    "michael": VoiceProfile(
        id="am_michael",
        name="Michael",
        gender="Male",
        accent="American",
        description="Deep, authoritative, steady pace. Ideal for formal consult notes.",
        recommended_speed=1.18,
    ),
    "sarah": VoiceProfile(
        id="af_sarah",
        name="Sarah",
        gender="Female",
        accent="American",
        description="Neutral, articulate, professional clinical diction.",
        recommended_speed=1.18,
    ),
    "heart": VoiceProfile(
        id="af_heart",
        name="Heart",
        gender="Female",
        accent="American",
        description="Warm, highly expressive, high intelligibility.",
        recommended_speed=1.18,
    ),
    "bella": VoiceProfile(
        id="af_bella",
        name="Bella",
        gender="Female",
        accent="American",
        description="High clarity, fast comprehension.",
        recommended_speed=1.20,
    ),
}

DEFAULT_VOICE = "am_adam"
DEFAULT_SPEED = 1.18
KOKORO_SAMPLE_RATE = 24000

