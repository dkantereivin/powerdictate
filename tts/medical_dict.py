"""
Extensive Medical Pronunciation & Expansion Dictionary
======================================================
Provides phonetically-tuned expansions for medications, clinical terminology,
anatomical references, and hospital acronyms to ensure 100% natural,
unambiguous pronunciation in Kokoro TTS.
"""

from typing import Dict, List, Tuple
import re

# Direct pronunciation replacements: maps lowercased clinical word -> phonetically friendly string
MEDICAL_PRONUNCIATION_MAP: Dict[str, str] = {
    # 1. Complex/Tricky Medications
    "metoprolol": "meh-toe-pro-lol",
    "atorvastatin": "uh-tor-vuh-stat-in",
    "rosuvastatin": "roe-soo-vuh-stat-in",
    "furosemide": "fyoor-oh-suh-mide",
    "pantoprazole": "pan-toe-pruh-zole",
    "omeprazole": "oh-meh-pruh-zole",
    "ceftriaxone": "sef-try-axe-own",
    "cefazolin": "sef-az-oh-lin",
    "cefepime": "sef-eh-peem",
    "piperacillin": "pipe-er-uh-sil-in",
    "tazobactam": "taz-oh-back-tam",
    "piperacillin-tazobactam": "pipe-er-uh-sil-in taz-oh-back-tam",
    "pip-tazo": "pip-tazo",
    "enoxaparin": "ee-nox-uh-par-in",
    "amiodarone": "am-ee-oh-duh-rone",
    "levothyroxine": "lee-voe-thye-rox-een",
    "apixaban": "uh-pix-uh-ban",
    "rivaroxaban": "riv-uh-rox-uh-ban",
    "dabigatran": "da-bi-gat-ran",
    "clopidogrel": "kloh-pid-oh-grel",
    "hydrochlorothiazide": "hydro-chloro-thiazide",
    "spironolactone": "speer-on-oh-lak-tone",
    "lisinopril": "ly-sin-oh-pril",
    "ramipril": "ram-ih-pril",
    "hydromorphone": "hydro-morphone",
    "ondansetron": "on-dan-seh-tron",
    "ipratropium": "ip-ruh-troe-pee-um",
    "salbutamol": "sal-byoo-tuh-mol",
    "albuterol": "al-byoo-ter-ol",
    "diltiazem": "dil-tye-uh-zem",
    "amlodipine": "am-lod-ih-peen",
    "vancomycin": "van-koe-my-sin",
    "meropenem": "mer-oh-pen-em",
    "azithromycin": "uh-zith-roe-my-sin",
    "ciprofloxacin": "sip-roe-flox-uh-sin",
    "moxifloxacin": "mox-ee-flox-uh-sin",

    # 2. Clinical Signs, Symptoms, Pathologies & Greek/Latin Terms
    "dyspnea": "disp-nee-uh",
    "tachypnea": "tack-ip-nee-uh",
    "tachypneic": "tack-ip-neek",
    "bradypnea": "bray-dip-nee-uh",
    "cachectic": "kuh-kek-tik",
    "cachexia": "kuh-kex-ee-uh",
    "pruritus": "proo-rye-tus",
    "aphasia": "uh-fay-zhuh",
    "dysarthria": "dis-arth-ree-uh",
    "dysphagia": "dis-fay-zhuh",
    "diaphoresis": "dye-uh-for-ee-sis",
    "diaphoretic": "dye-uh-for-et-ik",
    "thrombocytopenia": "throm-boe-sye-toe-pee-nee-uh",
    "leukocytosis": "loo-koe-sye-toe-sis",
    "hypokalemia": "high-poe-kuh-lee-mee-uh",
    "hyperkalemia": "high-per-kuh-lee-mee-uh",
    "hyponatremia": "high-poe-nuh-tree-mee-uh",
    "hypernatremia": "high-per-nuh-tree-mee-uh",
    "hypomagnesemia": "high-poe-mag-neh-see-mee-uh",
    "choledocholithiasis": "koe-led-uh-koe-lith-eye-uh-sis",
    "cholecystectomy": "koe-luh-sis-tek-tuh-mee",
    "cholecystitis": "koe-luh-sis-tye-tis",
    "diverticulitis": "dye-ver-tik-yoo-lye-tis",
    "erythema": "air-ih-thee-muh",
    "erythematous": "air-ih-them-uh-tus",
    "ecchymosis": "ek-ih-moe-sis",
    "syncope": "sin-kuh-pee",
    "syncopal": "sin-kuh-pul",
    "lymphadenopathy": "lim-fad-eh-nop-uh-thee",
    "splenomegaly": "spleen-oh-meg-uh-lee",
    "hepatomegaly": "heh-pat-oh-meg-uh-lee",
    "hepatosplenomegaly": "heh-pat-oh-spleen-oh-meg-uh-lee",
    "bacteremia": "back-ter-ee-mee-uh",
    "petechiae": "peh-tee-kee-eye",
    "tinnitus": "tih-nye-tus",
    "vertigo": "ver-tih-go",
    "ischemia": "is-kee-mee-uh",
    "ischemic": "is-kee-mik",
    "auscultation": "os-kul-tay-shun",
    "tachycardia": "tack-ih-kar-dee-uh",
    "bradycardia": "bray-dih-kar-dee-uh",
    "paresthesia": "pair-ess-thee-zhuh",
    "paresthesias": "pair-ess-thee-zhuhs",

    # 3. Microorganisms & Infectious Disease
    "c. diff": "C diff",
    "c.diff": "C diff",
    "clostridioides difficile": "clostridioides diff-ih-seel",
    "mrsa": "M R S A",
    "vre": "V R E",
    "esbl": "E S B L",
    "pseudomonas aeruginosa": "soo-doe-moe-nas air-oo-jin-oh-suh",
    "klebsiella pneumoniae": "kleb-see-ell-uh new-moe-nee-eye",
    "escherichia coli": "E coli",
    "e. coli": "E coli",
    "e.coli": "E coli",
}

# Standalone acronyms and clinical abbreviations that must be pronounced cleanly
# (e.g. separated by spaces so Kokoro does not pronounce them as nonsense words)
CLINICAL_ACRONYMS_MAP: Dict[str, str] = {
    # Lab tests
    "egfr": "E G F R",
    "e-gfr": "E G F R",
    "bun": "B U N",
    "cbc": "C B C",
    "inr": "I N R",
    "ptt": "P T T",
    "aptt": "A P T T",
    "hco3": "bicarbonate",
    "po4": "phosphate",
    "alt": "A L T",
    "ast": "A S T",
    "alp": "alkaline phosphatase",
    "alk phos": "alkaline phosphatase",
    "tsh": "T S H",
    "ft4": "free T 4",
    "crp": "C R P",
    "esr": "E S R",
    "bnp": "B N P",
    "nt-probnp": "N T pro B N P",
    "wbc": "W B C",
    "hgb": "hemoglobin",
    "hb": "hemoglobin",
    "hct": "hematocrit",
    "plt": "platelets",
    "mcv": "M C V",
    "anc": "absolute neutrophil count",

    # Conditions & Diagnoses
    "copd": "C O P D",
    "stemi": "STEM-ee",
    "nstemi": "N-STEM-ee",
    "afib": "A Fib",
    "a-fib": "A Fib",
    "aflutter": "A flutter",
    "a-flutter": "A flutter",
    "chf": "C H F",
    "hfref": "H F ref",
    "hfpef": "H F pef",
    "ckd": "C K D",
    "esrd": "E S R D",
    "aki": "A K I",
    "dvt": "D V T",
    "pe": "P E",
    "sob": "shortness of breath",
    "doe": "dyspnea on exertion",
    "pnd": "P N D",
    "jvd": "J V D",
    "cva": "C V A",
    "tia": "T I A",
    "gerd": "gerd",
    "ibd": "I B D",
    "ibs": "I B S",
    "uti": "U T I",
    "bph": "B P H",
    "osa": "O S A",
    "cad": "coronary artery disease",
    "cabg": "cabbage",
    "pci": "P C I",
    "svt": "S V T",
    "vtach": "V tach",
    "v-tach": "V tach",
    "vfib": "V fib",
    "v-fib": "V fib",

    # Physical Exam findings
    "cta": "clear to auscultation",
    "rrr": "regular rate and rhythm",
    "perrl": "P E R R L",
    "eomi": "E O M I",
    "nabs": "normoactive bowel sounds",

    # Prescription & Route Acronyms (kept as clean spoken letters, NOT over-expanded)
    "po": "P O",
    "prn": "P R N",
    "bid": "B I D",
    "tid": "T I D",
    "qid": "Q I D",
    "qd": "Q D",
    "qhs": "Q H S",
    "iv": "I V",
    "im": "I M",
    "subq": "sub Q",
    "sc": "S C",
    "npo": "N P O",
    "stat": "stat",

    # Ambiguous or Rare Routes that SHOULD be clarified
    "sl": "sublingual",
    "it": "intrathecal",
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
