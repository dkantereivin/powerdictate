import pytest
from src.ocr.meditech_parser import MeditechOCRParser


SAMPLE_MEDITECH_TERMINAL_TEXT = """
================================================================================
PATIENT INQUIRY                       MEDITECH C/S               01/09/2026
NAME: MCPHERSON, ELEANOR              MRN: 9876543               SEX: F
AGE: 68 YOF                           ATTENDING: PATEL, J DR     ROOM: 3B-12
--------------------------------------------------------------------------------
LABORATORY RESULTS:
  WBC: 11.2       HGB: 110       PLT: 250
  NA:  138        K:   4.2       CL:  102        HCO3: 24
  BUN: 8.2        CR:  140       EGFR: 42
  HS-CTN: 45      BNP: 380       INR: 1.1
================================================================================
"""


def test_meditech_terminal_parsing():
    parser = MeditechOCRParser()
    data = parser.parse(SAMPLE_MEDITECH_TERMINAL_TEXT)
    
    assert data.mrn == "9876543"
    assert data.patient_name == "MCPHERSON, ELEANOR"
    assert data.age == "68"
    assert data.sex == "F"
    
    # CBC
    assert data.cbc["wbc"] == "11.2"
    assert data.cbc["hgb"] == "110"
    assert data.cbc["plt"] == "250"
    
    # Lytes & Renal
    assert data.chem["na"] == "138"
    assert data.chem["k"] == "4.2"
    assert data.chem["cr"] == "140"
    assert data.chem["bun"] == "8.2"
    assert data.chem["egfr"] == "42"
    
    # Cardiac & Coags
    assert data.cardiac["troponin"] == "45"
    assert data.cardiac["bnp"] == "380"
    assert data.coag["inr"] == "1.1"
    
    snippet = data.to_formatted_note_snippet()
    assert "MCPHERSON, ELEANOR" in snippet
    assert "MRN: 9876543" in snippet
    assert "WBC: 11.2" in snippet
    assert "CR: 140" in snippet
