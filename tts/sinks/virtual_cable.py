"""
Virtual Cable / Telephone Submission Audio Sink (Scaffold)
==========================================================
Scaffolds PipeWire / PulseAudio virtual mic loopback routing for submitting
dictations directly into hospital softphones (Cisco Jabber, Teams, WebRTC).
"""

import shutil
import logging
import subprocess
from typing import Optional
import numpy as np
import sounddevice as sd
from tts.sinks.base import BaseAudioSink

logger = logging.getLogger("tts.sinks.virtual_cable")


class VirtualCableSink(BaseAudioSink):
    """
    Scaffold for routing synthesized audio directly into a virtual microphone
    device on Linux (via PipeWire / PulseAudio pactl loopback).
    """

    def __init__(self, sink_name: str = "PowerDictateSink", remap_source: str = "PowerDictateMic"):
        self.sink_name = sink_name
        self.remap_source = remap_source
        self._sink_module_id: Optional[str] = None
        self._source_module_id: Optional[str] = None
        self._is_active = False

    def is_pactl_available(self) -> bool:
        """Returns True if pactl (PulseAudio/PipeWire CLI) is installed."""
        return shutil.which("pactl") is not None

    def setup_virtual_devices(self) -> bool:
        """
        Creates a null-sink and remap-source on PipeWire/PulseAudio:
        1. pactl load-module module-null-sink sink_name=PowerDictateSink
        2. pactl load-module module-remap-source master=PowerDictateSink.monitor source_name=PowerDictateMic
        """
        if not self.is_pactl_available():
            logger.warning("pactl is not installed; cannot automatically create virtual mic.")
            return False

        try:
            # 1. Create null-sink
            res1 = subprocess.run(
                [
                    "pactl", "load-module", "module-null-sink",
                    f"sink_name={self.sink_name}",
                    f"sink_properties=device.description=PowerDictate_Virtual_Audio"
                ],
                capture_output=True, text=True, check=True
            )
            self._sink_module_id = res1.stdout.strip()

            # 2. Remap to virtual microphone input
            res2 = subprocess.run(
                [
                    "pactl", "load-module", "module-remap-source",
                    f"master={self.sink_name}.monitor",
                    f"source_name={self.remap_source}",
                    f"source_properties=device.description=PowerDictate_Dictation_Mic"
                ],
                capture_output=True, text=True, check=True
            )
            self._source_module_id = res2.stdout.strip()
            logger.info(f"Virtual microphone created: '{self.remap_source}' (sink={self.sink_name})")
            return True
        except Exception as e:
            logger.error(f"Failed to create virtual audio cable: {e}")
            return False

    def cleanup_virtual_devices(self) -> None:
        """Unloads created PulseAudio/PipeWire modules."""
        for mod_id in (self._source_module_id, self._sink_module_id):
            if mod_id:
                try:
                    subprocess.run(["pactl", "unload-module", mod_id], capture_output=True)
                except Exception:
                    pass
        self._source_module_id = None
        self._sink_module_id = None

    def play(self, audio: np.ndarray, sample_rate: int = 24000) -> None:
        """Plays audio to the virtual sink device."""
        if audio is None or len(audio) == 0:
            return

        # Scaffold: find device index matching sink_name or use default
        try:
            self._is_active = True
            sd.play(audio, samplerate=sample_rate)
            logger.info(f"Routed {len(audio) / sample_rate:.2f}s audio to VirtualCableSink.")
        except Exception as e:
            self._is_active = False
            logger.error(f"Error playing to virtual cable sink: {e}")
            raise

    def stop(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass
        finally:
            self._is_active = False

    def is_playing(self) -> bool:
        return self._is_active
