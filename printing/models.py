"""
Clinical Note Print Data Models
===============================
Structured data representations for clinical notes, patient demographics,
vitals, problems, and sections for multi-style document rendering.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import datetime


@dataclass
class PatientMetadata:
    """Demographics, hospital metadata, and provider credentials."""
    patient_name: str = ""
    mrn: str = ""
    hcn: str = ""                         # Health Card / OHIP Number
    dob: str = ""
    age_gender: str = ""                  # e.g. "72-year-old male"
    room_bed: str = ""                    # e.g. "2B-14" / "Unit 3A"
    date: str = ""
    time: str = ""
    hospital_name: str = "Thunder Bay Regional Health Sciences Centre"
    department: str = "Department of Internal Medicine"
    service: str = "Internal Medicine Consultation Service"
    ward_unit: str = "Medicine Clinical Teaching Unit (MCTU)"
    requesting_service: str = ""          # e.g. "Orthopedic Surgery"
    requesting_physician: str = ""        # e.g. "Dr. Sarah Jenkins"
    reason_for_consult: str = ""          # e.g. "Multifocal pneumonia & AKI"
    dictating_physician: str = "David Kanter Eivin, PGY1"
    attending_physician: str = "Dr. Vandermeer, MCTU Staff"
    hospital_day: str = ""                # e.g. "HD# 3"
    postop_day: str = ""                  # e.g. "POD# 3"
    allergies: str = ""
    code_status: str = "Full Code"

    def __post_init__(self):
        if not self.date:
            self.date = datetime.date.today().strftime("%B %d, %Y")
        if not self.time:
            self.time = datetime.datetime.now().strftime("%H:%M")


@dataclass
class ClinicalProblem:
    """An individual active clinical issue or assessment/plan item."""
    number: int = 1
    title: str = ""
    status: str = ""                      # e.g. "Improving", "Active", "Resolving"
    bullets: List[str] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class ClinicalSection:
    """A standard clinical documentation section."""
    title: str = ""
    raw_content: str = ""
    paragraphs: List[str] = field(default_factory=list)
    bullets: List[str] = field(default_factory=list)
    subsections: List["ClinicalSection"] = field(default_factory=list)


@dataclass
class ClinicalNote:
    """Root structured representation of a clinical document."""
    raw_text: str = ""
    title: str = "CLINICAL NOTE"
    note_type: str = "consult"            # "consult", "progress", "general"
    preamble: str = ""                    # e.g. "THIS IS DAVID KANTER EIVIN DICTATING..."
    metadata: PatientMetadata = field(default_factory=PatientMetadata)
    sections: List[ClinicalSection] = field(default_factory=list)
    vitals: Dict[str, str] = field(default_factory=dict)
    allergies_list: List[str] = field(default_factory=list)
    problems: List[ClinicalProblem] = field(default_factory=list)
    assessment_summary: str = ""
    attestation_statement: str = ""
    signature_name: str = ""
    signature_title: str = ""
    signature_pager: str = ""
