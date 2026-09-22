import pytest
from widget.lexer.rule_engine import MedicalRuleEngine


def test_rule_engine_loading_and_normalization():
    engine = MedicalRuleEngine()
    
    # 1. Phonetic compound + dosage + abbreviation normalization
    raw = "patient received ferosa mide forty melegrams pi o and meto pro lol bid"
    norm = engine.normalize_text(raw)
    
    assert "furosemide" in norm
    assert "40 mg" in norm
    assert "PO" in norm
    assert "metoprolol" in norm
    assert "BID" in norm


def test_rule_engine_context_aware_insertion():
    engine = MedicalRuleEngine()

    # Scenario A: Inserting mid-sentence (after 'presents with ')
    prefix = "Patient presents with "
    suffix = "chest pain."
    inserted = engine.format_insertion_context(prefix, "Severe Exertional", suffix)
    
    # First letter should be lowercased to match mid-sentence flow, with proper spacing
    assert inserted.strip().startswith("severe")
    
    # Scenario B: Inserting at start of new sentence (after a period)
    prefix_sentence_end = "Patient is alert and oriented. "
    suffix_empty = ""
    inserted_start = engine.format_insertion_context(prefix_sentence_end, "plan is Lasix", suffix_empty)
    
    # First letter should be capitalized
    assert inserted_start.strip().startswith("Plan")
    assert "Lasix" in inserted_start

    # Scenario C: Inserting an acronym mid-sentence (e.g. 'IV')
    inserted_acronym = engine.format_insertion_context("administered ", "iv lasix", " immediately")
    assert "IV" in inserted_acronym
    assert "Lasix" in inserted_acronym
