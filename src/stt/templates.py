"""
Clinical Dot-Phrases, Voice Macros & Dynamic Template Library
==============================================================
Defines hospital-tested CTU / Internal Medicine macro templates with
dynamic '[ ... ]' field placeholders for Dragon-style voice navigation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Pattern
import re


@dataclass
class MacroTemplate:
    id: str
    name: str
    description: str
    trigger_patterns: List[str]
    replacement: str
    compiled_patterns: List[Pattern] = field(init=False, default_factory=list)

    def __post_init__(self):
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.trigger_patterns
        ]


# Comprehensive library of Clinical Power Phrases
CLINICAL_MACROS: Dict[str, MacroTemplate] = {
    "no_pe": MacroTemplate(
        id="no_pe",
        name="Negative PE Screen",
        description="Wells score & PERC rule evaluation for pulmonary embolism",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:no\s*p\s*e|negative\s*p\s*e|rule\s*out\s*p\s*e|\.no_pe)\b",
        ],
        replacement=(
            "• [No] cough / hemoptysis\n"
            "• [No] recent travel, surgery, or immobilization\n"
            "• [No] prior history of VTE / DVT / PE\n"
            "• [No] unilateral leg swelling / erythema\n"
            "--> Wells score: [ 0 ], PERC rule: [ Negative / Rule-out PE ]"
        ),
    ),
    "norm_card": MacroTemplate(
        id="norm_card",
        name="Normal Cardiac Exam",
        description="Standard cardiovascular physical examination findings",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:normal\s*cardiac|norm\s*card|normal\s*heart|cvs\s*exam|\.norm_card)\b",
        ],
        replacement=(
            "S1/S2 normal, regular rate and rhythm. No murmurs, rubs, or gallops. "
            "Peripheral pulses 2+ bilaterally. JVP [ flat / <3cm above sternal angle ]. No peripheral edema."
        ),
    ),
    "norm_resp": MacroTemplate(
        id="norm_resp",
        name="Normal Respiratory Exam",
        description="Standard pulmonary examination findings",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:normal\s*resp|normal\s*respiratory|normal\s*lungs|chest\s*exam|\.norm_resp)\b",
        ],
        replacement=(
            "Lungs clear to auscultation bilaterally. Normal vesicular breath sounds. "
            "No wheezes, crackles, or pleural friction rubs. Normal work of breathing on [ room air ]."
        ),
    ),
    "norm_neuro": MacroTemplate(
        id="norm_neuro",
        name="Normal Neurological Exam",
        description="Standard neurological screening examination",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:normal\s*neuro|normal\s*neurological|neuro\s*exam|\.norm_neuro)\b",
        ],
        replacement=(
            "Alert and oriented x3. GCS [ 15 ]. Cranial nerves II-XII grossly intact. "
            "Motor strength 5/5 in all four extremities. Sensation intact to light touch. "
            "Gait steady, cerebellar testing intact."
        ),
    ),
    "norm_gi": MacroTemplate(
        id="norm_gi",
        name="Normal Abdominal Exam",
        description="Standard gastrointestinal / abdominal physical examination",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:normal\s*abdomen|normal\s*gi|normal\s*belly|abdo\s*exam|\.norm_gi)\b",
        ],
        replacement=(
            "Abdomen soft, non-distended, non-tender to palpation throughout. "
            "Bowel sounds present in all four quadrants. No guarding, rigidity, rebound tenderness, or organomegaly."
        ),
    ),
    "hfref_plan": MacroTemplate(
        id="hfref_plan",
        name="Heart Failure (HFrEF) Plan",
        description="Acute decompensated heart failure management bundle",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:hfref\s*plan|heart\s*failure\s*plan|hf\s*plan|\.hfref_plan)\b",
        ],
        replacement=(
            "# Acute Decompensated Heart Failure (HFrEF)\n"
            "- Lasix [ 40 ] mg IV [ BID / daily ]\n"
            "- Fluid restrict to [ 1.5 ] L/day, strict I/O, daily morning weights\n"
            "- Target euvolemia; hold ACEi/ARB/ARNI if SBP < [ 100 ]\n"
            "- Transthoracic echocardiogram [ ordered / pending ]\n"
            "- Monitor electrolytes, BUN, and Creatinine daily"
        ),
    ),
    "copd_plan": MacroTemplate(
        id="copd_plan",
        name="COPD Exacerbation Plan",
        description="AECOPD acute management bundle",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:copd\s*plan|aecopd\s*plan|copd\s*exacerbation|\.copd_plan)\b",
        ],
        replacement=(
            "# Acute Exacerbation of COPD (AECOPD)\n"
            "- Prednisone [ 50 ] mg PO daily x 5 days\n"
            "- Ventolin [ 2.5 ] mg / Atrovent [ 500 ] mcg neb q4h PRN\n"
            "- Antibiotics: [ Azithromycin 500mg daily / Ceftriaxone 1g IV daily ]\n"
            "- Titrate supplemental O2 to target SpO2 [ 88-92% ]\n"
            "- Chest X-ray and sputum culture [ pending ]"
        ),
    ),
    "cap_plan": MacroTemplate(
        id="cap_plan",
        name="Pneumonia (CAP) Plan",
        description="Community-acquired pneumonia admission plan",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:cap\s*plan|pneumonia\s*plan|\.cap_plan)\b",
        ],
        replacement=(
            "# Community-Acquired Pneumonia (CAP)\n"
            "- Ceftriaxone [ 1g ] IV daily + Azithromycin [ 500mg ] PO/IV daily\n"
            "- CURB-65 score: [ 1 ]\n"
            "- Blood cultures x2 and sputum culture prior to antibiotics\n"
            "- Supplemental O2 to maintain SpO2 > [ 92% ]\n"
            "- Repeat chest radiography in [ 6 weeks ] outpatient"
        ),
    ),
    "order_bridge": MacroTemplate(
        id="order_bridge",
        name="NCR Order Sheet Bridge Reference",
        description="Standard 1-line bridge text for physical 50/50 NCR chart binder",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:order\s*bridge|chart\s*bridge|ncr\s*bridge|\.order_bridge)\b",
        ],
        replacement="CTU Consult — See attached typed note. Dictated / Meditech pending (Job #[XXX]).",
    ),
    "consult_header": MacroTemplate(
        id="consult_header",
        name="Consultation Note Header",
        description="Standard clinical consultation header",
        trigger_patterns=[
            r"\b(?:macro\s+|insert\s+|dot\s+)?(?:consult\s*header|new\s*consult|consult\s*template|\.consult_header)\b",
        ],
        replacement=(
            "CONSULT NOTE — [ INTERNAL MEDICINE / CTU ]\n\n"
            "Patient: [ Patient Name, Age, Sex ]\n"
            "MRN: [ ###### ]\n"
            "Referring Physician: [ Dr. Referring ]\n"
            "Consultant: [ Dr. Consultant ]\n"
            "Date of Consultation: [ September 1, 2026 ]\n\n"
            "Reason for Consultation: [ Chief Complaint / Consult Request ]\n\n"
            "History of Present Illness:\n[ HPI narrative ]\n\n"
            "Past Medical History:\n[ PMHx ]\n\n"
            "Medications:\n[ Current Medications ]\n\n"
            "Allergies:\n[ NKDA / Allergies ]\n\n"
            "Physical Examination:\n[ Vitals & Exam ]\n\n"
            "Diagnostic Investigations:\n[ Labs, Imaging, ECG ]\n\n"
            "Assessment and Plan:\n[ Problem List & Recommendations ]"
        ),
    ),
}
