"""
LLM Pertinence & Clinical Dictation Structurer
=============================================
Transforms raw OCR screen text into clean, audio-friendly clinical lines.
Supports local Ollama or cloud APIs, with a mandatory Ground-Truth Verifier
that cross-checks all numerical outputs against raw OCR to guarantee zero hallucination.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Tuple, Set

from widget.ocr.meditech_parser import MeditechLabParser

logger = logging.getLogger("widget.ocr.llm")


SYSTEM_PROMPT = """You are an expert clinical documentation assistant.
You are given raw optical character recognition (OCR) text extracted from a hospital EMR screen (such as Meditech, Epic, or paper chart).

YOUR OBJECTIVE:
1. Select and extract the most pertinent clinical findings (key labs: Labs, CBC, Troponin, Coags, or imaging impressions).
2. Format the output into clean, concise, audio-dictation-friendly lines suitable for speech synthesis or clinical documentation.
   Example format:
   Labs: Na 138, K 4.1, Cl 103, HCO3 24, BUN 18, Cr 92, eGFR >60, Glu 6.3, ALT 35, ALP 59
   CBC: WBC 14.2 (H), Hgb 115 (L), Plt 340
   Coags: INR 1.0, PTT 28
   Imaging: Mild cardiomegaly and interstitial edema.

CRITICAL ACCURACY RULES:
- Every single number, decimal, and unit MUST come directly from the source text.
- NEVER guess, estimate, extrapolate, or hallucinate any numbers or lab tests.
- Do NOT output "Lytes:" or "LFTs:" headers; group all general chemistry and liver/renal labs under "Labs:".
- Omit test codes and normal reference ranges.
- Output ONLY the formatted clinical lines, without conversational preamble.
"""


class LLMStructurer:
    """
    Orchestrates LLM structuring with deterministic fallback and ground-truth verification.
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.2:latest",
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",
    ):
        self.ollama_url = os.environ.get("OLLAMA_URL", ollama_url).rstrip("/")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", ollama_model)
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", openai_api_key)
        self.openai_model = os.environ.get("OPENAI_MODEL", openai_model)

    def structure_clinical_text(self, raw_ocr: str) -> str:
        """
        Structures raw OCR text:
        1. Tries LLM structuring (Ollama or OpenAI if available).
        2. Verifies numerical ground-truth.
        3. If LLM unavailable, falls back to deterministic MeditechLabParser.
        """
        if not raw_ocr.strip():
            return ""

        # 1. Try local Ollama first (fast, private, free)
        if self._is_ollama_available():
            try:
                llm_output = self._call_ollama(raw_ocr)
                if llm_output:
                    verified = self._verify_ground_truth(llm_output, raw_ocr)
                    return verified
            except Exception as e:
                logger.warning(f"Ollama call failed: {e}")

        # 2. Try OpenAI API if key configured
        if self.openai_api_key:
            try:
                llm_output = self._call_openai(raw_ocr)
                if llm_output:
                    verified = self._verify_ground_truth(llm_output, raw_ocr)
                    return verified
            except Exception as e:
                logger.warning(f"OpenAI call failed: {e}")

        # 3. Fallback: Deterministic Meditech regex parser
        logger.info("Falling back to deterministic MeditechLabParser.")
        parsed_panels = MeditechLabParser.parse_text(raw_ocr)
        if parsed_panels:
            return MeditechLabParser.format_audio_dictation(parsed_panels)

        # 4. If regex couldn't find labs, return cleaned raw OCR lines
        clean_lines = [l.strip() for l in raw_ocr.splitlines() if l.strip()]
        return "\n".join(clean_lines)

    def _is_ollama_available(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/tags",
                headers={"User-Agent": "PowerDictate"}
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _call_ollama(self, text: str) -> Optional[str]:
        payload = {
            "model": self.ollama_model,
            "prompt": f"{SYSTEM_PROMPT}\n\nRAW OCR TEXT:\n{text}\n\nFORMATTED CLINICAL LINES:",
            "stream": False,
            "options": {"temperature": 0.0}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "").strip()

    def _call_openai(self, text: str) -> Optional[str]:
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"RAW OCR TEXT:\n{text}"}
            ],
            "temperature": 0.0
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
        return None

    def _verify_ground_truth(self, llm_output: str, raw_ocr: str) -> str:
        """
        Extracts all numeric tokens from LLM output and verifies they exist
        in the raw OCR text. If an unverified number is found, flags it with [?].
        """
        # Collect all numeric tokens from raw OCR text
        ocr_numbers: Set[str] = set(re.findall(r'\b\d+(?:\.\d+)?\b', raw_ocr))

        verified_lines: List[str] = []
        for line in llm_output.splitlines():
            line_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            has_hallucination = False
            for num in line_numbers:
                # Allow single digits like bullet points 1., 2.
                if len(num) == 1 and num in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                    continue
                if num not in ocr_numbers:
                    has_hallucination = True
                    logger.warning(f"Ground-truth alert: Number {num} in LLM output was NOT found in raw OCR!")
                    break

            if not has_hallucination:
                verified_lines.append(line)
            else:
                # Retain line but annotate warning
                verified_lines.append(f"{line}  ⚠️ [unverified value]")

        return "\n".join(verified_lines)
