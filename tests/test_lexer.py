import pytest
from src.stt.lexer import PowerPhraseLexer, LexerResult


def test_spoken_punctuation_parsing():
    lexer = PowerPhraseLexer()
    
    raw = "Patient presents with chest pain comma dyspnea comma and orthopnea period New paragraph Vitals are stable period"
    res = lexer.process(raw)
    
    assert res.expanded is False
    assert res.is_navigation_command is False
    assert "chest pain, dyspnea, and orthopnea." in res.text
    assert "\n\n" in res.text
    assert "Vitals are stable." in res.text


def test_power_phrase_macro_expansion():
    lexer = PowerPhraseLexer()
    
    # Test "macro no PE"
    res_pe = lexer.process("insert macro no PE")
    assert res_pe.expanded is True
    assert res_pe.macro_id == "no_pe"
    assert "Wells score" in res_pe.text
    assert "PERC rule" in res_pe.text
    assert res_pe.placeholders_count > 0
    
    # Test "normal cardiac"
    res_card = lexer.process("patient has normal cardiac exam")
    assert res_card.expanded is True
    assert res_card.macro_id == "norm_card"
    assert "S1/S2 normal" in res_card.text
    assert "No murmurs, rubs, or gallops" in res_card.text


def test_navigation_voice_commands():
    lexer = PowerPhraseLexer()
    
    res_tab = lexer.process("tab")
    assert res_tab.is_navigation_command is True
    assert res_tab.command_type == "next_field"
    
    res_next = lexer.process("next field")
    assert res_next.is_navigation_command is True
    assert res_next.command_type == "next_field"
    
    res_prev = lexer.process("previous field")
    assert res_prev.is_navigation_command is True
    assert res_prev.command_type == "prev_field"


def test_placeholder_hopping_and_replacement():
    lexer = PowerPhraseLexer()
    doc = "Lasix [ 40 ] mg IV [ BID / daily ] for target [ euvolemia ]"
    
    placeholders = lexer.find_all_placeholders(doc)
    assert len(placeholders) == 3
    assert placeholders[0][2] == "40"
    assert placeholders[1][2] == "BID / daily"
    assert placeholders[2][2] == "euvolemia"
    
    # Jump to first placeholder
    first = lexer.get_next_placeholder(doc, current_cursor=0)
    assert first is not None
    assert first[2] == "40"
    
    # Overwrite first placeholder with "80"
    updated_doc = lexer.replace_active_placeholder(doc, first[0], first[1], "80")
    assert "Lasix 80 mg IV [ BID / daily ]" in updated_doc
    
    # Jump to next placeholder after replacing
    second = lexer.get_next_placeholder(updated_doc, current_cursor=first[0] + 2)
    assert second is not None
    assert second[2] == "BID / daily"
