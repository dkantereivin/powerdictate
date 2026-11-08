"""
Clinical Note Print Formatting Package
======================================
Provides multi-style clinical note rendering to vector PDF and Word .docx,
support for hospital templates (TBRHSC Consult Note, Progress Note, Clean Standard Note),
and local/network printing management.
"""

from printing.models import ClinicalNote, PatientMetadata, ClinicalSection, ClinicalProblem
from printing.parser import ClinicalNoteParser
from printing.templates import get_template, list_templates, DEFAULT_TEMPLATE_ID
from printing.pdf_generator import PdfGenerator
from printing.docx_generator import DocxGenerator
from printing.printer_service import PrinterService

__all__ = [
    "ClinicalNote",
    "PatientMetadata",
    "ClinicalSection",
    "ClinicalProblem",
    "ClinicalNoteParser",
    "get_template",
    "list_templates",
    "DEFAULT_TEMPLATE_ID",
    "PdfGenerator",
    "DocxGenerator",
    "PrinterService",
]
