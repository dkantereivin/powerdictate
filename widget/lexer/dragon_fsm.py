"""
Lookahead Finite-State Lexer & Medical Command Interceptor
=========================================================
Traps spoken punctuation, clinical macros, and navigation commands.
Suppresses command tokens from text output and dispatches visual toast notifications.
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class LexerAction:
    action_type: str  # "TYPE_TEXT", "PASTE_TEXT", "COMMAND_TRIGGERED"
    text: str = ""
    trigger: str = ""
    command_name: str = ""
    hotkey: str = ""
    description: str = ""


# Vocal clinical macros
VOCAL_MACROS = {
    "no pe": (
        "Physical Exam: Alert and oriented x3, no acute distress. "
        "Pupils equal, round, reactive to light. "
        "Heart: Regular rate and rhythm, normal S1/S2, no murmurs. "
        "Lungs: Clear to auscultation bilaterally, no wheezes, rales, or rhonchi. "
        "Abdomen: Soft, non-tender, non-distended, normal bowel sounds. "
        "Extremities: No cyanosis, clubbing, or edema."
    ),
    "negative pe": (
        "Physical Exam: Alert and oriented x3, no acute distress. "
        "Pupils equal, round, reactive to light. "
        "Heart: Regular rate and rhythm, normal S1/S2, no murmurs. "
        "Lungs: Clear to auscultation bilaterally, no wheezes, rales, or rhonchi. "
        "Abdomen: Soft, non-tender, non-distended, normal bowel sounds. "
        "Extremities: No cyanosis, clubbing, or edema."
    ),
    "normal cardiac": (
        "Cardiovascular: Regular rate and rhythm. S1 and S2 present. "
        "No murmurs, gallops, or rubs. Peripheral pulses intact bilaterally."
    ),
    "hf plan": (
        "Heart Failure Plan:\n"
        "1. Strict daily weights and I/O tracking.\n"
        "2. Continue loop diuretic therapy.\n"
        "3. Goal euvolemia prior to discharge.\n"
        "4. Fluid restriction <2L/day, low sodium diet.\n"
        "5. Optimize GDMT as tolerated."
    ),
}

# Voice navigation commands
VOICE_COMMANDS = {
    "next field": ("Next Field", "Tab", "Navigates cursor to next template field"),
    "jump next": ("Next Field", "Tab", "Navigates cursor to next template field"),
    "next bracket": ("Next Field", "Tab", "Navigates cursor to next template bracket"),
    "previous field": ("Previous Field", "Shift+Tab", "Navigates cursor to previous field"),
    "prev field": ("Previous Field", "Shift+Tab", "Navigates cursor to previous field"),
    "scratch that": ("Scratch That", "Ctrl+Z", "Deletes previous spoken phrase / undo"),
    "delete that": ("Scratch That", "Ctrl+Z", "Deletes previous spoken phrase / undo"),
    "undo": ("Undo", "Ctrl+Z", "Undoes previous action"),
    "select all": ("Select All", "Ctrl+A", "Selects all text in active field"),
    "clear field": ("Clear Field", "Ctrl+A, Backspace", "Clears current active field"),
}

# Spoken punctuation mapping
PUNCTUATION_MAP = {
    "period": ".",
    "full stop": ".",
    "comma": ",",
    "colon": ":",
    "semicolon": ";",
    "semi colon": ";",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
    "new line": "\n",
    "newline": "\n",
    "new paragraph": "\n\n",
    "new para": "\n\n",
    "open paren": "(",
    "open parenthesis": "(",
    "close paren": ")",
    "close parenthesis": ")",
    "open bracket": "[",
    "close bracket": "]",
    "bullet": "• ",
    "number 1": "1. ",
    "num 1": "1. ",
    "number 2": "2. ",
    "num 2": "2. ",
    "number 3": "3. ",
    "num 3": "3. ",
    "number 4": "4. ",
    "num 4": "4. ",
}


class DragonLexer:
    """
    Finite-State Machine trapping commands, spoken punctuation, and vocal macros.
    """

    def __init__(self):
        self.capitalize_next = True
        self.last_typed_length = 0

    def process_transcription(self, raw_text: str) -> List[LexerAction]:
        """
        Processes incoming transcription text through the lookahead lexer.
        Returns a list of actions (Text to type/paste, or Commands triggered).
        """
        if not raw_text or not raw_text.strip():
            return []

        actions: List[LexerAction] = []
        tokens = raw_text.strip().split()
        i = 0
        n = len(tokens)

        current_words: List[str] = []

        def flush_current_words():
            if current_words:
                text_to_type = self._format_words(current_words)
                if text_to_type:
                    actions.append(LexerAction(action_type="TYPE_TEXT", text=text_to_type))
                current_words.clear()

        while i < n:
            # 1. Check 3-word combinations
            if i + 3 <= n:
                three_words = " ".join(tokens[i:i+3]).lower().rstrip(".,?!:;")
                if three_words in VOICE_COMMANDS:
                    flush_current_words()
                    cmd_name, hotkey, desc = VOICE_COMMANDS[three_words]
                    actions.append(LexerAction(
                        action_type="COMMAND_TRIGGERED",
                        trigger=three_words,
                        command_name=cmd_name,
                        hotkey=hotkey,
                        description=desc
                    ))
                    self.capitalize_next = True
                    i += 3
                    continue

            # 2. Check 2-word combinations
            if i + 2 <= n:
                two_words = " ".join(tokens[i:i+2]).lower().rstrip(".,?!:;")
                # Check 2-word commands
                if two_words in VOICE_COMMANDS:
                    flush_current_words()
                    cmd_name, hotkey, desc = VOICE_COMMANDS[two_words]
                    actions.append(LexerAction(
                        action_type="COMMAND_TRIGGERED",
                        trigger=two_words,
                        command_name=cmd_name,
                        hotkey=hotkey,
                        description=desc
                    ))
                    self.capitalize_next = True
                    i += 2
                    continue

                # Check 2-word macros
                if two_words in VOCAL_MACROS:
                    flush_current_words()
                    macro_text = VOCAL_MACROS[two_words]
                    actions.append(LexerAction(action_type="PASTE_TEXT", text=macro_text))
                    self.capitalize_next = True
                    i += 2
                    continue

                # Check 2-word punctuation (e.g. "new line", "new paragraph", "number 1")
                if two_words in PUNCTUATION_MAP:
                    punct = PUNCTUATION_MAP[two_words]
                    if punct in ("\n", "\n\n", "• ", "1. ", "2. ", "3. ", "4. "):
                        flush_current_words()
                        actions.append(LexerAction(action_type="TYPE_TEXT", text=punct))
                        self.capitalize_next = True
                    else:
                        current_words.append(punct)
                    i += 2
                    continue

            # 3. Check 1-word tokens
            token = tokens[i]
            token_clean = token.lower().rstrip(".,?!:;")

            # 1-word commands (e.g. "undo", "tab")
            if token_clean in VOICE_COMMANDS:
                flush_current_words()
                cmd_name, hotkey, desc = VOICE_COMMANDS[token_clean]
                actions.append(LexerAction(
                    action_type="COMMAND_TRIGGERED",
                    trigger=token_clean,
                    command_name=cmd_name,
                    hotkey=hotkey,
                    description=desc
                ))
                self.capitalize_next = True
                i += 1
                continue

            # 1-word punctuation (e.g. "period", "comma", "colon")
            if token_clean in PUNCTUATION_MAP:
                punct = PUNCTUATION_MAP[token_clean]
                if punct in (".", "?", "!"):
                    current_words.append(punct)
                    self.capitalize_next = True
                elif punct in (",", ":", ";"):
                    current_words.append(punct)
                elif punct in ("\n", "\n\n"):
                    flush_current_words()
                    actions.append(LexerAction(action_type="TYPE_TEXT", text=punct))
                    self.capitalize_next = True
                else:
                    current_words.append(punct)
                i += 1
                continue

            # Regular spoken word
            current_words.append(token)
            i += 1

        flush_current_words()
        return actions

    def _format_words(self, words: List[str]) -> str:
        """Formats word stream, handling spacing, punctuation, and capitalization."""
        if not words:
            return ""

        out = []
        for w in words:
            if w in (".", ",", ":", ";", "?", "!"):
                # Attach directly to previous word without leading space
                if out:
                    out[-1] = out[-1].rstrip() + w
                else:
                    out.append(w)
            elif w in ("(", "["):
                out.append(w)
            elif w in (")", "]"):
                if out:
                    out[-1] = out[-1].rstrip() + w
                else:
                    out.append(w)
            else:
                formatted_w = w
                if self.capitalize_next and len(formatted_w) > 0:
                    formatted_w = formatted_w[0].upper() + formatted_w[1:]
                    self.capitalize_next = False

                if formatted_w.endswith((".", "!", "?")):
                    self.capitalize_next = True

                out.append(formatted_w)

        res = " ".join(out)
        # Deduplicate accidental multiple punctuation (e.g. ".." -> ".")
        res = re.sub(r'\.\s*\.', '.', res)
        res = re.sub(r',\s*,', ',', res)
        res = re.sub(r'\s+([.,;:?!])', r'\1', res)
        return res
