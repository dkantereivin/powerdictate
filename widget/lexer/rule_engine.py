"""
High-Performance Medical YAML Rule Engine & Text Normalizer
===========================================================
Loads modular YAML rule definitions from rules/ directory and applies:
1. Multi-word phonetic compound replacements
2. Medication generic/brand dictionary mappings
3. Clinical abbreviation auto-casing (IV, PO, BID, SpO2)
4. Dosage unit & numeral transformations (forty mg -> 40 mg)
5. Context-aware mid-sentence insertion formatting
"""

import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("widget.rules")

RULES_DIR = Path(__file__).resolve().parent.parent.parent / "rules"


class MedicalRuleEngine:
    """
    Sub-millisecond rule-based text normalizer and context formatter.
    """

    def __init__(self, rules_dir: Optional[Path] = None):
        self.rules_dir = rules_dir or RULES_DIR
        self.abbreviations: Dict[str, str] = {}
        self.medications: Dict[str, str] = {}
        self.phonetic_mappings: Dict[str, str] = {}
        self.number_words: Dict[str, str] = {}
        self.spoken_punctuation: Dict[str, str] = {}

        self.load_all_rules()

    def load_all_rules(self):
        """Loads and compiles all YAML rule files."""
        try:
            # 1. Abbreviations
            abbr_file = self.rules_dir / "abbreviations.yaml"
            if abbr_file.exists():
                with open(abbr_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.abbreviations = data.get("abbreviations", {})

            # 2. Medications
            meds_file = self.rules_dir / "medications.yaml"
            if meds_file.exists():
                with open(meds_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.medications = data.get("medications", {})

            # 3. Phonetic corrections
            phon_file = self.rules_dir / "phonetic_corrections.yaml"
            if phon_file.exists():
                with open(phon_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.phonetic_mappings = data.get("phonetic_mappings", {})

            # 4. Clinical formatting
            fmt_file = self.rules_dir / "clinical_formatting.yaml"
            if fmt_file.exists():
                with open(fmt_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.number_words = data.get("number_words", {})
                    self.spoken_punctuation = data.get("spoken_punctuation", {})

            logger.info(
                f"Loaded YAML Rules: {len(self.abbreviations)} abbreviations, "
                f"{len(self.medications)} medications, "
                f"{len(self.phonetic_mappings)} phonetic mappings."
            )
        except Exception as e:
            logger.error(f"Error loading YAML rules: {e}")

    def normalize_text(self, raw_text: str) -> str:
        """
        Applies all YAML normalizations across the raw transcript stream.
        """
        if not raw_text or not raw_text.strip():
            return ""

        s = raw_text.strip()
        lower_s = s.lower()

        # 1. Multi-word phonetic compound replacements
        for phonetic, target in self.phonetic_mappings.items():
            pattern = r'\b' + re.escape(phonetic) + r'\b'
            lower_s = re.sub(pattern, target, lower_s)

        # 2. Number words preceding dosage units -> digits (e.g. 'forty mg' -> '40 mg')
        for word, digit in self.number_words.items():
            pattern = r'\b' + re.escape(word) + r'\s+(mg|mcg|mL|mEq|kg|PO|IV|units|tabs|tablets|capsules)\b'
            lower_s = re.sub(pattern, digit + r' \1', lower_s)

        # 3. Clinical abbreviations casing (e.g. 'iv' -> 'IV', 'bid' -> 'BID')
        tokens = lower_s.split()
        normalized_tokens = []
        for token in tokens:
            clean_token = token.lower().rstrip(".,;:?!")
            punct = token[len(clean_token):] if len(token) > len(clean_token) else ""

            if clean_token in self.abbreviations:
                normalized_tokens.append(self.abbreviations[clean_token] + punct)
            elif clean_token in self.medications:
                normalized_tokens.append(self.medications[clean_token] + punct)
            else:
                normalized_tokens.append(token)

        reconstructed = " ".join(normalized_tokens)

        # 4. Sentence boundary true-casing
        segments = re.split(r'(\. |\n)', reconstructed)
        cased_segments = []
        for seg in segments:
            if seg and len(seg) > 0 and seg[0].isalpha():
                cased_segments.append(seg[0].upper() + seg[1:])
            else:
                cased_segments.append(seg)

        return "".join(cased_segments)

    def format_insertion_context(
        self,
        prefix_text: str,
        new_text: str,
        suffix_text: str
    ) -> str:
        """
        Context-aware formatting when inserting text midway:
        - Decides whether new_text should start with Uppercase or Lowercase.
        - Ensures clean single-spacing without double spaces or missing spaces.
        """
        if not new_text or not new_text.strip():
            return ""

        normalized = self.normalize_text(new_text)
        if not normalized:
            return ""

        prefix_clean = prefix_text.rstrip()
        suffix_clean = suffix_text.lstrip()

        # Check if cursor is at sentence beginning
        is_sentence_start = (
            len(prefix_clean) == 0 or
            prefix_clean.endswith((".", "!", "?", ":", "\n"))
        )

        first_word = normalized.split()[0] if normalized.split() else ""
        clean_first = first_word.rstrip(".,;:?!")

        # Determine casing for first word
        is_acronym_or_brand = (
            clean_first in self.abbreviations.values() or
            clean_first in self.medications.values() or
            clean_first.isupper()
        )

        formatted_body = normalized
        if not is_acronym_or_brand:
            if is_sentence_start:
                formatted_body = normalized[0].upper() + normalized[1:]
            else:
                formatted_body = normalized[0].lower() + normalized[1:]

        # Spacing adjustments: prevent double spacing if prefix/suffix already has space
        needs_leading_space = len(prefix_text) > 0 and not prefix_text.endswith((" ", "\n", "("))
        needs_trailing_space = len(suffix_text) > 0 and not suffix_text.startswith((" ", "\n", ".", ",", "!", "?", ":", ";", ")"))

        result = (
            (" " if needs_leading_space else "") +
            formatted_body +
            (" " if needs_trailing_space else "")
        )
        return result
