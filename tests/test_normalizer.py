import pytest
from src.tts.normalizer import ClinicalTextNormalizer, NormalizationMode


def test_rx_dosages_and_routes_normalization():
    norm = ClinicalTextNormalizer(mode=NormalizationMode.DICTATION)
    raw = "Tazocin 3.375g IV q8h; Lasix 40mg PO daily; empagliflozin 10mg PO daily."
    res = norm.normalize(raw)
    
    assert "three point three seven five grams" in res
    assert "intravenously" in res
    assert "every eight hours" in res
    assert "forty milligrams" in res
    assert "by mouth" in res
    assert "ten milligrams" in res
    assert "period" in res


def test_vitals_normalization():
    norm = ClinicalTextNormalizer(mode=NormalizationMode.DICTATION)
    raw = "Vitals: BP 138/74, HR 82, SpO2 96% on 2L NP, T 37.2 C, RR 18, GCS 15."
    res = norm.normalize(raw)
    
    assert "blood pressure 138 over 74" in res
    assert "heart rate 82" in res
    assert "oxygen saturation 96 percent on 2 liters nasal prongs" in res
    assert "temperature 37.2 degrees" in res
    assert "respiratory rate 18" in res
    assert "G C S 15" in res


def test_labs_normalization():
    norm = ClinicalTextNormalizer(mode=NormalizationMode.DICTATION)
    raw = "Labs: K+ 4.2, Na 138, Cr 140, eGFR 42, Hgb 110, WBC 11.2, Plt 250, INR 1.1, hs-cTn 45."
    res = norm.normalize(raw)
    
    assert "potassium 4.2" in res
    assert "sodium 138" in res
    assert "creatinine 140" in res
    assert "G F R 42" in res
    assert "hemoglobin 110" in res
    assert "white blood cell count 11.2" in res
    assert "platelets 250" in res
    assert "I N R 1.1" in res
    assert "troponin 45" in res


def test_ward_vs_dictation_mode():
    raw = "Patient has HFrEF. Start Lasix 40mg PO daily."
    
    dict_norm = ClinicalTextNormalizer(mode=NormalizationMode.DICTATION)
    dict_res = dict_norm.normalize(raw)
    assert "period" in dict_res
    
    ward_norm = ClinicalTextNormalizer(mode=NormalizationMode.WARD_REVIEW)
    ward_res = ward_norm.normalize(raw)
    assert "period" not in ward_res
    assert "." in ward_res
