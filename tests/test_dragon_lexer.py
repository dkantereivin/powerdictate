import pytest
from widget.lexer.dragon_fsm import DragonLexer, LexerAction


def test_lexer_spoken_punctuation():
    lexer = DragonLexer()
    actions = lexer.process_transcription("patient is alert comma oriented times three period new line plan is Lasix 40mg IV daily period")
    
    typed_chunks = [a.text for a in actions if a.action_type == "TYPE_TEXT"]
    full_text = "".join(typed_chunks)
    assert "alert, oriented times three." in full_text
    assert "Plan is Lasix 40mg IV daily." in full_text


def test_lexer_command_interception_and_token_suppression():
    lexer = DragonLexer()
    # Sentence with "next field" command in the middle
    actions = lexer.process_transcription("assessment and plan colon congestive heart failure next field Lasix 40mg IV daily")
    
    # 1. Verify command action was triggered
    cmd_actions = [a for a in actions if a.action_type == "COMMAND_TRIGGERED"]
    assert len(cmd_actions) == 1
    assert cmd_actions[0].command_name == "Next Field"
    assert cmd_actions[0].hotkey == "Tab"

    # 2. Verify command words "next field" were completely stripped from typed text
    typed_chunks = [a.text for a in actions if a.action_type == "TYPE_TEXT"]
    full_text = " ".join(typed_chunks)
    assert "next field" not in full_text.lower()
    assert "Assessment and plan: congestive heart failure" in full_text
    assert "Lasix 40mg IV daily" in full_text


def test_lexer_vocal_macro_expansion():
    lexer = DragonLexer()
    actions = lexer.process_transcription("physical examination colon no pe")
    
    paste_actions = [a for a in actions if a.action_type == "PASTE_TEXT"]
    assert len(paste_actions) == 1
    assert "Alert and oriented x3, no acute distress" in paste_actions[0].text
    assert "Pupils equal, round, reactive to light" in paste_actions[0].text
