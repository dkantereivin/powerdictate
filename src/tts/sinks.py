"""
Decoupled Audio Output Sinks
============================
Provides interchangeable audio destinations for synthesized clinical speech:
1. LocalSpeakerSink: Playback to room / headphones via sounddevice.
2. FileAudioSink: High-fidelity file persistence (24kHz / 16kHz WAV).
3. TelephonyAudioSink: Resampled 8000 Hz 16-bit Mono PCM (G.711u standard) for PBX / SIP.
4. VirtualMicSink: Streams to virtual loopback / microphone devices for mobile app / phone injection.
5. MultiSink: Broadcasts to multiple active sinks concurrently.
"""

import os
import io
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

import numpy as np
import soundfile as sf

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except Exception:
    HAS_SOUNDDEVICE = False

try:
    from scipy.signal import resample_poly
    HAS_SCIPY = True
except Exception:
    HAS_SCIPY = False


class AudioSink(ABC):
    """Abstract Base Class for all audio destinations."""

    @abstractmethod
    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """
        Receives raw floating-point audio numpy array (typically [-1.0, 1.0])
        and routes it to the specific sink.
        """
        pass

    def close(self):
        """Cleanup resources if necessary."""
        pass


class LocalSpeakerSink(AudioSink):
    """Plays audio directly to room speakers / headphones."""

    def __init__(self, device: Optional[Union[int, str]] = None, blocking: bool = True, volume: float = 1.0):
        if not HAS_SOUNDDEVICE:
            raise RuntimeError("sounddevice is not available. Install it via pip install sounddevice.")
        self.device = device
        self.blocking = blocking
        self.volume = max(0.0, min(2.0, volume))

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> None:
        if audio is None or len(audio) == 0:
            return

        play_audio = audio * self.volume
        sd.play(play_audio, samplerate=sample_rate, device=self.device)
        if self.blocking:
            sd.wait()

    def stop(self):
        """Interrupts playback."""
        if HAS_SOUNDDEVICE:
            sd.stop()


class FileAudioSink(AudioSink):
    """Saves synthesized audio to a file on disk."""

    def __init__(self, output_path: Union[str, Path], subtype: str = "PCM_16"):
        self.output_path = Path(output_path)
        self.subtype = subtype

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> Path:
        if audio is None or len(audio) == 0:
            raise ValueError("No audio data provided to FileAudioSink.")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(self.output_path), audio, sample_rate, subtype=self.subtype)
        return self.output_path


class TelephonyAudioSink(AudioSink):
    """
    Resamples audio to 8000 Hz 16-bit Mono PCM (G.711u / PBX telephone standard)
    and saves to file or returns PCM byte buffer.
    """

    def __init__(self, output_path: Optional[Union[str, Path]] = None, target_sample_rate: int = 8000):
        self.output_path = Path(output_path) if output_path else None
        self.target_sample_rate = target_sample_rate

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> Union[Path, bytes]:
        if audio is None or len(audio) == 0:
            raise ValueError("No audio data provided to TelephonyAudioSink.")

        # Ensure mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Resample to 8000 Hz
        if sample_rate != self.target_sample_rate:
            if HAS_SCIPY:
                # Fast polyphase resampler: gcd reduction
                import math
                gcd = math.gcd(sample_rate, self.target_sample_rate)
                up = self.target_sample_rate // gcd
                down = sample_rate // gcd
                resampled = resample_poly(audio, up, down)
            else:
                num_target_samples = int(len(audio) * self.target_sample_rate / sample_rate)
                resampled = np.interp(
                    np.linspace(0, len(audio), num_target_samples, endpoint=False),
                    np.arange(len(audio)),
                    audio
                )
        else:
            resampled = audio

        # Clip and convert to 16-bit integer PCM
        resampled = np.clip(resampled, -1.0, 1.0)

        if self.output_path:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(self.output_path), resampled, self.target_sample_rate, subtype="PCM_16")
            return self.output_path
        else:
            buffer = io.BytesIO()
            sf.write(buffer, resampled, self.target_sample_rate, format="WAV", subtype="PCM_16")
            return buffer.getvalue()


class VirtualMicSink(AudioSink):
    """
    Streams audio to a virtual microphone / loopback audio device or FIFO pipe
    so external apps (Fluency Mobile, phone connected via USB/audio jack) receive
    the synthesized voice as a live microphone input.
    """

    def __init__(self, virtual_device_name: Optional[str] = "VirtualMic", fifo_path: Optional[Union[str, Path]] = None):
        self.virtual_device_name = virtual_device_name
        self.fifo_path = Path(fifo_path) if fifo_path else None
        self._fifo_handle = None

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> None:
        if audio is None or len(audio) == 0:
            return

        # If a FIFO pipe is specified, write raw 16-bit PCM bytes to it
        if self.fifo_path:
            if not self.fifo_path.exists():
                os.mkfifo(str(self.fifo_path))
            
            pcm_16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            with open(self.fifo_path, "wb") as f:
                f.write(pcm_16.tobytes())
            return

        # If sounddevice is available, route to the designated virtual output device
        if HAS_SOUNDDEVICE:
            devices = sd.query_devices()
            target_id = None
            if self.virtual_device_name:
                for idx, dev in enumerate(devices):
                    if self.virtual_device_name.lower() in dev["name"].lower() and dev["max_output_channels"] > 0:
                        target_id = idx
                        break
            
            sd.play(audio, samplerate=sample_rate, device=target_id)
            sd.wait()


class MultiSink(AudioSink):
    """Broadcasts audio to multiple audio sinks concurrently."""

    def __init__(self, sinks: List[AudioSink]):
        self.sinks = sinks

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> List[Any]:
        results = []
        for sink in self.sinks:
            res = sink.emit(audio, sample_rate, metadata)
            results.append(res)
        return results

    def close(self):
        for sink in self.sinks:
            sink.close()
