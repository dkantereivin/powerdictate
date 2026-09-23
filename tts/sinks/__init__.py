"""
Audio Sinks Package
===================
Exports default PC speaker, WAV file, and virtual cable audio sinks.
"""

from tts.sinks.base import BaseAudioSink
from tts.sinks.speaker import DefaultSpeakerSink
from tts.sinks.wav_file import WavFileSink
from tts.sinks.virtual_cable import VirtualCableSink

__all__ = [
    "BaseAudioSink",
    "DefaultSpeakerSink",
    "WavFileSink",
    "VirtualCableSink",
]
