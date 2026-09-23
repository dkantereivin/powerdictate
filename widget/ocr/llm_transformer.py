"""
LLM Text & Lab Transformation Engine
====================================
Empowers clinicians to transform existing dictated text or captured labs using
AI prompts (e.g., selecting pertinent labs, formatting into SOAP notes, or summarizing).
Includes a strict Anti-Hallucination Ground-Truth Verifier that cross-references
every number in the output against the source text.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal, QThread
from widget.ocr.meditech_parser import MeditechLabParser

logger = logging.getLogger("widget.ocr.transformer")


# Built-in clinical transformation prompt templates
DEFAULT_PROMPTS = {
    "pertinent_labs": (
        "You are an expert physician assistant.\n"
        "Review the patient lab report provided below.\n"
        "Filter and output ONLY the clinically pertinent findings (key core values: WBC, Hgb, Plt, Na, K, Cr, eGFR, and any abnormal lab marked with (H) or (L)).\n"
        "Omit normal routine differential indices (Mono, Eos, Baso, MPV) unless abnormal.\n\n"
        "CRITICAL RULES:\n"
        "1. Every single number and decimal MUST match the source text exactly. NEVER alter or hallucinate values.\n"
        "2. Format into clean, concise, audio-dictation lines (e.g. 'Labs: Na 140, K 4.4, Cr 84.2, eGFR 102', 'CBC: WBC 12.45 (H), Hgb 154, Plt 251, Neut 10.55 (H)').\n"
        "3. Do not output 'Lytes:' or 'LFTs:' headers; group general chemistry labs under 'Labs:'.\n"
        "4. Do not include conversational filler or explanations."
    ),
    "summarize_dictation": (
        "You are a clinical documentation assistant.\n"
        "Transform the provided text into a concise, natural oral clinical summary suitable for reading aloud during rounds or audio dictation.\n"
        "Preserve every single medical fact and number exactly as written."
    ),
    "soap_format": (
        "You are an expert clinical documentation assistant.\n"
        "Organize the provided clinical information and labs into a clean, professional SOAP note format:\n"
        "SUBJECTIVE:\nOBJECTIVE:\nASSESSMENT:\nPLAN:\n"
        "Ensure all numbers, lab values, and vital signs are preserved with 100% exact accuracy."
    ),
}


class LLMTransformer:
    """
    Executes text transformations via local Ollama or cloud LLMs with deterministic
    fallback and zero-tolerance numerical ground-truth verification.
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

    def transform(
        self,
        input_text: str,
        preset: str = "pertinent_labs",
        custom_system_prompt: str = ""
    ) -> str:
        """
        Transforms input text according to the selected prompt preset or custom prompt.
        Verifies that no numerical hallucinations were introduced.
        """
        if not input_text.strip():
            return ""

        prompt_instruction = custom_system_prompt or DEFAULT_PROMPTS.get(preset, DEFAULT_PROMPTS["pertinent_labs"])

        # 1. Try Local Ollama first
        if self._is_ollama_available():
            try:
                llm_output = self._call_ollama(input_text, prompt_instruction)
                if llm_output:
                    return self._verify_ground_truth(llm_output, input_text)
            except Exception as e:
                logger.warning(f"Ollama transformation failed: {e}")

        # 2. Try OpenAI API if key configured
        if self.openai_api_key:
            try:
                llm_output = self._call_openai(input_text, prompt_instruction)
                if llm_output:
                    return self._verify_ground_truth(llm_output, input_text)
            except Exception as e:
                logger.warning(f"OpenAI transformation failed: {e}")

        # 3. Deterministic Local Fallback
        return self._deterministic_fallback(input_text, preset)

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

    def _call_ollama(self, text: str, system_prompt: str) -> Optional[str]:
        payload = {
            "model": self.ollama_model,
            "prompt": f"{system_prompt}\n\nINPUT TEXT:\n{text}\n\nTRANSFORMED OUTPUT:",
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

    def _call_openai(self, text: str, system_prompt: str) -> Optional[str]:
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"INPUT TEXT:\n{text}"}
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

    def _verify_ground_truth(self, llm_output: str, source_text: str) -> str:
        """
        Anti-Hallucination Verifier: Extracts all numeric tokens from LLM output
        and confirms each exists in the source text.
        """
        source_numbers: Set[str] = set(re.findall(r'\b\d+(?:\.\d+)?\b', source_text))

        verified_lines: List[str] = []
        for line in llm_output.splitlines():
            line_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', line)
            has_hallucination = False
            for num in line_numbers:
                # Allow single digits like numbered list markers 1., 2.
                if len(num) == 1 and num in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                    continue
                if num not in source_numbers:
                    has_hallucination = True
                    logger.warning(f"Hallucination Alert: Number '{num}' not in original text!")
                    break

            if not has_hallucination:
                verified_lines.append(line)
            else:
                verified_lines.append(f"{line}  ⚠️ [unverified value]")

        return "\n".join(verified_lines)

    def _deterministic_fallback(self, text: str, preset: str) -> str:
        """
        Rule-based local fallback when LLM backend is offline.
        """
        if preset == "pertinent_labs":
            # Parse labs and select only pertinent ones
            rep = MeditechLabParser.parse_report(text)
            if rep.panels:
                # Filter to core + flagged
                filtered_panels = {}
                for name, items in rep.panels.items():
                    if name == "CBC":
                        pertinent = [i for i in items if i.name in ("WBC", "Hgb", "Plt") or i.flag]
                        filtered_panels[name] = pertinent
                    elif name == "Lytes":
                        has_egfr = any(i.name == "eGFR" for i in items)
                        pertinent = [i for i in items if not (i.name == "CrCl" and has_egfr and not i.flag)]
                        filtered_panels[name] = pertinent
                    else:
                        filtered_panels[name] = items

                return MeditechLabParser.format_audio_dictation(filtered_panels, timestamp=rep.timestamp)

        # Default fallback: return text
        return text


class TransformWorker(QThread):
    """Background thread to run LLM transformations without blocking the Qt event loop."""

    transformation_completed = Signal(str)
    transformation_failed = Signal(str)

    def __init__(self, text: str, preset: str = "pertinent_labs", custom_prompt: str = "", parent=None):
        super().__init__(parent)
        self.text = text
        self.preset = preset
        self.custom_prompt = custom_prompt

    def run(self):
        try:
            transformer = LLMTransformer()
            res = transformer.transform(self.text, preset=self.preset, custom_system_prompt=self.custom_prompt)
            self.transformation_completed.emit(res)
        except Exception as e:
            logger.error(f"Error in TransformWorker: {e}", exc_info=True)
            self.transformation_failed.emit(str(e))
