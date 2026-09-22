"""
Widget Configuration & Settings
===============================
Manages user preferences, hotkeys, audio devices, dictation target,
and active STT transcription model.
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


CONFIG_DIR = Path.home() / ".config" / "powerdictate"
CONFIG_FILE = CONFIG_DIR / "widget_config.json"


@dataclass
class WidgetConfig:
    # Primary Dictation Hotkey (Right Control / F8)
    hotkey: str = "ctrl_r"
    hotkey_mode: str = "toggle"  # "toggle" or "ptt"
    
    # Audio settings
    sample_rate: int = 16000
    audio_device: Optional[str] = None
    
    # Dictation target: "cursor" (direct in-window typing) or "box" (Dragon-style dictation box)
    dictation_target: str = "cursor"

    # STT Model: "whisper_large_v3_turbo", "google_medasr", "onnx_conformer"
    stt_model: str = "whisper_large_v3_turbo"

    @classmethod
    def load(cls) -> "WidgetConfig":
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception:
                pass
        cfg = cls()
        cfg.save()
        return cfg

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
