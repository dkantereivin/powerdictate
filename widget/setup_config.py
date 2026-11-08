"""
Dictation Setup Configuration Manager
=====================================
Manages settings from 'setup.yaml' including physician introduction, outro,
hospital phone number, provider number, site number, work type, voip.ms SIP
credentials, and standardized call flow templates.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import yaml

from tts.preprocessor import spell_out_word


# Default setup path points to project root 'setup.yaml' or fallback ~/.config/powerdictate/setup.yaml
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETUP_PATH = PROJECT_ROOT / "setup.yaml"
USER_CONFIG_PATH = Path.home() / ".config" / "powerdictate" / "setup.yaml"


DEFAULT_CALL_FLOW = [
    {"action": "dial", "number": "{{hospital_phone_number}}"},
    {"action": "wait", "seconds": 3.0},
    {"action": "dtmf", "tones": "{{provider_number}}#"},
    {"action": "wait", "seconds": 2.0},
    {"action": "dtmf", "tones": "{{site_number}}#"},
    {"action": "wait", "seconds": 2.0},
    {"action": "dtmf", "tones": "{{work_type}}#"},
    {"action": "wait", "seconds": 2.0},
    {"action": "dtmf", "tones": "{{patient_mrn}}#"},
    {"action": "wait", "seconds": 2.0},
    {"action": "dictate_now"},
    {"action": "wait", "seconds": 1.0},
    {"action": "dtmf", "tones": "#"},
    {"action": "wait", "seconds": 1.0},
    {"action": "hangup"}
]


@dataclass
class DictationSetupConfig:
    # Clinician Identifiers
    introduction: str = "This is David Kanter Eivin PGY1, dictating on behalf of DR. XXAM, MCTU Staff"
    outro: str = "Thank you. End of dictation."

    # Hospital Telephony Line & Identity
    hospital_phone_number: str = "18005551234"
    provider_number: str = "6740"
    site_number: str = "01"
    work_type: str = "001"

    # VoIP.ms SIP Trunking Credentials
    voip_provider: str = "voip.ms"
    voip_server: str = "toronto.voip.ms"
    voip_username: str = ""
    voip_password: str = ""
    voip_port: int = 5060
    voip_caller_id: str = ""

    # Call Flow Template Sequence
    call_sequence_summary: str = (
        "dial {{hospital_phone_number}} --> wait 3s --> DTMF tones {{provider_number}}# "
        "--> {{site_number}}# --> {{work_type}}# --> {{patient_mrn}}# --> DICTATE NOW --> #"
    )
    call_flow_template: List[Dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_CALL_FLOW))

    # Submission Channel & Device Gateway
    submission_channel: str = "voip"  # "voip" or "bluetooth"
    bluetooth_device_name: str = "Pixel 7 Pro DK"
    bluetooth_device_mac: str = "D4:3A:2C:A5:93:9D"

    # Security & Export Settings
    encryption_key: str = "pd_sec_key_placeholder_change_in_production"
    default_output_option: str = "dial"
    listen_in_real_time: bool = True
    tts_voice: str = "am_adam"
    tts_speed: float = 1.18
    output_dir: str = "outputs"

    @classmethod
    def get_config_path(cls) -> Path:
        """Finds active setup.yaml file path."""
        if DEFAULT_SETUP_PATH.exists():
            return DEFAULT_SETUP_PATH
        if USER_CONFIG_PATH.exists():
            return USER_CONFIG_PATH
        return DEFAULT_SETUP_PATH

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "DictationSetupConfig":
        """Loads configuration from yaml file."""
        config_path = path or cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                valid_keys = {f for f in cls.__dataclass_fields__}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                # Ensure call_flow_template defaults if empty
                if not filtered.get("call_flow_template"):
                    filtered["call_flow_template"] = list(DEFAULT_CALL_FLOW)
                return cls(**filtered)
            except Exception:
                pass
        cfg = cls()
        cfg.save(config_path)
        return cfg

    def save(self, path: Optional[Path] = None) -> None:
        """Saves configuration to yaml file."""
        config_path = path or self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(asdict(self), f, sort_keys=False, default_flow_style=False)

    def get_provider_dtmf_sequence(self) -> str:
        """Returns the DTMF sequence for the provider ID (e.g. '6740#')."""
        num = (self.provider_number or "").strip()
        if not num.endswith("#"):
            return f"{num}#"
        return num

    def format_patient_preamble(self, patient_name: str, mrn: str) -> str:
        """
        Formats patient identification for telephone dictation:
        - Patient name is spelled out letter-by-letter for transcription clarity.
        - MRN digits are articulated individually.
        """
        parts = []
        name = (patient_name or "").strip()
        if name:
            words = name.split()
            spelled_tokens = []
            for w in words:
                cleaned = "".join(c for c in w if c.isalpha())
                if cleaned:
                    spelled_tokens.append(spell_out_word(cleaned))
            spelled_full = " space ".join(spelled_tokens) if spelled_tokens else name
            parts.append(f"Patient name: {name}, spelled {spelled_full}.")

        mrn_clean = (mrn or "").strip()
        if mrn_clean:
            digits = " ".join(c for c in mrn_clean if c.isalnum())
            parts.append(f"Medical Record Number: {digits}.")

        return " ".join(parts)

    def resolve_call_flow(
        self,
        patient_name: str = "",
        mrn: str = "",
        work_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Substitutes standardized variables in call_flow_template:
          {{hospital_phone_number}}
          {{provider_number}}
          {{site_number}}
          {{work_type}}
          {{patient_mrn}} / {{mrn}}
          {{patient_name}}
        Returns an executable list of step dictionaries.
        """
        active_work_type = (work_type or self.work_type or "001").strip()
        active_mrn = (mrn or "").strip()
        active_name = (patient_name or "").strip()

        # Variable replacement dictionary
        vars_map = {
            "hospital_phone_number": self.hospital_phone_number or "18005551234",
            "provider_number": self.provider_number or "6740",
            "site_number": self.site_number or "01",
            "work_type": active_work_type,
            "patient_mrn": active_mrn,
            "mrn": active_mrn,
            "patient_name": active_name,
        }

        def _substitute(val: Any) -> Any:
            if not isinstance(val, str):
                return val
            res = val
            for k, v in vars_map.items():
                pattern = r'\{\{\s*' + re.escape(k) + r'\s*\}\}'
                res = re.sub(pattern, str(v), res)
            return res

        resolved_steps = []
        raw_steps = self.call_flow_template or DEFAULT_CALL_FLOW
        for step in raw_steps:
            resolved_step = {}
            for k, v in step.items():
                resolved_step[k] = _substitute(v)
            resolved_steps.append(resolved_step)

        return resolved_steps
