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

    def __init__(self, explicit_punctuation: bool = True, spell_ambiguities: bool = True):
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

        # 8. Normalize clinical Roman numerals (Stage III -> Stage 3, II-XII -> 2 through 12)
        text = self._normalize_roman_numerals(text)

        # 9. Handle explicit spoken punctuation if requested
        if self.explicit_punctuation:
            text = self._apply_explicit_punctuation(text)

        # 10. Apply phonetic medical pronunciation dictionary
        text = apply_medical_dictionary(text)

        # Restore protected spelled blocks
        for idx, block in enumerate(spelled_blocks):
            text = text.replace(f"__SPELLED_TOKEN_{idx}__", block)

        # 11. Clean whitespace and excess pauses
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

        # 1. Clinician references: Dr. [First] [Last] or Dr. [Last]
        def _replace_dr(m):
            first_or_last = m.group(2)
            second = m.group(3)
            if second:
                if second.lower() in common_exemptions:
                    return f"Doctor {first_or_last} {second}"
                return f"Doctor {first_or_last} {second}, last name spelled {spell_out_word(second)}"
            if first_or_last.lower() in common_exemptions or len(first_or_last) <= 2:
                return m.group(0)
            return f"Doctor {first_or_last}, spelled {spell_out_word(first_or_last)}"

        text = re.sub(r'\b(Dr\.|Doctor)\s+([A-Z][a-z]+)(?:\s+([A-Z][a-z]+))?\b', _replace_dr, text)

        # 2. Clinician with MD/DO suffix: First Last, MD -> Doctor First Last, MD, last name spelled L A S T
        def _replace_md_suffix(m):
            first = m.group(1)
            last = m.group(2)
            suffix = m.group(3)
            return f"Doctor {first} {last}, {suffix}, last name spelled {spell_out_word(last)}"

        text = re.sub(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+),\s*(MD|DO|MBBS)\b', _replace_md_suffix, text)

        # 3. Patient surname references: Mr. / Mrs. / Ms. [Name]
        title_map = {"mr.": "Mister", "mr": "Mister", "mrs.": "Missus", "mrs": "Missus", "ms.": "Mizz", "ms": "Mizz"}
        def _replace_title(m):
            raw_title = m.group(1).lower()
            title = title_map.get(raw_title, raw_title.capitalize())
            name = m.group(2)
            if len(name) <= 2:
                return m.group(0)
            return f"{title} {name}, spelled {spell_out_word(name)}"

        text = re.sub(r'\b(Mr\.|Mrs\.|Ms\.|Mr|Mrs|Ms)\s+([A-Z][a-z]+)\b', _replace_title, text)

        # 4. Patient Name: [First] [Last] header
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

    def _normalize_roman_numerals(self, text: str) -> str:
        """
        Converts clinical Roman numerals into standard numbers for dictation.
        Examples:
        - 'GOLD Stage III' -> 'GOLD Stage 3'
        - 'NYHA Class II' -> 'NYHA Class 2'
        - 'Cranial nerves II–XII' -> 'Cranial nerves 2 through 12'
        - 'Grade II/VI' -> 'Grade 2 out of 6'
        - 'Type II' -> 'type 2'
        - 'V1–V3' -> 'V 1 through V 3'
        - 'S1 and S2' -> 'S 1 and S 2', 'S3' -> 'S 3'
        """
        roman_map = {
            "I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6",
            "VII": "7", "VIII": "8", "IX": "9", "X": "10", "XI": "11", "XII": "12"
        }

        # 1. Ranges: II–XII or II-XII -> 2 through 12
        def _range_repl(m):
            r1 = m.group(1).upper()
            r2 = m.group(2).upper()
            n1 = roman_map.get(r1, r1)
            n2 = roman_map.get(r2, r2)
            return f"{n1} through {n2}"

        text = re.sub(r'\b([IVXLCDM]{1,4})\s*[-–—]\s*([IVXLCDM]{1,4})\b', _range_repl, text)

        # 2. Fractions/murmurs: II/VI or II / VI -> 2 out of 6
        def _frac_repl(m):
            r1 = m.group(1).upper()
            r2 = m.group(2).upper()
            n1 = roman_map.get(r1, r1)
            n2 = roman_map.get(r2, r2)
            return f"{n1} out of {n2}"

        text = re.sub(r'\b([IVXLCDM]{1,4})\s*/\s*([IVXLCDM]{1,4})\b', _frac_repl, text)

        # 3. Stage, Class, Grade, Type, Group
        def _named_repl(m):
            prefix = m.group(1)
            num_part = m.group(2).upper()
            suffix = m.group(3) or ""
            val = roman_map.get(num_part, num_part)
            return f"{prefix} {val}{suffix}"

        text = re.sub(r'\b(Stage|Class|Grade|Type)\s+([IVXLCDM]{1,4})([a-eA-E]?)\b', _named_repl, text, flags=re.IGNORECASE)

        # 4. ECG leads V1–V3 -> V 1 through V 3, V1 -> V 1
        text = re.sub(r'\bV([1-6])\s*[-–—]\s*V([1-6])\b', r'V \1 through V \2', text)
        text = re.sub(r'\bV([1-6])\b', r'V \1', text)

        # 5. Heart sounds: S1 and S2 -> S 1 and S 2, S3 -> S 3, S4 -> S 4
        text = re.sub(r'\bS([1-4])\b', r'S \1', text)

        return text

    def _normalize_units(self, text: str) -> str:
        """
        Expands clinical measurement units into natural spoken words.
        Handles compound clinical units, rates, pressures, and singular/plural quantities.
        Example: 'ceftriaxone 1g IV' -> 'ceftriaxone 1 gram IV'
        """
        # 1. Compound rates, pressures, concentrations
        # Note: 'minit' is used intentionally to prevent Kokoro from pronouncing 'minute' as 'my-NOOT'
        compound_units = [
            (r'\bmL/min/1\.73\s*m[²2]\b', 'milliliters per minit per 1 point 73 square meters'),
            (r'\bmL/kg/h(?:r)?\b', 'milliliters per kilogram per hour'),
            (r'\bmL/min\b', 'milliliters per minit'),
            (r'\bL/min\b', 'liters per minit'),
            (r'\bmL/hr\b', 'milliliters per hour'),
            (r'\bmg/dL\b', 'milligrams per deciliter'),
            (r'\bmmol/L\b', 'millimoles per liter'),
            (r'\b[uµ]mol/L\b', 'micromoles per liter'),
            (r'\bg/dL\b', 'grams per deciliter'),
            (r'\bg/L\b', 'grams per liter'),
            (r'\bng/mL\b', 'nanograms per milliliter'),
            (r'\bmg/L\b', 'milligrams per liter'),
            (r'\b[uµ]g/mL\b', 'micrograms per milliliter'),
            (r'\bmEq/L\b', 'milliequivalents per liter'),
            (r'\bU/L\b', 'units per liter'),
            (r'[x×]\s*10[\^³3]/[uµ]L', 'thousand per microliter'),
            (r'/[uµ]L\b', 'per microliter'),
            (r'/hpf\b', 'per high-power field'),
            (r'\bmmHg\b', 'millimeters of mercury'),
            (r'\bcm\s*H[₂2]O\b', 'centimeters of water'),
            (r'\bbreaths/min\b', 'breaths per minit'),
            (r'\bper minute\b', 'per minit'),
            (r'\bbpm\b', 'beats per minit'),
            (r'\bkg/m[²2]\b', 'kilograms per square meter'),
            (r'°C\b', 'degrees Celsius'),
            (r'°F\b', 'degrees Fahrenheit'),
            (r'\bPaCO[2₂]\b', 'P A CO2'),
            (r'\bPaO[2₂]\b', 'P A O2'),
            (r'\bSaO[2₂]\b', 'oxygen saturation'),
            (r'\bHCO[3₃][⁻-]?\b', 'Bicarbonate'),
        ]

        for pat, repl in compound_units:
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

        # 2. Numbered quantity units (singular vs plural)
        def _unit_repl(unit_singular: str, unit_plural: str):
            def _repl(m):
                val_str = m.group(1)
                try:
                    val = float(val_str)
                    unit = unit_singular if val == 1.0 else unit_plural
                except ValueError:
                    unit = unit_plural
                return f"{val_str} {unit}"
            return _repl

        # Grams: 1g -> 1 gram, 2g -> 2 grams
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*(?:g|gm|gms)\b', _unit_repl('gram', 'grams'), text, flags=re.IGNORECASE)
        # Milligrams: 1mg -> 1 milligram, 50mg -> 50 milligrams
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*mg\b', _unit_repl('milligram', 'milligrams'), text, flags=re.IGNORECASE)
        # Micrograms: 1mcg -> 1 microgram, 100mcg -> 100 micrograms
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*(?:mcg|[uµ]g)\b', _unit_repl('microgram', 'micrograms'), text, flags=re.IGNORECASE)
        # Liters: 1L -> 1 liter, 4L -> 4 liters
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*L\b', _unit_repl('liter', 'liters'), text)
        # Milliliters: 1mL -> 1 milliliter, 250mL -> 250 milliliters
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*(?:mL|ml|cc)\b', _unit_repl('milliliter', 'milliliters'), text)
        # Kilograms: 1kg -> 1 kilogram, 84.5kg -> 84.5 kilograms
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*kg\b', _unit_repl('kilogram', 'kilograms'), text, flags=re.IGNORECASE)
        # Minutes: 1 minute -> 1 minit, 5 minutes -> 5 minits
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*minutes?\b', _unit_repl('minit', 'minits'), text, flags=re.IGNORECASE)
        # Pounds
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\b', _unit_repl('pound', 'pounds'), text, flags=re.IGNORECASE)
        # Units (e.g. 18 units)
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*units?\b', _unit_repl('unit', 'units'), text, flags=re.IGNORECASE)
        # Puffs (e.g. 2 puffs)
        text = re.sub(r'\b(\d+(?:\.\d+)?)\s*puffs?\b', _unit_repl('puff', 'puffs'), text, flags=re.IGNORECASE)

        # Standalone remaining units
        fallback_units = [
            (r'\bmg\b', 'milligrams'),
            (r'\bmcg\b', 'micrograms'),
            (r'\bmL\b', 'milliliters'),
            (r'\bkg\b', 'kilograms'),
        ]
        for pat, repl in fallback_units:
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

        return text

    def _apply_explicit_punctuation(self, text: str) -> str:
        """
        Replaces all punctuation marks and newlines with explicit spoken dictation words
        for human medical transcriptionists, while preserving natural acoustic pauses.
        Dictates: period, comma, colon, semicolon, open/close parenthesis, quotes,
        new line, and new paragraph.
        Consecutive list items only produce 'new line' rather than 'new paragraph'.
        """
        # 1. Clean markdown headers, tables, and horizontal rules
        text = re.sub(r'^\s*---+\s*$', '\n\n', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*#{1,6}\s*(.*?)$', r'\n\n\1:\n', text, flags=re.MULTILINE)
        # Note: Do not inject leading '\n' on list bullets or numbers, which would create false blank lines
        text = re.sub(r'^\s*[\*\-]\s+', 'Bullet, ', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*(\d+)\.\s+', r'Number \1 period, ', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold removal
        text = re.sub(r'\*([^*]+)\*', r'\1', text)    # Italic removal
        text = re.sub(r'\|', ' new line, ', text)     # Table row delimiters

        # 2. Abbreviations and common symbols before punctuation expansion
        text = re.sub(r'\bvs\.?\b', 'versus', text, flags=re.IGNORECASE)
        text = re.sub(r'\betc\.?\b', 'etcetera', text, flags=re.IGNORECASE)
        text = re.sub(r'\bapprox\.?\b', 'approximately', text, flags=re.IGNORECASE)
        text = re.sub(r'#(\d+)', r'number \1', text)
        text = re.sub(r'~\s*(\d+)', r'approximately \1', text)
        text = re.sub(r'×\s*(\d+)', r'times \1', text)



        # 2. Convert decimal points to 'point' so they are not spoken as 'period'
        text = re.sub(r'(\d+)\.(\d+)', r'\1 point \2', text)

        # 3. Numeric ranges: 1.4-1.6 -> 1.4 to 1.6
        text = re.sub(r'(\d+(?:\s*point\s*\d+)?)\s*[-–—]\s*(\d+(?:\s*point\s*\d+)?)', r'\1 to \2', text)

        # 4. Slashes: blood pressures are already 'over', medications like 24/26 -> 24 slash 26
        text = re.sub(r'(?<=\d)\s*/\s*(?=\d)', ' slash ', text)
        text = re.sub(r'\s*/\s*', ' slash ', text)

        # 5. Commas (must be replaced FIRST so injected commas in 'colon,' or 'parenthesis,' are not recursively replaced)
        text = re.sub(r',', ' comma, ', text)

        # 6. Parentheses and Brackets
        text = re.sub(r'\(', ' open parenthesis, ', text)
        text = re.sub(r'\)', ' close parenthesis, ', text)
        text = re.sub(r'\[', ' open bracket, ', text)
        text = re.sub(r'\]', ' close bracket, ', text)

        # 7. Quotes
        text = re.sub(r'["“”]', ' quote, ', text)

        # 8. Colon and Semicolon
        text = re.sub(r':', ' colon, ', text)
        text = re.sub(r';', ' semicolon, ', text)

        # 9. Question and exclamation marks
        text = re.sub(r'\?', ' question mark? ', text)
        text = re.sub(r'!', ' exclamation point! ', text)

        # 10. Sentence-ending Periods (followed by space, newline, or EOF)
        text = re.sub(r'\.(?=\s|$)', ' period. ', text)

        # 11. Newlines and Paragraphs
        text = re.sub(r'\n\s*\n+', ' new paragraph. ', text)
        text = re.sub(r'\n', ' new line, ', text)

        # Clean multiple spaces
        text = re.sub(r'[ \t]+', ' ', text)
        return text


