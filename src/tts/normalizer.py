"""
Clinical Text Normalizer & Pharmacology Preprocessor
====================================================
Transforms clinical notes and consult summaries into pristine spoken English,
supporting both:
1. DICTATION MODE: Optimized for PBX / human hospital transcriptionists
   (spoken punctuation: 'period', 'comma', 'new paragraph', letter spelling).
2. WARD REVIEW MODE: Optimized for direct human listening (natural pauses,
   organic cadence, and clinical expansions).
"""

import re
from enum import Enum
from typing import Optional


class NormalizationMode(str, Enum):
    DICTATION = "dictation"      # For human transcriptionist / PBX telephony
    WARD_REVIEW = "ward_review"  # For direct listening with natural prosody


# Units and clinical routes mappings
ROUTE_EXPANSIONS = {
    r"\bPO\b": "by mouth",
    r"\bP\.O\.\b": "by mouth",
    r"\bIV\b": "intravenously",
    r"\bI\.V\.\b": "intravenously",
    r"\bIM\b": "intramuscularly",
    r"\bI\.M\.\b": "intramuscularly",
    r"\bSC\b": "subcutaneously",
    r"\bSubQ\b": "subcutaneously",
    r"\bS\.C\.\b": "subcutaneously",
    r"\bSL\b": "sublingually",
    r"\bS\.L\.\b": "sublingually",
    r"\bPR\b": "rectally",
    r"\bP\.R\.\b": "rectally",
    r"\bNGT\b": "via nasogastric tube",
    r"\bPEG\b": "via PEG tube",
}

FREQUENCY_EXPANSIONS = {
    r"\bBID\b": "twice daily",
    r"\bB\.I\.D\.\b": "twice daily",
    r"\bTID\b": "three times daily",
    r"\bT\.I\.D\.\b": "three times daily",
    r"\bQID\b": "four times daily",
    r"\bQ\.I\.D\.\b": "four times daily",
    r"\bPRN\b": "as needed",
    r"\bP\.R\.N\.\b": "as needed",
    r"\bQHS\b": "at bedtime",
    r"\bQ\.H\.S\.\b": "at bedtime",
    r"\bq8h\b": "every eight hours",
    r"\bq6h\b": "every six hours",
    r"\bq4h\b": "every four hours",
    r"\bq12h\b": "every twelve hours",
    r"\bq24h\b": "every twenty-four hours",
    r"\bqdaily\b": "daily",
    r"\bq\.daily\b": "daily",
    r"\bqam\b": "every morning",
    r"\bqpm\b": "every evening",
    r"\bac\b": "before meals",
    r"\bpc\b": "after meals",
    r"\bstat\b": "immediately",
}

# Number to words conversion helpers for dosages
NUM_MAP = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen", "14": "fourteen",
    "15": "fifteen", "16": "sixteen", "17": "seventeen", "18": "eighteen", "19": "nineteen",
    "20": "twenty", "25": "twenty-five", "30": "thirty", "40": "forty", "50": "fifty",
    "60": "sixty", "70": "seventy", "75": "seventy-five", "80": "eighty", "90": "ninety",
    "100": "one hundred", "125": "one twenty-five", "150": "one fifty", "200": "two hundred",
    "250": "two fifty", "300": "three hundred", "375": "three seventy-five", "400": "four hundred",
    "500": "five hundred", "600": "six hundred", "750": "seven fifty", "800": "eight hundred",
    "1000": "one thousand", "1,000": "one thousand", "1200": "twelve hundred", "1500": "fifteen hundred",
    "2000": "two thousand", "2,000": "two thousand", "5000": "five thousand", "5,000": "five thousand",
    "10000": "ten thousand", "10,000": "ten thousand"
}


def number_to_spoken(num_str: str) -> str:
    """Converts a decimal or integer number string to spoken words."""
    clean_num = num_str.replace(",", "").strip()
    if clean_num in NUM_MAP:
        return NUM_MAP[clean_num]
    
    if "." in clean_num:
        parts = clean_num.split(".")
        whole_part = parts[0]
        dec_part = parts[1]
        
        whole_spoken = NUM_MAP.get(whole_part, whole_part)
        dec_digits = " ".join(NUM_MAP.get(d, d) for d in dec_part)
        return f"{whole_spoken} point {dec_digits}"
    
    return clean_num


def spell_word(word: str) -> str:
    """Spells out a word character by character for clear dictation (e.g. E M P A G L I F L O Z I N)."""
    return " ".join(c.upper() for c in word if c.isalnum())


class ClinicalTextNormalizer:
    def __init__(self, mode: NormalizationMode = NormalizationMode.DICTATION):
        self.mode = mode

    def normalize(self, text: str, spell_complex_drugs: bool = False) -> str:
        """
        Main entrypoint to normalize raw clinical text into spoken TTS input.
        """
        if not text:
            return ""

        res = text

        # 1. Expand Markdown / Bullet characters
        res = re.sub(r'^[ \t]*[-*•][ \t]+', 'bullet ', res, flags=re.MULTILINE)
        res = re.sub(r'^[ \t]*#+[ \t]+', 'heading ', res, flags=re.MULTILINE)

        # 2. Normalize Vital Signs
        res = self._normalize_vitals(res)

        # 3. Normalize Lab Values
        res = self._normalize_labs(res)

        # 4. Normalize Dosages & Units
        res = self._normalize_dosages(res)

        # 5. Normalize Routes and Frequencies
        res = self._normalize_sigs(res)

        # 6. Normalize Acronyms & Medical Abbreviations
        res = self._normalize_acronyms(res)

        # 7. Apply Mode-Specific Punctuation Formatting
        if self.mode == NormalizationMode.DICTATION:
            res = self._apply_dictation_punctuation(res)
        else:
            res = self._apply_ward_punctuation(res)

        # 8. Clean extra whitespace
        res = re.sub(r'[ \t]+', ' ', res)
        res = re.sub(r'\n{3,}', '\n\n', res).strip()

        return res

    def _normalize_vitals(self, text: str) -> str:
        """Normalizes clinical vitals like BP, HR, SpO2, Temp, RR, GCS."""
        # Blood Pressure: BP 138/74 or 138/74 mmHg
        def _bp_repl(m):
            sys_p = m.group(1)
            dia_p = m.group(2)
            return f"blood pressure {sys_p} over {dia_p}"
        text = re.sub(r'\b(?:BP|blood pressure)[:\s]*(\d{2,3})/(\d{2,3})(?:\s*mmHg)?\b', _bp_repl, text, flags=re.IGNORECASE)

        # Heart Rate: HR 82 or HR 82 bpm
        def _hr_repl(m):
            hr = m.group(1)
            return f"heart rate {hr}"
        text = re.sub(r'\b(?:HR|heart rate)[:\s]*(\d{2,3})(?:\s*bpm)?\b', _hr_repl, text, flags=re.IGNORECASE)

        # SpO2: SpO2 96% on 2L NP / SpO2 98% RA
        def _spo2_repl(m):
            sat = m.group(1)
            return f"oxygen saturation {sat} percent"
        text = re.sub(r'\b(?:SpO2|SaO2|O2 sat)[:\s]*(\d{2,3})%', _spo2_repl, text, flags=re.IGNORECASE)
        text = re.sub(r'\bon\s+(\d+(?:\.\d+)?)\s*L\s*(?:NP|nasal prongs)?\b', r'on \1 liters nasal prongs', text, flags=re.IGNORECASE)
        text = re.sub(r'\bon\s+RA\b', 'on room air', text, flags=re.IGNORECASE)

        # Respiratory Rate: RR 18
        text = re.sub(r'\bRR[:\s]*(\d{1,2})\b', r'respiratory rate \1', text, flags=re.IGNORECASE)

        # Temperature: T 37.2 or 37.2 C / 98.6 F
        def _temp_repl(m):
            val = m.group(1)
            return f"temperature {val} degrees"
        text = re.sub(r'\bT[:\s]*(\d{2}(?:\.\d+)?)\s*(?:C|degrees)?\b', _temp_repl, text)

        # GCS: GCS 15 or GCS 15/15
        text = re.sub(r'\bGCS[:\s]*(\d{1,2})(?:/15)?\b', r'G C S \1', text, flags=re.IGNORECASE)

        # JVP: JVP <3cm or JVP 4cm above sternal angle
        text = re.sub(r'\bJVP[:\s]*([<>]=?|\d+)\s*cm\b', r'J V P \1 centimeters', text, flags=re.IGNORECASE)

        return text

    def _normalize_labs(self, text: str) -> str:
        """Normalizes clinical lab panel results."""
        # Electrolytes & Renal
        text = re.sub(r'\bK\+?[:\s]*(\d+(?:\.\d+)?)\b', r'potassium \1', text)
        text = re.sub(r'\bNa[:\s]*(\d{2,3})\b', r'sodium \1', text)
        text = re.sub(r'\bCr[:\s]*(\d+(?:\.\d+)?)\b', r'creatinine \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\be?GFR[:\s]*([<>]?\s*\d+)\b', r'G F R \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bBUN[:\s]*(\d+(?:\.\d+)?)\b', r'B U N \1', text)

        # CBC
        text = re.sub(r'\b(?:Hgb|Hb)[:\s]*(\d{2,3})\b', r'hemoglobin \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bWBC[:\s]*(\d+(?:\.\d+)?)\b', r'white blood cell count \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bPlt[:\s]*(\d{2,3})\b', r'platelets \1', text, flags=re.IGNORECASE)

        # Coags & Cardiac
        text = re.sub(r'\bINR[:\s]*(\d+(?:\.\d+)?)\b', r'I N R \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:hs-cTn|cTnT|cTnI|Troponin)[:\s]*([<>]?\s*\d+(?:\.\d+)?)\b', r'troponin \1', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:LVEF|EF)[:\s]*(\d{1,2}(?:[-–]\d{1,2})?)\s*%', r'ejection fraction \1 percent', text, flags=re.IGNORECASE)

        return text

    def _normalize_dosages(self, text: str) -> str:
        """Expands medication dosages with clear articulated spoken words."""
        # Grams: 3.375g or 3.375 g -> "three point three seven five grams" / "1g" -> "one gram"
        def _gram_repl(m):
            val = m.group(1)
            spoken = number_to_spoken(val)
            unit = "gram" if val == "1" else "grams"
            return f"{spoken} {unit}"
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*g\b', _gram_repl, text, flags=re.IGNORECASE)

        # Milligrams: 40mg or 40 mg -> "forty milligrams" / "1mg" -> "one milligram"
        def _mg_repl(m):
            val = m.group(1)
            spoken = number_to_spoken(val)
            unit = "milligram" if val == "1" else "milligrams"
            return f"{spoken} {unit}"
        text = re.sub(r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*mg\b', _mg_repl, text, flags=re.IGNORECASE)

        # Micrograms: 500mcg / 500 ug / 500 µg
        def _mcg_repl(m):
            val = m.group(1)
            spoken = number_to_spoken(val)
            unit = "microgram" if val == "1" else "micrograms"
            return f"{spoken} {unit}"
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*(?:mcg|ug|µg)\b', _mcg_repl, text, flags=re.IGNORECASE)

        # Units: 5000 units / 5000 U
        def _units_repl(m):
            val = m.group(1)
            spoken = number_to_spoken(val)
            unit = "unit" if val == "1" else "units"
            return f"{spoken} {unit}"
        text = re.sub(r'\b(\d+(?:,\d{3})*)\s*(?:units|unit|U)\b', _units_repl, text, flags=re.IGNORECASE)

        # Liters: 1.5 L or 1.5L
        def _liter_repl(m):
            val = m.group(1)
            spoken = number_to_spoken(val)
            unit = "liter" if val == "1" else "liters"
            return f"{spoken} {unit}"
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*L(?:/day)?\b', lambda m: f"{_liter_repl(m)} per day" if "/day" in m.group(0) else _liter_repl(m), text)

        # Milliliters: 500 mL or 500mL
        def _ml_repl(m):
            val = m.group(1)
            spoken = number_to_spoken(val)
            unit = "milliliter" if val == "1" else "milliliters"
            return f"{spoken} {unit}"
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*m[Ll]\b', _ml_repl, text)

        return text

    def _normalize_sigs(self, text: str) -> str:
        """Expands Latin prescription sigs into plain spoken words."""
        for pattern, replacement in ROUTE_EXPANSIONS.items():
            text = re.sub(pattern, replacement, text)

        for pattern, replacement in FREQUENCY_EXPANSIONS.items():
            text = re.sub(pattern, replacement, text)

        return text

    def _normalize_acronyms(self, text: str) -> str:
        """Spells or expands clinical shorthand and abbreviations."""
        # Common clinical symbols
        text = text.replace("-->", " yields ")
        text = text.replace("->", " leads to ")
        text = text.replace("+/-", " plus or minus ")
        text = text.replace("&", " and ")
        text = text.replace("w/", " with ")
        text = text.replace("w/o", " without ")
        text = text.replace("s/p", " status post ")
        text = text.replace("h/o", " history of ")
        text = text.replace("r/o", " rule out ")
        text = text.replace("c/o", " complaining of ")
        text = text.replace("d/t", " due to ")
        text = text.replace("yo", " year old ")
        text = text.replace("y/o", " year old ")
        text = text.replace("y.o.", " year old ")

        # Common cardiac shorthand
        text = re.sub(r'\bS1/S2\b', 'S 1 and S 2', text, flags=re.IGNORECASE)
        text = re.sub(r'\bS1\b', 'S 1', text)
        text = re.sub(r'\bS2\b', 'S 2', text)
        text = re.sub(r'\bS3\b', 'S 3', text)
        text = re.sub(r'\bS4\b', 'S 4', text)
        text = re.sub(r'\b2\+\b', 'two plus', text)
        text = re.sub(r'\b1\+\b', 'one plus', text)
        text = re.sub(r'\b3\+\b', 'three plus', text)
        text = re.sub(r'\b4\+\b', 'four plus', text)

        # Roman numerals in clinical stages (e.g. Stage III -> Stage 3)
        text = re.sub(r'\bStage\s+I\b', 'Stage 1', text)
        text = re.sub(r'\bStage\s+II\b', 'Stage 2', text)
        text = re.sub(r'\bStage\s+III\b', 'Stage 3', text)
        text = re.sub(r'\bStage\s+IV\b', 'Stage 4', text)

        return text

    def _apply_dictation_punctuation(self, text: str) -> str:
        """
        Converts punctuation into spoken words for human hospital transcriptionists.
        e.g., '.' -> ' period ', ',' -> ' comma ', '\n\n' -> ' new paragraph '
        """
        # Protect abbreviations like Dr. / Mr. / Ms.
        text = re.sub(r'\bDr\.', 'Doctor', text)
        text = re.sub(r'\bMr\.', 'Mister', text)
        text = re.sub(r'\bMs\.', 'Miz', text)
        text = re.sub(r'\bMrs\.', 'Missus', text)

        # Quotation marks
        text = re.sub(r'["“”]', ' quotation mark ', text)

        # Semicolons and colons
        text = text.replace(';', ' semicolon ')
        text = text.replace(':', ' colon ')

        # Commas
        text = text.replace(',', ' comma ')

        # Parentheses & Brackets
        text = text.replace('(', ' open parenthesis ')
        text = text.replace(')', ' close parenthesis ')
        text = text.replace('[', ' open bracket ')
        text = text.replace(']', ' close bracket ')

        # Question marks & Exclamation marks
        text = text.replace('?', ' question mark ')
        text = text.replace('!', ' exclamation mark ')

        # Periods (ensure not inside a decimal number)
        text = re.sub(r'\.(?!\d)', ' period ', text)

        # Paragraphs and newlines
        paragraphs = text.split('\n\n')
        para_joined = []
        for p in paragraphs:
            lines = p.split('\n')
            para_joined.append(' new line '.join(l.strip() for l in lines if l.strip()))
        
        text = ' new paragraph '.join(p for p in para_joined if p)

        # Clean multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _apply_ward_punctuation(self, text: str) -> str:
        """
        Cleans text for natural human audio playback (preserving punctuation as pauses).
        """
        # Expand Doctor titles
        text = re.sub(r'\bDr\.', 'Doctor', text)
        text = re.sub(r'\bMr\.', 'Mister', text)
        text = re.sub(r'\bMs\.', 'Ms', text)

        # Clean bracket placeholders like [ 40 ] or [ flat / <3cm ]
        text = re.sub(r'\[\s*(.*?)\s*\]', r'\1', text)

        # Normalize dash separators
        text = text.replace('—', ', ').replace('–', ', ')

        return text
