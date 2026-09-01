"""
Option A: Smartphone Cellular Audio Injection Sink
===================================================
Transmits synthesized dictation and IVR DTMF tones directly into an active
cellular phone call placed on a connected smartphone (via Bluetooth HFP Headset,
USB-C Audio Gadget, or 3.5mm TRRS Headset Cable).
"""

from typing import Optional, Dict, Any, Union
from pathlib import Path
import numpy as np
import soundfile as sf

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

from src.tts.sinks import AudioSink
from src.telephony.dtmf import DTMFGenerator


class SmartphoneAudioSink(AudioSink):
    """
    Audio sink that streams DTMF navigation tones followed by the 8kHz dictation
    speech directly into a connected smartphone cellular call.
    """

    def __init__(
        self,
        output_device: Optional[Union[int, str]] = None,
        volume: float = 1.0,
        include_dtmf_header: bool = True,
        initial_wait: float = 2.0,
        inter_step_wait: float = 2.0,
        pre_speech_wait: float = 3.0,
        save_disconnect_key: str = "8"
    ):
        self.output_device = output_device
        self.volume = max(0.0, min(2.0, volume))
        self.include_dtmf_header = include_dtmf_header
        self.initial_wait = initial_wait
        self.inter_step_wait = inter_step_wait
        self.pre_speech_wait = pre_speech_wait
        self.save_disconnect_key = save_disconnect_key
        self.dtmf_gen = DTMFGenerator(sample_rate=8000)

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> np.ndarray:
        if audio is None or len(audio) == 0:
            return np.array([], dtype=np.float32)

        meta = metadata or {}
        provider_id = meta.get("provider_id", "")
        work_type = meta.get("work_type", "01")
        mrn = meta.get("mrn", "")

        # Resample to 8000 Hz if necessary
        if sample_rate != 8000:
            from scipy.signal import resample_poly
            import math
            gcd = math.gcd(sample_rate, 8000)
            speech_8k = resample_poly(audio, 8000 // gcd, sample_rate // gcd).astype(np.float32)
        else:
            speech_8k = audio.astype(np.float32)

        if self.include_dtmf_header and provider_id and mrn:
            final_payload = self.dtmf_gen.generate_ivr_payload(
                provider_id=provider_id,
                work_type=work_type,
                mrn=mrn,
                dictation_audio=speech_8k,
                dictation_sr=8000,
                initial_wait=self.initial_wait,
                inter_step_wait=self.inter_step_wait,
                pre_speech_wait=self.pre_speech_wait,
                save_disconnect_key=self.save_disconnect_key
            )
        else:
            final_payload = speech_8k

        # Play to the designated smartphone output device if sounddevice is active
        if HAS_SOUNDDEVICE:
            dev_id = self._resolve_device(self.output_device)
            sd.play(final_payload * self.volume, samplerate=8000, device=dev_id)
            sd.wait()

        return final_payload

    def dial_dtmf_digits_only(self, digits: str) -> None:
        """Plays only a specific DTMF sequence (e.g. for interactive IVR steps)."""
        tones = self.dtmf_gen.generate_digit_sequence(digits)
        if HAS_SOUNDDEVICE and len(tones) > 0:
            dev_id = self._resolve_device(self.output_device)
            sd.play(tones * self.volume, samplerate=8000, device=dev_id)
            sd.wait()

    def _resolve_device(self, dev_spec: Optional[Union[int, str]]) -> Optional[int]:
        """Finds matching sounddevice ID for Bluetooth or USB Audio."""
        if not HAS_SOUNDDEVICE or dev_spec is None:
            return None
        if isinstance(dev_spec, int):
            return dev_spec

        devices = sd.query_devices()
        for idx, d in enumerate(devices):
            if dev_spec.lower() in d["name"].lower() and d["max_output_channels"] > 0:
                return idx
        return None
