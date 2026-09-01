"""
Meditech Client/Server Monospace Terminal OCR Parser
====================================================
Extracts structured patient demographics and lab values from legacy
Meditech green/purple monospace terminal windows (running inside remote Citrix sessions).
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List


@dataclass
class MeditechParsedData:
    mrn: Optional[str] = None
    patient_name: Optional[str] = None
    age: Optional[str] = None
    sex: Optional[str] = None
    attending_physician: Optional[str] = None
    vitals: Dict[str, str] = field(default_factory=dict)
    cbc: Dict[str, str] = field(default_factory=dict)
    chem: Dict[str, str] = field(default_factory=dict)
    cardiac: Dict[str, str] = field(default_factory=dict)
    coag: Dict[str, str] = field(default_factory=dict)
    raw_ocr_text: str = ""

    def to_formatted_note_snippet(self) -> str:
        """Generates structured clinical text block ready for note insertion."""
        lines = []
        if self.patient_name or self.mrn or self.age:
            header_parts = []
            if self.patient_name:
                header_parts.append(f"Patient: {self.patient_name}")
            if self.age and self.sex:
                header_parts.append(f"({self.age}yo {self.sex})")
            elif self.age:
                header_parts.append(f"({self.age}yo)")
            if self.mrn:
                header_parts.append(f"MRN: {self.mrn}")
            lines.append(" | ".join(header_parts))
            lines.append("")

        if self.vitals:
            v_str = ", ".join(f"{k.upper()}: {v}" for k, v in self.vitals.items())
            lines.append(f"Vitals: {v_str}")

        if self.cbc:
            c_str = ", ".join(f"{k.upper()}: {v}" for k, v in self.cbc.items())
            lines.append(f"CBC: {c_str}")

        if self.chem:
            ch_str = ", ".join(f"{k.upper()}: {v}" for k, v in self.chem.items())
            lines.append(f"Lytes/Renal: {ch_str}")

        if self.cardiac:
            car_str = ", ".join(f"{k.upper()}: {v}" for k, v in self.cardiac.items())
            lines.append(f"Cardiac: {car_str}")

        if self.coag:
            coag_str = ", ".join(f"{k.upper()}: {v}" for k, v in self.coag.items())
            lines.append(f"Coags: {coag_str}")

        return "\n".join(lines).strip()


class MeditechOCRParser:
    """
    Parses OCR text extracted from Meditech terminal screens.
    """

    def parse(self, ocr_text: str) -> MeditechParsedData:
        data = MeditechParsedData(raw_ocr_text=ocr_text)

        # 1. Demographics: MRN (6 to 9 digits)
        mrn_m = re.search(r'\b(?:MRN|UNIT|CHART|ACCT)[:\s#]*(\d{6,9})\b', ocr_text, re.IGNORECASE)
        if mrn_m:
            data.mrn = mrn_m.group(1)

        # Name: NAME: LAST, FIRST or LAST, FIRST M
        name_m = re.search(r'\bNAME[:\s]+([A-Z\'-]+,\s*[A-Z\'-]+(?:\s+[A-Z])?)\b', ocr_text, re.IGNORECASE)
        if name_m:
            data.patient_name = name_m.group(1).strip()

        # Age & Sex: AGE: 68 SEX: F or 68 YOF / 74 YOM
        age_m = re.search(r'\bAGE[:\s]+(\d{1,3})\b', ocr_text, re.IGNORECASE)
        if age_m:
            data.age = age_m.group(1)

        sex_m = re.search(r'\bSEX[:\s]+([MF])\b', ocr_text, re.IGNORECASE)
        if sex_m:
            data.sex = sex_m.group(1).upper()
        else:
            # Check for shorthand e.g. "68 YOF" / "74 YOM"
            demo_short = re.search(r'\b(\d{1,3})\s*YO([FM])\b', ocr_text, re.IGNORECASE)
            if demo_short:
                data.age = demo_short.group(1)
                data.sex = demo_short.group(2).upper()

        # 2. CBC Panel
        wbc_m = re.search(r'\bWBC[:\s]*(\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if wbc_m:
            data.cbc["wbc"] = wbc_m.group(1)

        hgb_m = re.search(r'\b(?:HGB|HB)[:\s]*(\d{2,3})\b', ocr_text, re.IGNORECASE)
        if hgb_m:
            data.cbc["hgb"] = hgb_m.group(1)

        plt_m = re.search(r'\bPLT[:\s]*(\d{2,3})\b', ocr_text, re.IGNORECASE)
        if plt_m:
            data.cbc["plt"] = plt_m.group(1)

        # 3. Chemistry / Electrolytes & Renal Panel
        na_m = re.search(r'\bNA[:\s]*(\d{2,3})\b', ocr_text, re.IGNORECASE)
        if na_m:
            data.chem["na"] = na_m.group(1)

        k_m = re.search(r'\bK[:\s]*(\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if k_m:
            data.chem["k"] = k_m.group(1)

        cl_m = re.search(r'\bCL[:\s]*(\d{2,3})\b', ocr_text, re.IGNORECASE)
        if cl_m:
            data.chem["cl"] = cl_m.group(1)

        hco3_m = re.search(r'\b(?:HCO3|CO2)[:\s]*(\d{1,2})\b', ocr_text, re.IGNORECASE)
        if hco3_m:
            data.chem["hco3"] = hco3_m.group(1)

        cr_m = re.search(r'\b(?:CR|CREAT)[:\s]*(\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if cr_m:
            data.chem["cr"] = cr_m.group(1)

        bun_m = re.search(r'\b(?:BUN|UREA)[:\s]*(\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if bun_m:
            data.chem["bun"] = bun_m.group(1)

        egfr_m = re.search(r'\be?GFR[:\s]*([<>]?\s*\d+)\b', ocr_text, re.IGNORECASE)
        if egfr_m:
            data.chem["egfr"] = egfr_m.group(1)

        # 4. Cardiac & Coagulation
        trop_m = re.search(r'\b(?:TROP|TROPONIN|HS-CTN|CTNT)[:\s]*([<>]?\s*\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if trop_m:
            data.cardiac["troponin"] = trop_m.group(1)

        bnp_m = re.search(r'\b(?:BNP|NT-PROBNP)[:\s]*(\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if bnp_m:
            data.cardiac["bnp"] = bnp_m.group(1)

        inr_m = re.search(r'\bINR[:\s]*(\d+(?:\.\d+)?)\b', ocr_text, re.IGNORECASE)
        if inr_m:
            data.coag["inr"] = inr_m.group(1)

        return data
