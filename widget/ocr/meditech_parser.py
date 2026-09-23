"""
Deterministic Meditech / Hospital Terminal Lab Parser
=====================================================
Fast, regex-based, 100% deterministic extractor for standard hospital lab grids
across all EMR pages (Chemistry, Hematology, Coagulation, Blood Gas, Urines, LFTs, Cardiac, Vitals).
Ensures zero AI hallucination by directly parsing screen text and OCR bounding rows.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("widget.ocr.meditech")


@dataclass
class ClinicalLabValue:
    name: str
    value: str
    flag: str = ""  # "H", "L", or ""

    def to_audio_str(self) -> str:
        if self.flag:
            return f"{self.name} {self.value} ({self.flag})"
        return f"{self.name} {self.value}"


@dataclass
class ParsedLabReport:
    panels: Dict[str, List[ClinicalLabValue]] = field(default_factory=dict)
    timestamp: str = ""  # e.g. "1/11/25 08:03"
    raw_ocr: str = ""

    def to_audio_dictation(self) -> str:
        return MeditechLabParser.format_audio_dictation(self.panels, timestamp=self.timestamp)


class MeditechLabParser:
    """
    Scans raw OCR text for standard hospital laboratory panels, dates, units, and flags.
    Outputs clean, audio-dictation-ready formatted lines.
    """

    # Value pattern: captures numbers, decimals (including leading dots like .82),
    # and inequality prefixes (e.g. >60, <0.01) followed by optional High/Low flag (H, (H), L, (L), *, CRIT)
    FLAG_PAT = r'(?:\((?:[HL]|\*|CRIT)\)|\[(?:[HL]|\*|CRIT)\]|\b[HL]\b|\*|\bCRIT\b)'
    VAL_REGEX = r'(?:[:=\s\t]+)([<>~]?\s*(?:\d+(?:\.\d+)?|\.\d+))\s*(' + FLAG_PAT + r')?(?:\s+[A-Za-z/%^0-9\.\-\(\)]*)?'

    # 1. Electrolytes & Renal Panel
    LYTES_DEFS = [
        ("Na", r'(?:\bNA\b|\bSODIUM\b)' + VAL_REGEX),
        ("K", r'(?:\bK\b|\bPOTASSIUM\b)' + VAL_REGEX),
        ("Cl", r'(?:\bCL\b|\bCHLORIDE\b)' + VAL_REGEX),
        ("HCO3", r'(?:\bCO2\b|\bHC[O0]3\b|\bBICARB\b|TOTAL\s*CO2)' + VAL_REGEX),
        ("Anion Gap", r'(?:\bANION\s*GAP\b)' + VAL_REGEX),
        ("BUN", r'(?:\bBUN\b|\bUREA\b)' + VAL_REGEX),
        ("Cr", r'(?:\bCR\b|\bCREAT\b|\bCREATININE\b)' + VAL_REGEX),
        ("eGFR", r'(?:EGFR|E-GFR|\bGFR\b)(?:\s*\([^\)]*\))?' + VAL_REGEX),
        ("CrCl", r'(?:ESTIMATED\s*CREAT\s*CLEAR|\bCRCL\b)' + VAL_REGEX),
        ("Glucose", r'(?:RANDOM\s*GLUCOSE|FASTING\s*GLUCOSE|\bGLU(?:COSE)?\b)' + VAL_REGEX),
        ("Ca", r'(?:\bCA\b|\bCALCIUM\b)' + VAL_REGEX),
        ("PO4", r'(?:\bPO4\b|\bPHOS(?:PHATE|PHORUS)?\b)' + VAL_REGEX),
        ("Mg", r'(?:\bMG\b|\bMAGNESIUM\b)' + VAL_REGEX),
        ("Osm", r'(?:\bOSM\b|\bOSMOLALITY\b)' + VAL_REGEX),
    ]

    # 2. CBC (Hematology / Complete Blood Count)
    CBC_DEFS = [
        ("WBC", r'(?:\bWBC\b|WHITE\s*BLOOD\s*CELLS?)' + VAL_REGEX),
        ("Hgb", r'(?:\bHGB\b|\bHB\b|HEMOGLOBIN)' + VAL_REGEX),
        ("Hct", r'(?:\bHCT\b|HEMATOCRIT)' + VAL_REGEX),
        ("Plt", r'(?:\bPLT(?:\s*COUNT)?\b|\bPLATELETS?(?:\s*COUNT)?\b)' + VAL_REGEX),
        ("MCV", r'(?:\bMCV\b)' + VAL_REGEX),
        ("Neut", r'(?:\bNEUT(?:ROPHILS?)?|\bANC\b)(?:[#\s\(\)Auto（）]*)' + VAL_REGEX),
        ("Lymph", r'(?:\bLYMPH(?:OCYTES?)?)(?:[#\s\(\)Auto（）]*)' + VAL_REGEX),
        ("Mono", r'(?:\bMONO(?:CYTES?)?)(?:[#\s\(\)Auto（）]*)' + VAL_REGEX),
        ("Eos", r'(?:\bEOS(?:INOPHILS?)?)(?:[#\s\(\)Auto（）]*)' + VAL_REGEX),
        ("Baso", r'(?:\bBASO(?:PHILS?)?)(?:[#\s\(\)Auto（）]*)' + VAL_REGEX),
        ("Immature Gran", r'(?:IMMATURE\s*GRAN|\bIG\b|\bBANDS?\b)(?:[#\s\(\)Auto（）]*)' + VAL_REGEX),
        ("MCH", r'(?:\bMCH\b)' + VAL_REGEX),
        ("MCHC", r'(?:\bMCHC\b)' + VAL_REGEX),
        ("RDW", r'(?:\bRDW\b)' + VAL_REGEX),
        ("MPV", r'(?:\bMPV\b)' + VAL_REGEX),
        ("NRBC", r'(?:ABSOLUTE\s*NUCLEATED\s*RBC|\bNRBC\b)' + VAL_REGEX),
    ]

    # 3. Coagulation
    COAG_DEFS = [
        ("INR", r'(?:\bINR\b)' + VAL_REGEX),
        ("PTT", r'(?:\bPTT\b|\bAPTT\b)' + VAL_REGEX),
        ("PT", r'(?:\bPT\b|PROTHROMBIN\s*TIME)' + VAL_REGEX),
        ("Fibrinogen", r'(?:\bFIBRINOGEN\b|\bFIB\b)' + VAL_REGEX),
        ("D-Dimer", r'(?:D-?DIMER)' + VAL_REGEX),
    ]

    # 4. Liver & Pancreas (LFTs)
    LFT_DEFS = [
        ("Total Bili", r'(?:TOTAL\s*BILI(?:RUBIN)?|\bBILI(?:RUBIN)?\b)' + VAL_REGEX),
        ("Direct Bili", r'(?:DIRECT\s*BILI(?:RUBIN)?)' + VAL_REGEX),
        ("ALT", r'(?:\bALT\b|\bSGPT\b)' + VAL_REGEX),
        ("AST", r'(?:\bAST\b|\bSGOT\b)' + VAL_REGEX),
        ("ALP", r'(?:\bALP\b|ALK(?:ALINE)?\s*PHOS(?:PHATASE)?)' + VAL_REGEX),
        ("Total Protein", r'(?:TOTAL\s*PROTEIN|\bTOTALPROTEIN\b)' + VAL_REGEX),
        ("Albumin", r'(?:\bALB(?:UMIN)?\b)' + VAL_REGEX),
        ("Lipase", r'(?:\bLIPASE\b)' + VAL_REGEX),
        ("Amylase", r'(?:\bAMYLASE\b)' + VAL_REGEX),
    ]

    # 5. Cardiac Biomarkers
    CARDIAC_DEFS = [
        ("hs-Troponin", r'(?:\bTROP(?:ONIN)?\b|HS-?TROP|TN[TI]?)' + VAL_REGEX),
        ("BNP", r'(?:\bBNP\b|NT-?PRO-?BNP)' + VAL_REGEX),
        ("CK", r'(?:\bCK\b|CREATINE\s*KINASE|\bCPK\b)' + VAL_REGEX),
        ("CK-MB", r'(?:CK-?MB)' + VAL_REGEX),
    ]

    # 6. Blood Gas (ABG / VBG)
    BLOOD_GAS_DEFS = [
        ("pH", r'(?:\bPH\b)' + VAL_REGEX),
        ("pCO2", r'(?:\bPCO2\b)' + VAL_REGEX),
        ("pO2", r'(?:\bPO2\b)' + VAL_REGEX),
        ("HCO3", r'(?:\bCO2\b|\bHC[O0]3\b)' + VAL_REGEX),
        ("Base Excess", r'(?:BASE\s*EXCESS|\bBE\b)' + VAL_REGEX),
        ("Lactate", r'(?:\bLACTATE\b|LACTIC\s*ACID)' + VAL_REGEX),
        ("sO2", r'(?:\bSO2\b|O2\s*SAT)' + VAL_REGEX),
    ]

    # 7. Inflammatory & Endocrine
    INFLAMMATORY_DEFS = [
        ("CRP", r'(?:\bCRP\b|HS-?CRP)' + VAL_REGEX),
        ("ESR", r'(?:\bESR\b|SED\s*RATE)' + VAL_REGEX),
        ("Ferritin", r'(?:\bFERRITIN\b)' + VAL_REGEX),
        ("TSH", r'(?:\bTSH\b)' + VAL_REGEX),
        ("Free T4", r'(?:FREE\s*T4|\bFT4\b)' + VAL_REGEX),
        ("HbA1c", r'(?:\bHBA1C\b|\bA1C\b)' + VAL_REGEX),
    ]

    # 8. Urinalysis (Strictly dedicated urinalysis markers)
    URINE_DEFS = [
        ("SpGr", r'(?:SPGR|SPECIFIC\s*GRAVITY)' + VAL_REGEX),
        ("Urine pH", r'(?:URINE\s*PH)' + VAL_REGEX),
        ("Urine Protein", r'(?:URINE\s*PROTEIN)' + VAL_REGEX),
        ("Urine Glucose", r'(?:URINE\s*GLUCOSE)' + VAL_REGEX),
        ("Ketones", r'(?:\bKETONES\b)' + VAL_REGEX),
        ("Urine Blood", r'(?:URINE\s*BLOOD|OCCULT\s*BLOOD)' + VAL_REGEX),
        ("Leuk Est", r'(?:LEUK(?:OCYTE)?\s*EST(?:ERASE)?)' + VAL_REGEX),
        ("Nitrite", r'(?:\bNITRITE\b)' + VAL_REGEX),
        ("Urine WBC", r'(?:URINE\s*WBC)' + VAL_REGEX),
        ("Urine RBC", r'(?:URINE\s*RBC)' + VAL_REGEX),
        ("Bacteria", r'(?:\bBACTERIA\b)' + VAL_REGEX),
    ]

    # 9. Vital Signs
    VITALS_DEFS = [
        ("BP", r'\b(?:BP|BLOOD\s*PRESSURE)\b[:\s=]*(\d{2,3}/\d{2,3})'),
        ("HR", r'\b(?:HR|HEART\s*RATE|PULSE)\b[:\s=]*(\d{2,3})\b'),
        ("SpO2", r'\b(?:SPO2|O2\s*SAT|SAT)\b[:\s=]*(\d{2,3})%?'),
        ("RR", r'\b(?:RR|RESP|RESP\s*RATE)\b[:\s=]*(\d{1,2})\b'),
        ("Temp", r'\b(?:TEMP|TEMPERATURE)\b[:\s=]*(\d{2}(?:\.\d+)?)\b'),
    ]

    @classmethod
    def extract_timestamp(cls, text: str) -> str:
        """
        Extracts collection date and time from hospital headers (e.g. '1/11/25 08:03').
        Strictly validates 24-hour time (00-23:00-59) adjacent to the date.
        Rejects invalid timestamps such as ratios (e.g. '60:80').
        """
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            dm = re.search(r'\b([01]?\d/[0-3]?\d/(?:20)?\d{2})\b', line)
            if dm:
                date_str = dm.group(1)
                # Check same line for valid 24h time
                tm = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', line)
                if tm:
                    return f"{date_str} {int(tm.group(1)):02d}:{tm.group(2)}"
                # Check immediately following line
                if i + 1 < len(lines):
                    tm_next = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', lines[i + 1])
                    if tm_next:
                        return f"{date_str} {int(tm_next.group(1)):02d}:{tm_next.group(2)}"
                return date_str
        return ""

    @classmethod
    def clean_ocr_artifacts(cls, text: str) -> str:
        """
        Cleans common terminal OCR artifacts:
        - Heals fragmented decimals (e.g. '6 . 3' -> '6.3', '0 . 82' -> '0.82')
        - Normalizes leading decimal points (e.g. ' .82' -> ' 0.82')
        - Converts commas in numbers to dots ('0,82' -> '0.82')
        - Strips terminal comment bubble glyphs ('Q', 'D')
        - Replaces full-width unicode parentheses
        """
        # Replace full-width parentheses
        text = text.replace("（", "(").replace("）", ")")

        # Heal broken decimals like '6 . 3' -> '6.3' or '0 , 82' -> '0.82'
        text = re.sub(r'(\d+)\s*[\.,]\s*(\d+)', r'\1.\2', text)

        # Heal leading decimals like ' .82' -> ' 0.82'
        text = re.sub(r'(?<=\s)[\.,]\s*(\d+)', r'0.\1', text)

        # Strip standalone trailing 'Q' or 'D' icon artifact after numbers at end of words/lines
        text = re.sub(r'(\d+(?:\.\d+)?)\s+[QD]\b', r'\1', text)
        return text

    @classmethod
    def parse_report(cls, raw_text: str) -> ParsedLabReport:
        """
        Parses raw OCR text into a full structured report including panels and timestamp.
        """
        clean_text = cls.clean_ocr_artifacts(raw_text)
        timestamp = cls.extract_timestamp(clean_text)
        panels = cls.parse_text(clean_text)
        return ParsedLabReport(panels=panels, timestamp=timestamp, raw_ocr=raw_text)

    @classmethod
    def parse_text(cls, raw_text: str) -> Dict[str, List[ClinicalLabValue]]:
        """
        Parses raw text into categorized lab panels.
        Returns dict: {'Lytes': [...], 'CBC': [...], ...}
        """
        results: Dict[str, List[ClinicalLabValue]] = {}
        clean_text = cls.clean_ocr_artifacts(raw_text)

        # 1. Parse Lytes & Renal
        lytes = cls._match_panel(clean_text, cls.LYTES_DEFS)
        if lytes:
            results["Lytes"] = lytes

        # 2. Parse CBC
        cbc = cls._match_panel(clean_text, cls.CBC_DEFS)
        if cbc:
            results["CBC"] = cbc

        # 3. Parse Coags
        coags = cls._match_panel(clean_text, cls.COAG_DEFS)
        if coags:
            results["Coags"] = coags

        # 4. Parse LFTs & Pancreas
        lfts = cls._match_panel(clean_text, cls.LFT_DEFS)
        if lfts:
            results["LFTs"] = lfts

        # 5. Parse Cardiac
        cardiac = cls._match_panel(clean_text, cls.CARDIAC_DEFS)
        if cardiac:
            results["Cardiac"] = cardiac

        # 6. Parse Blood Gas (Only if arterial/venous gas markers present)
        abg = cls._match_panel(clean_text, cls.BLOOD_GAS_DEFS)
        if abg and any(item.name in ("pH", "pCO2", "pO2", "Lactate", "Base Excess") for item in abg):
            results["Blood Gas"] = abg

        # 7. Parse Inflammatory / Endocrine
        inf = cls._match_panel(clean_text, cls.INFLAMMATORY_DEFS)
        if inf:
            results["Endocrine & Inflammatory"] = inf

        # 8. Parse Urines (Strictly require urinalysis context)
        urines = cls._match_panel(clean_text, cls.URINE_DEFS)
        if urines and (any(item.name in ("Leuk Est", "Nitrite", "SpGr", "Urine WBC", "Urine RBC", "Bacteria") for item in urines) or "URINE" in clean_text.upper()):
            results["Urinalysis"] = urines

        # 9. Parse Vitals
        vitals: List[ClinicalLabValue] = []
        for label, pattern in cls.VITALS_DEFS:
            m = re.search(pattern, clean_text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                vitals.append(ClinicalLabValue(name=label, value=val))
        if vitals:
            results["Vitals"] = vitals

        return results

    @classmethod
    def _match_panel(cls, text: str, definitions: List[Tuple[str, str]]) -> List[ClinicalLabValue]:
        values: List[ClinicalLabValue] = []
        for name, pattern in definitions:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                raw_val = m.group(1).strip().replace(" ", "").replace(",", ".")
                if raw_val.startswith("."):
                    raw_val = "0" + raw_val
                flag = m.group(2).strip().strip("()[]* ") if m.lastindex >= 2 and m.group(2) else ""
                # Normalize flag
                if flag in ("*", "CRIT"):
                    flag = "CRIT"
                values.append(ClinicalLabValue(name=name, value=raw_val, flag=flag))
        return values

    @classmethod
    def merge_reports(cls, reports: List[ParsedLabReport]) -> ParsedLabReport:
        """
        Merges multiple lab reports (e.g. from multi-page browsing) into a single unified report.
        """
        merged_panels: Dict[str, List[ClinicalLabValue]] = {}
        latest_timestamp = ""

        # Desired clinical ordering of panels
        canonical_order = [
            "Lytes", "LFTs", "CBC", "Coags", "Cardiac", "Blood Gas",
            "Endocrine & Inflammatory", "Urinalysis", "Vitals"
        ]

        for rep in reports:
            if rep.timestamp and not latest_timestamp:
                latest_timestamp = rep.timestamp
            for panel_name, items in rep.panels.items():
                if panel_name not in merged_panels:
                    merged_panels[panel_name] = []
                # Avoid duplicate test names within the same panel
                existing_names = {v.name for v in merged_panels[panel_name]}
                for item in items:
                    if item.name not in existing_names:
                        merged_panels[panel_name].append(item)
                        existing_names.add(item.name)

        # Sort panels canonically
        sorted_panels: Dict[str, List[ClinicalLabValue]] = {}
        for p in canonical_order:
            if p in merged_panels:
                sorted_panels[p] = merged_panels[p]
        for p in merged_panels:
            if p not in sorted_panels:
                sorted_panels[p] = merged_panels[p]

        return ParsedLabReport(panels=sorted_panels, timestamp=latest_timestamp)

    @classmethod
    def format_audio_dictation(
        cls,
        parsed_panels: Dict[str, List[ClinicalLabValue]],
        timestamp: str = ""
    ) -> str:
        """
        Formats parsed panels into clean, audio-friendly clinical lines.
        Combines chemistry labs (Lytes + LFTs) together under 'Labs:'
        without inaccurate 'Lytes:' or 'LFTs:' headers.
        """
        if not parsed_panels:
            return ""

        # Group chemistry labs (Lytes + LFTs) together under "Labs"
        chemistry_items: List[ClinicalLabValue] = []
        seen_chem_names = set()
        for p in ("Lytes", "LFTs"):
            if p in parsed_panels:
                for item in parsed_panels[p]:
                    if item.name not in seen_chem_names:
                        chemistry_items.append(item)
                        seen_chem_names.add(item.name)

        output_groups: List[Tuple[str, List[ClinicalLabValue]]] = []
        if chemistry_items:
            output_groups.append(("Labs", chemistry_items))

        # Canonical ordering for remaining panels
        canonical_panels = [
            ("CBC", "CBC"),
            ("Coags", "Coags"),
            ("Cardiac", "Cardiac"),
            ("Blood Gas", "Blood Gas"),
            ("Endocrine & Inflammatory", "Endocrine"),
            ("Urinalysis", "Urinalysis"),
            ("Vitals", "Vitals"),
        ]

        for internal_key, display_name in canonical_panels:
            if internal_key in parsed_panels and parsed_panels[internal_key]:
                output_groups.append((display_name, parsed_panels[internal_key]))

        # Any extra unhandled panels
        handled_keys = {"Lytes", "LFTs"} | {k for k, _ in canonical_panels}
        for k, v in parsed_panels.items():
            if k not in handled_keys and v:
                output_groups.append((k, v))

        if not output_groups:
            return ""

        lines: List[str] = []
        for display_name, items in output_groups:
            formatted_items = [item.to_audio_str() for item in items]
            items_str = ", ".join(formatted_items)
            if timestamp:
                lines.append(f"{display_name} ({timestamp}): {items_str}")
            else:
                lines.append(f"{display_name}: {items_str}")

        return "\n".join(lines)
