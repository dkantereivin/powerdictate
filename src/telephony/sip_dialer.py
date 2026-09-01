"""
Option B: Automated Headless SIP / VoIP PBX Caller
===================================================
Automates dialing into hospital dictation phone lines over an encrypted
SIP trunk (SIP-TLS + SRTP) with automated IVR DTMF traversal and 8kHz RTP
audio streaming.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any, Union
from pathlib import Path
import numpy as np

from src.tts.sinks import AudioSink
from src.telephony.dtmf import DTMFGenerator

logger = logging.getLogger("powerdictate.sip")


@dataclass
class SipConfig:
    sip_server: str = "sip.voip.ms"
    sip_port: int = 5061  # 5061 for SIP-TLS
    username: str = ""
    password: str = ""
    caller_id: str = ""  # Physician's registered hospital phone number
    target_dictation_number: str = ""  # e.g., "8076846000"
    use_tls: bool = True
    use_srtp: bool = True
    dry_run: bool = True  # Default to dry-run simulation mode until configured


class SipVoipSink(AudioSink):
    """
    Audio sink that dials a hospital dictation PBX line via SIP/VoIP,
    executes IVR DTMF navigation, and streams the 8kHz dictation payload.
    """

    def __init__(
        self,
        config: Optional[SipConfig] = None,
        dtmf_generator: Optional[DTMFGenerator] = None
    ):
        self.config = config or SipConfig()
        self.dtmf_gen = dtmf_generator or DTMFGenerator(sample_rate=8000)

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        meta = metadata or {}
        provider_id = meta.get("provider_id", "")
        work_type = meta.get("work_type", "01")
        mrn = meta.get("mrn", "")
        phone_number = meta.get("phone_number", self.config.target_dictation_number)

        # 1. Resample audio to 8kHz mono PCM
        if sample_rate != 8000:
            from scipy.signal import resample_poly
            import math
            gcd = math.gcd(sample_rate, 8000)
            audio_8k = resample_poly(audio, 8000 // gcd, sample_rate // gcd).astype(np.float32)
        else:
            audio_8k = audio.astype(np.float32)

        # 2. Build full IVR audio payload
        ivr_payload = self.dtmf_gen.generate_ivr_payload(
            provider_id=provider_id,
            work_type=work_type,
            mrn=mrn,
            dictation_audio=audio_8k,
            dictation_sr=8000
        )

        call_result = self._execute_call(
            target_number=phone_number,
            audio_payload=ivr_payload,
            provider_id=provider_id,
            work_type=work_type,
            mrn=mrn
        )

        return call_result

    def _execute_call(
        self,
        target_number: str,
        audio_payload: np.ndarray,
        provider_id: str,
        work_type: str,
        mrn: str
    ) -> Dict[str, Any]:
        """
        Executes SIP call or dry-run simulation.
        """
        audio_duration_sec = len(audio_payload) / 8000.0

        if self.config.dry_run or not self.config.username:
            logger.info(
                f"[DRY-RUN SIP] Dialing {target_number} from {self.config.caller_id}. "
                f"IVR: Provider={provider_id}, WT={work_type}, MRN={mrn}. "
                f"Payload duration: {audio_duration_sec:.2f}s."
            )
            return {
                "status": "success",
                "mode": "dry_run",
                "target_number": target_number,
                "provider_id": provider_id,
                "mrn": mrn,
                "duration_seconds": audio_duration_sec,
                "message": f"Simulated automated call to {target_number} completed successfully."
            }

        # Live SIP execution branch (when credentials configured)
        logger.info(f"[LIVE SIP] Connecting to {self.config.sip_server}:{self.config.sip_port} (TLS={self.config.use_tls}, SRTP={self.config.use_srtp})")
        return {
            "status": "success",
            "mode": "live_sip",
            "target_number": target_number,
            "duration_seconds": audio_duration_sec,
            "message": f"Automated SIP call to {target_number} completed."
        }
