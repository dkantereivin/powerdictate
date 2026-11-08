"""
Extensive Medical Pronunciation & Expansion Dictionary
======================================================
Provides phonetically-tuned expansions for medications, clinical terminology,
anatomical references, and hospital acronyms to ensure 100% natural,
unambiguous pronunciation in Kokoro TTS.
"""

from typing import Dict, List, Tuple
import re

# Direct pronunciation replacements: only for terms that Kokoro's native G2P mispronounces.
# IMPORTANT: Never use hyphenated respellings (e.g. "meh-toe-pro-lol", "sef-try-axe-own")
# as hyphens force Kokoro to pause between syllables. Kokoro handles standard medical
# terminology (metoprolol, ceftriaxone, atorvastatin, dyspnea, etc.) natively and smoothly.
MEDICAL_PRONUNCIATION_MAP: Dict[str, str] = {
    # 1. Tricky Medications (clean, non-stuttering enunciation)
    "atorvastatin": "a torva statin",
    "cefazolin": "seh faz oh lin",
    "ketorolac": "kee toe roe lak",

    # 2. Clinical Terminology, Signs & Pathologies
    "hypoxemic": "hy pox ee mik",
    "hypoxemia": "hy pox ee mee uh",
    "orthopnea": "or thop nee uh",
    "hematochezia": "hemato keezia",
    "tachypneic": "tack ip nee ik",
    "conjunctivae": "con junk tie vee",
    "hepatosplenomegaly": "hepato spleno megaly",
    "nadir": "nay deer",
    "cardiorenal": "cardio renal",

    # 3. Microorganisms & Infectious Disease
    "c. diff": "C diff",
    "c.diff": "C diff",
    "clostridioides difficile": "clostridioides diffeeseel",
    "pseudomonas aeruginosa": "pseudomonas air-oo-jin-oh-suh",
    "klebsiella pneumoniae": "klebsiella new moe nee eye",
    "streptococcus pneumoniae": "Streptococcus new moe nee eye",
    "pneumoniae": "new moe nee eye",
    "diplococci": "diplo coki",
    "cocci": "coki",
    "streptococci": "strepto coki",
    "staphylococci": "staphylo coki",
    "escherichia coli": "E coli",
    "e. coli": "E coli",
    "e.coli": "E coli",
}


# Standalone acronyms and clinical abbreviations that must be pronounced cleanly
# Letters separated by '. ' to ensure slower, unhurried, crisp enunciation by Kokoro
CLINICAL_ACRONYMS_MAP: Dict[str, str] = {
    # Lab tests
    "egfr": "E. G. F. R.",
    "e-gfr": "E. G. F. R.",
    "bun": "B. U. N.",
    "cbc": "C. B. C.",
    "inr": "I. N. R.",
    "ptt": "P. T. T.",
    "aptt": "A. P. T. T.",
    "hco3": "Bicarbonate",
    "hco₃": "Bicarbonate",
    "hco₃⁻": "Bicarbonate",
    "hco3-": "Bicarbonate",
    "po4": "phosphate",
    "alt": "A. L. T.",
    "ast": "A. S. T.",
    "alp": "alkaline phosphatase",
    "alk phos": "alkaline phosphatase",
    "tsh": "T. S. H.",
    "ft4": "free T 4",
    "crp": "C. R. P.",
    "esr": "E. S. R.",
    "bnp": "B. N. P.",
    "nt-probnp": "N T pro B N P",
    "wbc": "W. B. C.",
    "hgb": "hemoglobin",
    "hb": "hemoglobin",
    "hct": "hematocrit",
    "plt": "platelets",
    "mcv": "M. C. V.",
    "anc": "absolute neutrophil count",

    # Arterial Blood Gas (ABG) user specific rules
    "paco2": "P A CO2",
    "paco₂": "P A CO2",
    "pao2": "P A O2",
    "pao₂": "P A O2",


    # Conditions & Diagnoses
    "copd": "C. O. P. D.",
    "stemi": "STEM-ee",
    "nstemi": "N-STEM-ee",
    "afib": "A Fib",
    "a-fib": "A Fib",
    "aflutter": "A flutter",
    "a-flutter": "A flutter",
    "chf": "C. H. F.",
    "hfref": "hefref",
    "hfpef": "hefpef",
    "ckd": "C. K. D.",
    "esrd": "E. S. R. D.",
    "aki": "A. K. I.",
    "dvt": "D. V. T.",
    "pe": "P. E.",
    "sob": "shortness of breath",
    "doe": "dyspnea on exertion",
    "pnd": "P. N. D.",
    "jvd": "J. V. D.",
    "cva": "C. V. A.",
    "tia": "T. I. A.",
    "gerd": "gerd",
    "ibd": "I. B. D.",
    "ibs": "I. B. S.",
    "uti": "U. T. I.",
    "bph": "B. P. H.",
    "osa": "O. S. A.",
    "cad": "coronary artery disease",
    "cabg": "cabbage",
    "pci": "P. C. I.",
    "svt": "S. V. T.",
    "vtach": "V tach",
    "v-tach": "V tach",
    "vfib": "V fib",
    "v-fib": "V fib",

    # Physical Exam findings
    "cta": "clear to auscultation",
    "rrr": "regular rate and rhythm",
    "perrl": "P. E. R. R. L.",
    "eomi": "E. O. M. I.",
    "nabs": "normoactive bowel sounds",

    # Prescription & Route Acronyms (kept as clean deliberate spoken letters)
    "po": "P. O.",
    "prn": "P. R. N.",
    "bid": "B. I. D.",
    "tid": "T. I. D.",
    "qid": "Q. I. D.",
    "qd": "Q. D.",
    "qhs": "Q. H. S.",
    "iv": "I. V.",
    "im": "I. M.",
    "subq": "sub Q",
    "sc": "S. C.",
    "npo": "N. P. O.",
    "stat": "stat",

    # Ambiguous or Rare Routes that SHOULD be clarified
    "sl": "sublingual",
    "it": "intrathecal",

    # Note Sections & Clinical Shorthand
    "hpi": "H. P. I.",
    "pmhx": "past medical history",
    "pshx": "past surgical history",
    "ros": "review of systems",
    "heent": "H. E. E. N. T.",
    "pod": "P. O. D.",
    "adls": "ay dee elzz",
    "adl": "ay dee el",
    "pmns": "P. M. Ns",
    "hap": "H. A. P.",
    "atn": "A. T. N.",
    "ards": "A. R. D. S.",
    "sfa": "S. F. A.",
    "lad": "L. A. D.",
    "icu": "I. C. U.",
    "micu": "M. I. C. U.",
    "facp": "F. A. C. P.",
    "md": "M. D.",
    "scds": "S. C. Ds",
    "bmp": "B. M. P.",
    "cmp": "C. M. P.",
    "abg": "A. B. G.",
    "ecg": "E. C. G.",
    "ekg": "E. K. G.",
    "map": "M. A. P.",
    "lvef": "L. V. E. F.",
    "nyha": "N. Y. H. A.",
    "kdigo": "K. D. I. G. O.",
    "t2dm": "type 2 diabetes mellitus",
    "mrsa": "M. R. S. A.",
    "vre": "V. R. E.",
    "esbl": "E. S. B. L.",
}


def apply_medical_dictionary(text: str) -> str:
    """
    Applies pronunciation corrections and medical acronym expansions.
    Operates with case-insensitivity on word boundaries.
    """
    # 1. Multi-word replacements first
    for key, repl in MEDICAL_PRONUNCIATION_MAP.items():
        if " " in key or "-" in key or "." in key:
            pattern = r'\b' + re.escape(key) + r'\b'
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 2. Single-word pronunciation corrections
    for key, repl in MEDICAL_PRONUNCIATION_MAP.items():
        if " " not in key and "-" not in key and "." not in key:
            pattern = r'\b' + re.escape(key) + r'\b'
            text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 3. Clinical Acronyms (strict word boundary)
    for key, repl in CLINICAL_ACRONYMS_MAP.items():
        pattern = r'\b' + re.escape(key) + r'\b'
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text
