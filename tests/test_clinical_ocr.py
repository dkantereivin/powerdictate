import pytest
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from widget.ocr.engine import OcrEngine, OcrResult
from widget.ocr.meditech_parser import MeditechLabParser
from widget.ocr.llm_structurer import LLMStructurer
from widget.ui.dictation_box import DictationBoxWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def box(qapp):
    widget = DictationBoxWidget()
    yield widget
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


def test_rapid_ocr_engine_inference():
    # 1. Create a synthetic image with monospace hospital lab text
    img = Image.new("RGB", (600, 150), color=(11, 17, 32))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "SODIUM: 138   POTASSIUM: 4.1   CHLORIDE: 103", fill=(248, 250, 252))
    draw.text((20, 60), "CREATININE: 92   eGFR: >60", fill=(248, 250, 252))
    draw.text((20, 100), "WBC: 8.4   HGB: 128   PLT: 220", fill=(248, 250, 252))

    # 2. Run RapidOCR
    engine = OcrEngine()
    assert engine.available
    res = engine.recognize(img)

    assert not res.is_empty
    raw = res.raw_text.upper()
    assert "138" in raw
    assert "4.1" in raw
    assert "92" in raw
    assert "8.4" in raw


def test_meditech_deterministic_parser():
    raw_meditech = """
    CHEMISTRY / RENAL
    SODIUM        138   mmol/L       (135-145)
    POTASSIUM     4.1   mmol/L       (3.5-5.0)
    CHLORIDE      103   mmol/L       (98-107)
    CO2 TOTAL     24    mmol/L       (22-29)
    UREA          6.2   mmol/L       (2.5-8.0)
    CREATININE    92    umol/L       (60-110)
    eGFR          >60   mL/min/1.73m2(>60)
    GLUCOSE       5.6   mmol/L       (3.9-6.0)

    HEMATOLOGY
    WBC           14.2 H  x10^9/L    (4.0-11.0)
    HGB           115  L  g/L        (120-160)
    PLT           340     x10^9/L    (150-400)

    CARDIAC / COAGS
    TROPONIN      14   ng/L          (<14)
    INR           1.1
    PTT           28   sec
    """

    parsed = MeditechLabParser.parse_text(raw_meditech)
    assert "Lytes" in parsed
    assert "CBC" in parsed
    assert "Cardiac" in parsed
    assert "Coags" in parsed

    lytes = {v.name: v.value for v in parsed["Lytes"]}
    assert lytes["Na"] == "138"
    assert lytes["K"] == "4.1"
    assert lytes["Cl"] == "103"
    assert lytes["Cr"] == "92"
    assert lytes["eGFR"] == ">60"

    cbc = {v.name: (v.value, v.flag) for v in parsed["CBC"]}
    assert cbc["WBC"] == ("14.2", "H")
    assert cbc["Hgb"] == ("115", "L")
    assert cbc["Plt"] == ("340", "")

    # Audio dictation formatting
    formatted = MeditechLabParser.format_audio_dictation(parsed)
    assert "Labs: Na 138, K 4.1" in formatted
    assert "Lytes:" not in formatted
    assert "LFTs:" not in formatted
    assert "CBC: WBC 14.2 (H), Hgb 115 (L), Plt 340" in formatted
    assert "Cardiac: hs-Troponin 14" in formatted
    assert "Coags: INR 1.1, PTT 28" in formatted


def test_llm_ground_truth_verification():
    structurer = LLMStructurer()
    raw_ocr = "SODIUM 138 POTASSIUM 4.1 CREATININE 92 WBC 8.4 HGB 128"

    # Case 1: Ground-truth verified (all numbers are in raw OCR)
    valid_llm = "Lytes: Na 138, K 4.1, Cr 92\nCBC: WBC 8.4, Hgb 128"
    verified = structurer._verify_ground_truth(valid_llm, raw_ocr)
    assert "⚠️" not in verified
    assert verified == valid_llm

    # Case 2: Hallucinated number (Glucose 15.4 was NOT in raw OCR)
    hallucinated_llm = "Lytes: Na 138, K 4.1, Glucose 15.4"
    verified_hallucination = structurer._verify_ground_truth(hallucinated_llm, raw_ocr)
    assert "⚠️ [unverified value]" in verified_hallucination


def test_dictation_box_ocr_integration(box):
    box.text_edit.setPlainText("Patient admitted with AKI.\n")
    box.text_edit.moveCursor(box.text_edit.textCursor().MoveOperation.End)

    # Simulate OCR parsing completed signal
    parsed_sample = "Lytes: Na 138, K 4.1, Cl 103, HCO3 24, Cr 92, eGFR >60"
    box._on_ocr_completed(parsed_sample)

    full = box.text_edit.toPlainText()
    assert "Patient admitted with AKI." in full
    assert "Lytes: Na 138, K 4.1, Cl 103, HCO3 24, Cr 92, eGFR >60" in full
    assert "Ingested" in box.status_badge.text()


def test_real_world_meditech_screenshots():
    """Validates 100% extraction accuracy on the actual 3 patient screenshots in example/*.png."""
    import os
    from widget.ocr.tab_navigator import MeditechTabNavigator

    example_dir = "/home/david/Dev/Misc/powerdictate/example"
    if not os.path.exists(example_dir):
        pytest.skip("example/ directory not found")

    p1 = os.path.join(example_dir, "Screenshot From 2026-09-22 20-55-36.png")
    p2 = os.path.join(example_dir, "Screenshot From 2026-09-22 20-55-48.png")
    p3 = os.path.join(example_dir, "Screenshot From 2026-09-22 20-55-54.png")

    engine = OcrEngine.get_instance()

    # 1. Hematology Screen
    img1 = Image.open(p1)
    res1 = engine.recognize(img1)
    rep1 = MeditechLabParser.parse_report(res1.raw_text)
    assert rep1.timestamp == "1/11/25 08:03"
    assert "CBC" in rep1.panels
    cbc_vals = {v.name: (v.value, v.flag) for v in rep1.panels["CBC"]}
    assert cbc_vals["WBC"] == ("12.45", "H")
    assert cbc_vals["Hgb"][0] == "154"
    assert cbc_vals["Plt"][0] == "251"
    assert cbc_vals["Neut"] == ("10.55", "H")

    # Verify Tab detection on Page 1
    tabs1 = MeditechTabNavigator.detect_tabs(res1, img1)
    active1 = MeditechTabNavigator.get_active_tab(tabs1)
    assert active1 is not None and active1.name == "Hematology"

    # 2. Chemistry Screen
    img2 = Image.open(p2)
    res2 = engine.recognize(img2)
    rep2 = MeditechLabParser.parse_report(res2.raw_text)
    assert rep2.timestamp == "1/11/25 08:03"
    assert "Lytes" in rep2.panels
    assert "LFTs" in rep2.panels
    lytes_vals = {v.name: (v.value, v.flag) for v in rep2.panels["Lytes"]}
    assert lytes_vals["Na"][0] == "140"
    assert lytes_vals["K"][0] == "4.4"
    assert lytes_vals["Cl"][0] == "105"
    assert lytes_vals["HCO3"][0] == "27"
    assert lytes_vals["BUN"] == ("8.6", "H")
    assert lytes_vals["Cr"][0] == "84.2"
    assert lytes_vals["eGFR"][0] == "102"
    assert lytes_vals["Glu"][0] == "6.3"
    assert lytes_vals["Ca"][0] == "2.31"
    assert lytes_vals["PO4"][0] == "0.86"
    assert lytes_vals["Mg"][0] == "0.78"

    lft_vals = {v.name: v.value for v in rep2.panels["LFTs"]}
    assert lft_vals["Total Bili"] == "12"
    assert lft_vals["ALT"] == "35"
    assert lft_vals["ALP"] == "59"
    assert lft_vals["Total Protein"] == "81"
    assert lft_vals["Albumin"] == "47"
    assert lft_vals["Lipase"] == "51"

    # Verify Tab detection on Page 2
    tabs2 = MeditechTabNavigator.detect_tabs(res2, img2)
    active2 = MeditechTabNavigator.get_active_tab(tabs2)
    assert active2 is not None and active2.name == "Chemistry"

    # 3. Coagulation Screen
    img3 = Image.open(p3)
    res3 = engine.recognize(img3)
    rep3 = MeditechLabParser.parse_report(res3.raw_text)
    assert rep3.timestamp == "1/11/25 08:03"
    assert "Coags" in rep3.panels
    coags_vals = {v.name: v.value for v in rep3.panels["Coags"]}
    assert coags_vals["INR"] == "1.0"
    assert coags_vals["PTT"] == "28"

    # Verify Tab detection on Page 3
    tabs3 = MeditechTabNavigator.detect_tabs(res3, img3)
    active3 = MeditechTabNavigator.get_active_tab(tabs3)
    assert active3 is not None and active3.name == "Coagulation"

    # 4. Multi-Page Unified Merging
    merged = MeditechLabParser.merge_reports([rep1, rep2, rep3])
    audio_output = merged.to_audio_dictation()

    assert "Lytes:" not in audio_output
    assert "LFTs:" not in audio_output
    assert "Labs (1/11/25 08:03): Na 140, K 4.4, Cl 105, HCO3 27, Anion Gap 8, BUN 8.6 (H), Cr 84.2, eGFR 102, CrCl 102.00, Glu 6.3, Ca 2.31, PO4 0.86, Mg 0.78, Total Bili 12, ALT 35, ALP 59, Total Protein 81, Albumin 47, Lipase 51" in audio_output
    assert "CBC (1/11/25 08:03): WBC 12.45 (H), Hgb 154, Hct 0.44, Plt 251, MCV 88, Neut 10.55 (H), Lymph 1.05, Mono 0.74, Eos 0.04, Baso 0.04, Immature Gran 0.03, MCH 31.0, MCHC 352, RDW 10.9, MPV 9.9, NRBC <0.01" in audio_output
    assert "Coags (1/11/25 08:03): INR 1.0, PTT 28" in audio_output


def test_dictation_box_batch_mode_flow(box):
    """Verifies batch snip accumulation and UI button state changes."""
    assert box.batch_btn.text() == "📑 Batch Snip"

    # 1. Start batch mode
    box.toggle_batch_mode()
    assert box.ocr_service.is_batch_mode
    assert "0" in box.batch_btn.text()

    # 2. Simulate 2 pages captured
    box._on_batch_updated(1, "Lytes")
    assert "1" in box.batch_btn.text()
    assert "Page 1 Added" in box.status_badge.text()

    box._on_batch_updated(2, "CBC")
    assert "2" in box.batch_btn.text()

    # 3. Simulate completion insertion
    merged_text = "Labs (1/11/25 08:03):\nLytes: Na 140, K 4.4\nCBC: WBC 12.45 (H)"
    box._on_ocr_completed(merged_text)

    assert box.batch_btn.text() == "📑 Batch Snip"
    full = box.text_edit.toPlainText()
    assert "Labs (1/11/25 08:03):" in full
    assert "CBC: WBC 12.45 (H)" in full


def test_llm_transformer_and_selection(box):
    """Verifies LLM text transformation on lab outputs and selection replacement."""
    from PySide6.QtGui import QTextCursor
    from widget.ocr.llm_transformer import LLMTransformer

    raw_labs = (
        "Labs (1/11/25 08:03): Na 140, K 4.4, Cl 105, HCO3 27, Anion Gap 8, BUN 8.6 (H), Cr 84.2, eGFR 102, CrCl 102.00, Glu 6.3, Ca 2.31, PO4 0.86, Mg 0.78, Total Bili 12, ALT 35, ALP 59, Total Protein 81, Albumin 47, Lipase 51\n"
        "CBC (1/11/25 08:03): WBC 12.45 (H), Hgb 154, Hct 0.44, Plt 251, MCV 88, Neut 10.55 (H), Lymph 1.05, Mono 0.74, Eos 0.04, Baso 0.04, Immature Gran 0.03\n"
        "Coags (1/11/25 08:03): INR 1.0, PTT 28"
    )

    transformer = LLMTransformer()
    # 1. Transform pertinent labs
    filtered = transformer.transform(raw_labs, preset="pertinent_labs")
    assert "WBC 12.45 (H), Hgb 154, Plt 251, Neut 10.55 (H)" in filtered
    assert "Mono 0.74" not in filtered  # Routine normal diff omitted by LLM transformer
    assert "Baso 0.04" not in filtered

    # 2. Test in DictationBox with text selection
    box.text_edit.setPlainText(raw_labs)
    doc_text = box.text_edit.toPlainText()
    cbc_start = doc_text.index("CBC (")
    cbc_end = doc_text.index("Coags (")
    cursor = box.text_edit.textCursor()
    cursor.setPosition(cbc_start)
    cursor.setPosition(cbc_end, QTextCursor.MoveMode.KeepAnchor)
    box.text_edit.setTextCursor(cursor)

    # Run transform on selection
    box.run_llm_transform(preset="pertinent_labs")
    qapp = QApplication.instance()
    qapp.processEvents()

    assert "Transforming" in box.status_badge.text() or "Transformed" in box.status_badge.text()


def test_screenshot_file_deleted_after_parsing(tmp_path, box):
    """Verifies any temporary screenshot file created during capture is deleted once parsing completes."""
    from widget.ocr.service import OcrWorker

    # Create dummy screenshot on disk
    temp_img_file = tmp_path / "portal_screenshot_test.png"
    img = Image.new("RGB", (100, 100), color="white")
    img.save(temp_img_file)
    assert temp_img_file.exists()

    # Load into PIL and attach source path as portal snipper does
    loaded_img = Image.open(temp_img_file)
    loaded_img._source_file_path = str(temp_img_file)

    worker = OcrWorker(loaded_img, parent=box)
    worker.start()
    worker.wait(5000)

    # Verify the temporary file was securely deleted upon parsing completion
    assert not temp_img_file.exists()
