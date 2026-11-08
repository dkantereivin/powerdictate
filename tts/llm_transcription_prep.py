"""
LLM-Assisted Transcriptionist Preparation & Ambiguity Detector
==============================================================
Uses local Ollama or cloud LLMs to identify ambiguous proper nouns (physician names,
patient names, specific clinics, facilities) and appends transcriptionist spelling
clarifications (e.g., 'Dr. Vandermeer, spelled V A N D E R M E E R').

Leaves standard medications and medical diseases unspelled as they exist in standard
medical transcription dictionaries.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

from tts.preprocessor import ClinicalTextPreprocessor

logger = logging.getLogger("tts.llm_prep")

TRANSCRIPTION_PREP_PROMPT = """You are an expert medical transcription pre-processor.
Your job is to prepare clinical notes to be dictated aloud over the phone to a medical transcriptionist.

CRITICAL RULES:
1. Identify all AMBIGUOUS PROPER NOUNS:
   - Names of individual people (patient names, physician names, family members).
   - Specific clinic, hospital, street, or town names.
   For each ambiguous proper noun, immediately follow it with: ', spelled [L E T T E R S]'
   Example:
   - 'Dr. Vandermeer called' -> 'Dr. Vandermeer, spelled V A N D E R M E E R, called'
   - 'Transferred from Tillsonburg Hospital' -> 'Transferred from Tillsonburg, spelled T I L L S O N B U R G, Hospital'
   - 'Patient John Kaczynski' -> 'Patient John Kaczynski, spelled K A C Z Y N S K I'

2. DO NOT OVER-EXPAND STANDARD MEDICAL ACRONYMS:
   - Acronyms that are standard in written medical notes and obvious to a medical transcriptionist MUST remain as clean abbreviations.
   - Specifically: PO, BID, TID, QID, IV, IM, PRN, QD, COPD, CHF, CKD, AKI, DVT, PE.
   - DO NOT expand 'PO' to 'by mouth' or 'per os'.
   - DO NOT expand 'BID' to 'twice daily'.
   - DO NOT expand 'IV' to 'intravenously'.
   - Keep them as clean abbreviations (e.g. 'PO', 'BID', 'IV') which will be transcribed verbatim.
   - HOWEVER, DO clarify or spell out RARE or AMBIGUOUS clinical acronyms that could be confused with ordinary English words or misheard:
     * 'IN' (intranasal) -> expand or clarify as 'intranasal' so it is not confused with the preposition 'in'.
     * 'IT' (intrathecal) -> 'intrathecal'
     * 'PR' (per rectum) -> 'per rectum'
     * 'SL' (sublingual) -> 'sublingual'

3. CONVERT CLINICAL MEASUREMENT UNITS TO SPOKEN WORDS:
   - Convert dosage units to natural spoken form:
     * '1g' / '1 g' -> '1 gram', '2g' -> '2 grams'
     * '1mg' / '1 mg' -> '1 milligram', '50mg' -> '50 milligrams'
     * '100mcg' -> '100 micrograms'
     * '4 L/min' -> '4 liters per minute'
     * '75 mL/hr' -> '75 milliliters per hour'
     * '104/62 mmHg' -> '104 over 62 millimeters of mercury'
     * '108 bpm' -> '108 beats per minute'
     * '26 breaths/min' -> '26 breaths per minute'
     * '38.6 °C' -> '38.6 degrees Celsius'
     * 'mg/dL' -> 'milligrams per deciliter'
     * 'mmol/L' -> 'millimoles per liter'
   - Speak decimals as 'point' (e.g., '1.4' -> '1 point 4', '8.6' -> '8 point 6').
   - Speak numeric ranges as 'to' (e.g. '1.4-1.6' -> '1 point 4 to 1 point 6').

4. DICTATE ALL PUNCTUATION AND NEWLINES EXPLICITLY:
   - Dictate all punctuation marks aloud: 'period', 'comma', 'colon', 'semicolon', 'open parenthesis', 'close parenthesis', 'quote', 'unquote'.
   - Dictate structural spacing: 'new line' for line breaks, 'new paragraph' for paragraph/section breaks.

5. DO NOT spell out standard drug names (e.g. Ceftriaxone, Atorvastatin, Metoprolol, Furosemide, Piperacillin-Tazobactam) or standard medical diseases (e.g. Cholecystitis, Choledocholithiasis, Diverticulitis, STEMI). Medical transcriptionists already know standard medical vocabulary.
   Only spell out a drug or disease if it is exceptionally obscure, experimental, or ambiguous.

6. PRESERVE ALL CLINICAL FACTS AND NUMBERS with 100% exact accuracy. Never modify, hallucinate, or omit any clinical finding.

7. Output ONLY the processed clinical text, without conversational chatter or introductory remarks.
"""



class LLMTranscriptionPrep:
    """
    Coordinates LLM-based ambiguity spelling with deterministic regex fallback.
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
        self.deterministic_preprocessor = ClinicalTextPreprocessor(spell_ambiguities=True)

    def prepare_text(self, text: str) -> str:
        """
        Processes text for dictation:
        1. Tries LLM ambiguity spelling (Ollama / OpenAI).
        2. Falls back to deterministic preprocessor if LLM is offline.
        3. Runs deterministic clinical normalizer on the result.
        """
        if not text.strip():
            return ""

        prepared_text = ""

        # 1. Try Ollama
        if self._is_ollama_available():
            try:
                res = self._call_ollama(text)
                if res and len(res.strip()) > 5:
                    prepared_text = res.strip()
            except Exception as e:
                logger.warning(f"Ollama transcription prep failed: {e}")

        # 2. Try OpenAI
        if not prepared_text and self.openai_api_key:
            try:
                res = self._call_openai(text)
                if res and len(res.strip()) > 5:
                    prepared_text = res.strip()
            except Exception as e:
                logger.warning(f"OpenAI transcription prep failed: {e}")

        # 3. Fallback to deterministic regex spelling
        if not prepared_text:
            prepared_text = text

        # Always run deterministic normalizer to handle labs, vitals, and medical dictionary
        return self.deterministic_preprocessor.preprocess(prepared_text)

    def _is_ollama_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "PowerDictate"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _call_ollama(self, text: str) -> Optional[str]:
        payload = {
            "model": self.ollama_model,
            "prompt": f"{TRANSCRIPTION_PREP_PROMPT}\n\nCLINICAL NOTE TO DICTATE:\n{text}\n\nPROCESSED DICTATION SCRIPT:",
            "stream": False,
            "options": {"temperature": 0.0}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "").strip()

    def _call_openai(self, text: str) -> Optional[str]:
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": TRANSCRIPTION_PREP_PROMPT},
                {"role": "user", "content": f"CLINICAL NOTE TO DICTATE:\n{text}"}
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
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
        return None
