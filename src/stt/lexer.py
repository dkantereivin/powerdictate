"""
Live Power-Phrase Lexer & Dynamic Placeholder Engine
=====================================================
Processes raw STT transcripts in real-time to:
1. Parse spoken punctuation tokens into written punctuation.
2. Intercept and expand voice macro triggers (dot-phrases).
3. Handle voice navigation commands ('next field', 'tab').
4. Manage dynamic '[ ... ]' variable placeholder stops.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from src.stt.templates import CLINICAL_MACROS, MacroTemplate


@dataclass
class LexerResult:
    text: str
    expanded: bool
    is_navigation_command: bool
    command_type: Optional[str] = None  # "next_field", "prev_field", "clear_field"
    macro_id: Optional[str] = None
    placeholders_count: int = 0


# Spoken punctuation regex replacements
PUNCTUATION_MAPPINGS = [
    (re.compile(r'\b(?:new\s*paragraph|next\s*paragraph)\b', re.IGNORECASE), '\n\n'),
    (re.compile(r'\b(?:new\s*line|next\s*line)\b', re.IGNORECASE), '\n'),
    (re.compile(r'\b(?:period|full\s*stop)\b', re.IGNORECASE), '.'),
    (re.compile(r'\bcomma\b', re.IGNORECASE), ','),
    (re.compile(r'\bcolon\b', re.IGNORECASE), ':'),
    (re.compile(r'\bsemicolon\b', re.IGNORECASE), ';'),
    (re.compile(r'\bquestion\s*mark\b', re.IGNORECASE), '?'),
    (re.compile(r'\bexclamation\s*(?:mark|point)\b', re.IGNORECASE), '!'),
    (re.compile(r'\b(?:open\s*quote|start\s*quote|quote)\b', re.IGNORECASE), '"'),
    (re.compile(r'\b(?:close\s*quote|end\s*quote|unquote)\b', re.IGNORECASE), '"'),
    (re.compile(r'\b(?:open\s*parenthesis|open\s*paren)\b', re.IGNORECASE), '('),
    (re.compile(r'\b(?:close\s*parenthesis|close\s*paren)\b', re.IGNORECASE), ')'),
    (re.compile(r'\bopen\s*bracket\b', re.IGNORECASE), '['),
    (re.compile(r'\bclose\s*bracket\b', re.IGNORECASE), ']'),
    (re.compile(r'\b(?:bullet|dash|hyphen)\b', re.IGNORECASE), '- '),
]

# Navigation voice commands
NAV_COMMANDS = {
    "next_field": re.compile(r'^(?:next\s*field|next\s*bracket|tab|jump\s*next)$', re.IGNORECASE),
    "prev_field": re.compile(r'^(?:previous\s*field|prev\s*field|back\s*field|shift\s*tab)$', re.IGNORECASE),
    "clear_field": re.compile(r'^(?:clear\s*field|delete\s*field|erase\s*field)$', re.IGNORECASE),
}

# Regex to match '[ ... ]' variable placeholders
PLACEHOLDER_REGEX = re.compile(r'\[(.*?)\]')

# Common clinical phonetic Whisper corrections
PHONETIC_CORRECTIONS = [
    (re.compile(r'\bampegliflozin\b', re.IGNORECASE), 'empagliflozin'),
    (re.compile(r'\bzeomonitor\b', re.IGNORECASE), 'Zio monitor'),
    (re.compile(r'\baliener\b', re.IGNORECASE), 'Eleanor'),
]


class PowerPhraseLexer:
    """
    Live stream lexer that intercepts speech tokens and transforms them
    into rich clinical text and editor actions.
    """

    def __init__(self, custom_macros: Optional[Dict[str, MacroTemplate]] = None):
        self.macros: Dict[str, MacroTemplate] = dict(CLINICAL_MACROS)
        if custom_macros:
            self.macros.update(custom_macros)

    def register_macro(self, macro: MacroTemplate):
        """Registers or updates a custom macro."""
        self.macros[macro.id] = macro

    def process(self, raw_transcript: str) -> LexerResult:
        """
        Processes a raw transcript chunk from the STT engine.
        Returns transformed text, expansion status, and navigation directives.
        """
        trimmed = raw_transcript.strip()
        if not trimmed:
            return LexerResult(text="", expanded=False, is_navigation_command=False)

        # 1. Check for standalone voice navigation commands
        for cmd_type, pattern in NAV_COMMANDS.items():
            if pattern.match(trimmed):
                return LexerResult(
                    text="",
                    expanded=False,
                    is_navigation_command=True,
                    command_type=cmd_type
                )

        transformed = raw_transcript
        expanded = False
        matched_macro_id = None

        # 2. Check and expand Power Phrase voice macros
        for macro_id, macro in self.macros.items():
            for pattern in macro.compiled_patterns:
                if pattern.search(transformed):
                    transformed = pattern.sub(macro.replacement, transformed)
                    expanded = True
                    matched_macro_id = macro_id
                    break
            if expanded:
                break

        # 3. Handle Voice Spelling Commands (e.g. "spell P A T E L" -> "PATEL")
        if not expanded:
            def _spell_repl(m):
                letters = re.sub(r'[^a-zA-Z]', '', m.group(1))
                return letters.upper()

            transformed = re.sub(
                r'\b(?:spell|spelled|spelling|spelled\s+out)\s+([A-Za-z](?:[\s-]+[A-Za-z]){1,15})\b',
                _spell_repl,
                transformed,
                flags=re.IGNORECASE
            )

        # 4. Apply Spoken Punctuation Transformations (if not already expanded into a structured template)
        if not expanded:
            for pattern, replacement in PHONETIC_CORRECTIONS:
                transformed = pattern.sub(replacement, transformed)

            for pattern, replacement in PUNCTUATION_MAPPINGS:
                transformed = pattern.sub(replacement, transformed)

            # Cleanup spacing around punctuation
            transformed = self._clean_punctuation_spacing(transformed)

        # Count remaining placeholders in the resulting string
        placeholders = list(PLACEHOLDER_REGEX.finditer(transformed))

        return LexerResult(
            text=transformed,
            expanded=expanded,
            is_navigation_command=False,
            macro_id=matched_macro_id,
            placeholders_count=len(placeholders)
        )

    def _clean_punctuation_spacing(self, text: str) -> str:
        """Cleans up space before punctuation marks and ensures proper sentence spacing."""
        text = re.sub(r'\s+([.,:;!?\)])', r'\1', text)
        text = re.sub(r'([\(\[])\s+', r'\1', text)
        text = re.sub(r'([.,:;!?])(?=[a-zA-Z])', r'\1 ', text)
        return text

    @staticmethod
    def find_all_placeholders(document_text: str) -> List[Tuple[int, int, str]]:
        """
        Returns list of (start_idx, end_idx, placeholder_content) for all '[ ... ]' in document.
        """
        results = []
        for m in PLACEHOLDER_REGEX.finditer(document_text):
            results.append((m.start(), m.end(), m.group(1).strip()))
        return results

    @staticmethod
    def get_next_placeholder(document_text: str, current_cursor: int = 0) -> Optional[Tuple[int, int, str]]:
        """
        Finds the next '[ ... ]' placeholder at or after current_cursor position.
        Loops to the beginning if none found after current_cursor.
        """
        all_matches = list(PLACEHOLDER_REGEX.finditer(document_text))
        if not all_matches:
            return None

        # Search after cursor
        for m in all_matches:
            if m.start() >= current_cursor:
                return (m.start(), m.end(), m.group(1).strip())

        # Loop back to first match
        first = all_matches[0]
        return (first.start(), first.end(), first.group(1).strip())

    @staticmethod
    def replace_active_placeholder(
        document_text: str,
        start_idx: int,
        end_idx: int,
        replacement_text: str
    ) -> str:
        """
        Replaces the placeholder span [start_idx, end_idx] with replacement_text.
        """
        return document_text[:start_idx] + replacement_text + document_text[end_idx:]
