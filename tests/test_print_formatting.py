"""
Tests for Clinical Print Formatting & Document Generation
=========================================================
Tests parsing of clinical notes, template rendering (TBRHSC Consult, Progress Note, Clean Note),
vector PDF generation, and Microsoft Word DOCX generation.
"""

import os
from pathlib import Path
import pytest
from printing.models import ClinicalNote, PatientMetadata
from printing.parser import ClinicalNoteParser
from printing.templates import get_template, list_templates
from printing.pdf_generator import PdfGenerator
from printing.docx_generator import DocxGenerator
from printing.printer_service import PrinterService


SAMPLE_NOTE_TEXT = """THIS IS DAVID KANTER EIVIN DICTATING ON BEHALF OF DR. VANDERMEER, MCTU STAFF

**INTERNAL MEDICINE CONSULTATION NOTE**

**DATE OF CONSULTATION:** September 22, 2026
**REQUESTING SERVICE:** Orthopedic Surgery
**REQUESTING PHYSICIAN:** Sarah Jenkins, MD
**REASON FOR CONSULTATION:** Acute kidney injury and multifocal pneumonia.

---

### IDENTIFYING DATA & DEMOGRAPHICS
The patient is a 72-year-old male POD 3 right total hip arthroplasty.

### HISTORY OF PRESENT ILLNESS (HPI)
Patient developed low grade fever and productive cough. Creatinine acutely rose to 3.2 mg/dL.

### ALLERGIES / ADVERSE REACTIONS
* **Penicillin:** Hives / Urticaria (childhood).
* **Codeine:** Severe nausea / emesis.

### PHYSICAL EXAMINATION
BP: 104/62 mmHg | HR: 108 bpm | Temp: 38.6 °C | RR: 26 | SpO2: 91% on room air

### ASSESSMENT & PLAN
1. **Multifocal Pneumonia:** Empiric cefepime and vancomycin.
2. **Acute Kidney Injury (KDIGO 3):** Hold nephrotoxic medications, avoid NSAIDs.

---

**Alexander Reed, MD, FACP**
Department of Internal Medicine
Pager: #4412
"""


def test_note_parser():
    note = ClinicalNoteParser.parse(SAMPLE_NOTE_TEXT)
    assert "INTERNAL MEDICINE CONSULTATION" in note.title
    assert "David Kanter Eivin" in note.metadata.dictating_physician
    assert "Vandermeer" in note.metadata.attending_physician
    assert "Orthopedic" in note.metadata.requesting_service
    assert "Sarah Jenkins" in note.metadata.requesting_physician
    assert "kidney" in note.metadata.reason_for_consult.lower()
    assert len(note.allergies_list) == 2
    assert "BP" in note.vitals
    assert "104/62" in note.vitals["BP"]
    assert len(note.problems) >= 2
    assert "Alexander Reed" in note.signature_name


def test_template_registry():
    templates = list_templates()
    ids = [t["id"] for t in templates]
    assert "tbrhsc_consult" in ids
    assert "progress_note" in ids
    assert "clean_note" in ids

    tpl = get_template("tbrhsc_consult")
    assert tpl.name == "TBRHSC Consult Note"

    tpl2 = get_template("progress_note")
    assert tpl2.name == "Progress Note"


def test_tbrhsc_consult_html():
    note = ClinicalNoteParser.parse(SAMPLE_NOTE_TEXT)
    tpl = get_template("tbrhsc_consult")
    html_out = tpl.render_html(note)
    assert "THUNDER BAY REGIONAL HEALTH SCIENCES CENTRE" in html_out
    assert "CONSULTATION NOTE" in html_out
    assert "REASON FOR CONSULTATION" in html_out
    assert "Penicillin" in html_out
    assert "Alexander Reed" in html_out


def test_progress_note_html():
    note = ClinicalNoteParser.parse(SAMPLE_NOTE_TEXT)
    tpl = get_template("progress_note")
    html_out = tpl.render_html(note)
    assert "PROGRESS NOTE" in html_out
    assert "TELEMETRY / VITALS" in html_out
    assert "HISTORY OF PRESENT ILLNESS" in html_out


def test_pdf_generation(tmp_path):
    note = ClinicalNoteParser.parse(SAMPLE_NOTE_TEXT)
    out_file = str(tmp_path / "test_consult.pdf")
    res = PdfGenerator.generate_pdf(note, "tbrhsc_consult", out_file)
    assert os.path.exists(res)
    assert os.path.getsize(res) > 1000  # valid PDF generated


def test_docx_generation(tmp_path):
    note = ClinicalNoteParser.parse(SAMPLE_NOTE_TEXT)
    out_file = str(tmp_path / "test_consult.docx")
    res = DocxGenerator.generate_docx(note, "tbrhsc_consult", out_file)
    assert os.path.exists(res)
    assert os.path.getsize(res) > 1000  # valid Word doc generated


def test_printer_discovery():
    printers = PrinterService.get_available_printers()
    assert isinstance(printers, list)
    # MFC-9320CW is installed on this system
    assert "MFC-9320CW" in printers
