"""
Clinical Text Preprocessor & Normalizer for TTS
===============================================
Normalizes raw medical dictation text into an optimal, highly-intelligible format
for Kokoro TTS.

Handles:
1. Spoken transcriptionist expansions (spelling out ambiguous names and places).
2. Lab value and flag normalization (e.g. 'BUN 8.6 (H)' -> 'B U N 8.6 high').
3. Vital signs and ratios (e.g. 'BP 120/80' -> 'blood pressure 120 over 80').
4. Clinical units and decimal expansions.
5. Medical dictionary pronunciation replacement.
6. Optional explicit spoken punctuation ('period', 'comma', 'new line').
"""

import re
from typing import Dict, List, Optional, Set
from tts.medical_dict import apply_medical_dictionary


MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def spell_out_word(word: str) -> str:
    """
    Spells out an ambiguous proper noun letter-by-letter for transcriptionists.
    Example: 'Kaczynski' -> 'K A C Z Y N S K I'
    """
    clean = re.sub(r'[^A-Za-z]', '', word)
    return " ".join(list(clean.upper()))


def format_spelled_out_name(full_name: str) -> str:
    """
    Formats a name with a transcriptionist spelling clarification:
    Example: 'Dr. Vandermeer' -> 'Dr. Vandermeer, spelled V A N D E R M E E R'
    """
    # Extract last word / surname
    tokens = full_name.strip().split()
    if not tokens:
        return full_name
    surname = tokens[-1]
    spelled = spell_out_word(surname)
    return f"{full_name}, spelled {spelled}"


class ClinicalTextPreprocessor:
    """
    Transforms clinical text and lab batteries into a pristine, natural script
    optimized for medical speech synthesis.
    """

    def __init__(self, explicit_punctuation: bool = False, spell_ambiguities: bool = True):
        self.explicit_punctuation = explicit_punctuation
        self.spell_ambiguities = spell_ambiguities

    def preprocess(self, text: str) -> str:
        """Runs the complete clinical text normalization pipeline."""
        if not text or not text.strip():
            return ""

        # 1. Expand explicit [spell:Word] or [spell Word] tags
        text = self._expand_explicit_spell_tags(text)

        # 2. Spell out ambiguous clinician and patient names (Dr. X, Mr. Y)
        if self.spell_ambiguities:
            text = self._spell_out_names_and_places(text)

        # Protect all "spelled [A-Z ]+" blocks so medical dictionary and acronym expansions don't touch them
        spelled_blocks = []
        def _protect(m):
            spelled_blocks.append(m.group(0))
            return f"__SPELLED_TOKEN_{len(spelled_blocks) - 1}__"

        text = re.sub(r',?\s*spelled\s+[A-Za-z\s]+(?=[,\.]|\b|$)', _protect, text)

        # 3. Clean up template brackets [***] -> 'blank' or omission
        text = re.sub(r'\[\*{3}\]', 'blank', text)
        text = re.sub(r'\[(.*?)\]', r'\1', text)  # Strip picklist brackets

        # 4. Normalize dates and times
        text = self._normalize_dates_and_times(text)

        # 5. Normalize vital signs
        text = self._normalize_vitals(text)

        # 6. Normalize lab panels and test values
        text = self._normalize_labs(text)

        # 7. Normalize clinical units and measurements
        text = self._normalize_units(text)

        # 8. Apply phonetic medical pronunciation dictionary
        text = apply_medical_dictionary(text)

        # Restore protected spelled blocks
        for idx, block in enumerate(spelled_blocks):
            text = text.replace(f"__SPELLED_TOKEN_{idx}__", block)

        # 9. Handle explicit spoken punctuation if requested
        if self.explicit_punctuation:
            text = self._apply_explicit_punctuation(text)

        # 10. Clean whitespace and excess pauses
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _expand_explicit_spell_tags(self, text: str) -> str:
        """Expands [spell:Word] or [spell Word] tags into 'Word, spelled W O R D'."""
        def _repl(m):
            word = m.group(1).strip()
            return f"{word}, spelled {spell_out_word(word)}"
        return re.sub(r'\[spell:?\s*([A-Za-z\-]+)\]', _repl, text, flags=re.IGNORECASE)

    def _spell_out_names_and_places(self, text: str) -> str:
        """
        Detects ambiguous personal names (Dr. LastName, Mr. LastName, Patient FirstName LastName)
        and facility names, appending transcriptionist spelling clarifications.
        Does NOT spell out common medications or diseases.
        """
        # Exclude common medical words that might follow 'Dr.' mistakenly
        common_exemptions = {"medical", "hospital", "clinic", "order", "note", "rounds"}

        # 1. Clinician references: Dr. [Name] / Doctor [Name]
        def _replace_dr(m):
            prefix = m.group(1)
            name = m.group(2)
            if name.lower() in common_exemptions or len(name) <= 2:
                return m.group(0)
            return f"{prefix} {name}, spelled {spell_out_word(name)}"

        text = re.sub(r'\b(Dr\.|Doctor)\s+([A-Z][a-z]+)\b', _replace_dr, text)

        # 2. Patient surname references: Mr. / Mrs. / Ms. [Name]
        def _replace_title(m):
            title = m.group(1)
            name = m.group(2)
            if len(name) <= 2:
                return m.group(0)
            return f"{title} {name}, spelled {spell_out_word(name)}"

        text = re.sub(r'\b(Mr\.|Mrs\.|Ms\.)\s+([A-Z][a-z]+)\b', _replace_title, text)

        # 3. Patient Name: [First] [Last] header
        def _replace_patient_hdr(m):
            first = m.group(1)
            last = m.group(2)
            return f"Patient {first} {last}, last name spelled {spell_out_word(last)}"

        text = re.sub(r'\bPatient:\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', _replace_patient_hdr, text)
        return text

    def _normalize_dates_and_times(self, text: str) -> str:
        """Converts dates like 1/11/25 -> January 11th, 2025 and 08:03 -> 08:03 hours."""
        def _date_repl(m):
            month = int(m.group(1))
            day = int(m.group(2))
            year = m.group(3)
            full_year = f"20{year}" if len(year) == 2 else year
            month_name = MONTHS.get(month, str(month))
            return f"{month_name} {day}, {full_year}"

        text = re.sub(r'\b([01]?\d)/([0-3]?\d)/(\d{2,4})\b', _date_repl, text)

        # Times: 08:03 -> 08:03 hours
        text = re.sub(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', r'\1 \2 hours', text)
        return text

    def _normalize_vitals(self, text: str) -> str:
        """Normalizes clinical vital signs for speech synthesis."""
        # Blood pressure 120/80 -> blood pressure 120 over 80
        text = re.sub(r'\b(?:BP|Blood Pressure)[:\s=]*(\d{2,3})/(\d{2,3})\b', r'blood pressure \1 over \2', text, flags=re.IGNORECASE)

        # Heart rate
        text = re.sub(r'\b(?:HR|Heart Rate|Pulse)[:\s=]*(\d{2,3})\b', r'heart rate \1', text, flags=re.IGNORECASE)

        # SpO2
        text = re.sub(r'\b(?:SpO2|O2 Sat)[:\s=]*(\d{2,3})%?', r'oxygen saturation \1 percent', text, flags=re.IGNORECASE)

        # Respiratory rate
        text = re.sub(r'\b(?:RR|Resp Rate)[:\s=]*(\d{1,2})\b', r'respiratory rate \1', text, flags=re.IGNORECASE)

        # Temperature
        text = re.sub(r'\b(?:Temp|Temperature)[:\s=]*(\d{2}(?:\.\d+)?)\s*(?:C|F)?\b', r'temperature \1 degrees', text, flags=re.IGNORECASE)
        return text

    def _normalize_labs(self, text: str) -> str:
        """Expands lab names, high/low flags, and format into natural cadence."""
        # Normalize abnormal flags (H) -> high, (L) -> low, [H] -> high, (CRIT) -> critical
        text = re.sub(r'[\(\[]([HL])[\)\]]', lambda m: " high" if m.group(1).upper() == "H" else " low", text)
        text = re.sub(r'[\(\[]CRIT[\)\]]', " critical", text, flags=re.IGNORECASE)

        # Replace test acronyms with natural spoken words when followed by values
        lab_expansions = [
            (r'\bNa\b(?=\s*[:=\d])', 'Sodium'),
            (r'\bK\b(?=\s*[:=\d])', 'Potassium'),
            (r'\bCl\b(?=\s*[:=\d])', 'Chloride'),
            (r'\bHCO3\b(?=\s*[:=\d])', 'Bicarbonate'),
            (r'\bBUN\b(?=\s*[:=\d])', 'B U N'),
            (r'\bCr\b(?=\s*[:=\d])', 'Creatinine'),
            (r'\beGFR\b(?=\s*[:=\d])', 'E G F R'),
            (r'\bCrCl\b(?=\s*[:=\d])', 'Creatinine Clearance'),
            (r'\bGlu\b(?=\s*[:=\d])', 'Glucose'),
            (r'\bCa\b(?=\s*[:=\d])', 'Calcium'),
            (r'\bPO4\b(?=\s*[:=\d])', 'Phosphate'),
            (r'\bMg\b(?=\s*[:=\d])', 'Magnesium'),
            (r'\bWBC\b(?=\s*[:=\d])', 'White blood count'),
            (r'\bHgb\b(?=\s*[:=\d])', 'Hemoglobin'),
            (r'\bHct\b(?=\s*[:=\d])', 'Hematocrit'),
            (r'\bPlt\b(?=\s*[:=\d])', 'Platelets'),
            (r'\bMCV\b(?=\s*[:=\d])', 'M C V'),
            (r'\bNeut\b(?=\s*[:=\d])', 'Neutrophils'),
            (r'\bLymph\b(?=\s*[:=\d])', 'Lymphocytes'),
            (r'\bMono\b(?=\s*[:=\d])', 'Monocytes'),
            (r'\bEos\b(?=\s*[:=\d])', 'Eosinophils'),
            (r'\bBaso\b(?=\s*[:=\d])', 'Basophils'),
            (r'\bINR\b(?=\s*[:=\d])', 'I N R'),
            (r'\bPTT\b(?=\s*[:=\d])', 'P T T'),
            (r'\bALT\b(?=\s*[:=\d])', 'A L T'),
            (r'\bAST\b(?=\s*[:=\d])', 'A S T'),
            (r'\bALP\b(?=\s*[:=\d])', 'Alkaline phosphatase'),
            (r'\bLipase\b(?=\s*[:=\d])', 'Lipase'),
        ]
        for pat, repl in lab_expansions:
            text = re.sub(pat, repl, text)

        # Replace inequalities: >60 -> greater than 60, <0.01 -> less than 0.01
        text = re.sub(r'>\s*(\d+(?:\.\d+)?)', r'greater than \1', text)
        text = re.sub(r'<\s*(\d+(?:\.\d+)?)', r'less than \1', text)
        return text

    def _normalize_units(self, text: str) -> str:
        """Expands clinical measurement units."""
        units_map = [
            (r'\bmg/dL\b', 'milligrams per deciliter'),
            (r'\bmmol/L\b', 'millimoles per liter'),
            (r'\bumol/L\b', 'micromoles per liter'),
            (r'\bg/dL\b', 'grams per deciliter'),
            (r'\bg/L\b', 'grams per liter'),
            (r'\bmEq/L\b', 'milliequivalents per liter'),
            (r'\bmg\b', 'milligrams'),
            (r'\bmcg\b', 'micrograms'),
            (r'\bmL\b', 'milliliters'),
            (r'\bkg\b', 'kilograms'),
            (r'\blbs?\b', 'pounds'),
        ]
        for pat, repl in units_map:
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)
        return text

    def _apply_explicit_punctuation(self, text: str) -> str:
        """Replaces punctuation marks with explicit spoken words for human transcriptionists."""
        # Replace new paragraphs first
        text = re.sub(r'\n\s*\n', ' new paragraph ', text)
        text = re.sub(r'\n', ' new line ', text)
        text = re.sub(r'\.', ' period ', text)
        text = re.sub(r',', ' comma ', text)
        text = re.sub(r':', ' colon ', text)
        text = re.sub(r';', ' semicolon ', text)
        text = re.sub(r'\?', ' question mark ', text)
        return text
