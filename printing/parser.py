"""
Clinical Note Parser
====================
Parses raw clinical text / markdown into structured ClinicalNote objects,
extracting patient demographics, sections, vitals, allergies, problem lists,
and provider signatures.
"""

import re
from typing import Dict, List, Tuple, Optional
from printing.models import ClinicalNote, PatientMetadata, ClinicalSection, ClinicalProblem


class ClinicalNoteParser:
    """Intelligently converts clinical Markdown/dictation text into a structured ClinicalNote."""

    SECTION_HEADERS = [
        "IDENTIFYING DATA",
        "DEMOGRAPHICS",
        "HISTORY OF PRESENT ILLNESS",
        "HPI",
        "PAST MEDICAL HISTORY",
        "PMHX",
        "PAST SURGICAL HISTORY",
        "PSHX",
        "MEDICATIONS",
        "MEDICATION LIST",
        "ALLERGIES",
        "ALLERGIES / ADVERSE REACTIONS",
        "SOCIAL HISTORY",
        "FAMILY HISTORY",
        "REVIEW OF SYSTEMS",
        "ROS",
        "PHYSICAL EXAMINATION",
        "PHYSICAL EXAM",
        "EXAM",
        "VITAL SIGNS",
        "VITALS",
        "PERTINENT INVESTIGATIONS",
        "LABORATORY INVESTIGATIONS",
        "LABS",
        "DIAGNOSTIC STUDIES",
        "IMAGING",
        "ASSESSMENT & CLINICAL IMPRESSION",
        "ASSESSMENT",
        "CLINICAL IMPRESSION",
        "DETAILED PLAN & RECOMMENDATIONS",
        "PLAN & RECOMMENDATIONS",
        "PLAN",
        "ASSESSMENT & PLAN",
        "A/P",
        "DISCUSSED WITH TEAM",
        "TEAM DISCUSSION",
        "RECOMMENDATIONS",
        "DISPOSITION",
        "SUBJECTIVE",
        "OBJECTIVE"
    ]

    @classmethod
    def parse(cls, text: str, default_metadata: Optional[PatientMetadata] = None) -> ClinicalNote:
        note = ClinicalNote(raw_text=text)
        note.metadata = default_metadata or PatientMetadata()

        lines = [line.rstrip() for line in text.splitlines()]
        if not lines:
            return note

        # 1. Parse Dictation Preamble (e.g. "THIS IS DAVID KANTER EIVIN DICTATING ON BEHALF OF...")
        content_start_idx = cls._extract_preamble_and_title(lines, note)

        # 2. Parse Top Metadata Block (DATE, REQUESTING SERVICE, REASON, PATIENT, MRN)
        content_start_idx = cls._extract_header_metadata(lines, content_start_idx, note)

        # 3. Parse Sections
        cls._extract_sections_and_problems(lines, content_start_idx, note)

        # 4. Extract Vitals & Allergies
        cls._extract_vitals(note)
        cls._extract_allergies(note)

        # 5. Extract Assessment & Plan Problems
        cls._structure_problems(note)

        # 6. Extract Signature & Attestation
        cls._extract_signature(note)

        return note

    @classmethod
    def _extract_preamble_and_title(cls, lines: List[str], note: ClinicalNote) -> int:
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1

        if idx >= len(lines):
            return idx

        first_line = lines[idx].strip()
        # Check preamble
        if "DICTATING ON BEHALF OF" in first_line.upper() or "THIS IS" in first_line.upper():
            note.preamble = first_line
            # Try to extract dictating & attending
            m = re.search(r"THIS IS\s+([A-Z\s]+?)\s+(?:PGY\d|\bDICTATING\b)", first_line, re.IGNORECASE)
            if m:
                clean_name = " ".join(w.capitalize() for w in m.group(1).split())
                pgy_m = re.search(r"\b(PGY\s*\d)\b", first_line, re.IGNORECASE)
                pgy_str = f", {pgy_m.group(1).upper()}" if pgy_m else ""
                note.metadata.dictating_physician = f"{clean_name}{pgy_str}"

            m_att = re.search(r"ON BEHALF OF\s+(?:DR\.?\s*)?([A-Za-z\s]+?)(?:,|\.|\bMCTU\b|\bSTAFF\b|$)", first_line, re.IGNORECASE)
            if m_att:
                clean_att = " ".join(w.capitalize() for w in m_att.group(1).split())
                note.metadata.attending_physician = f"Dr. {clean_att}"

            idx += 1
            while idx < len(lines) and not lines[idx].strip():
                idx += 1

        # Check for Title (e.g. **INTERNAL MEDICINE CONSULTATION NOTE** or # Progress Note)
        if idx < len(lines):
            line = lines[idx].strip()
            clean_title = re.sub(r"^#+\s*|\*+", "", line).strip()
            if any(term in clean_title.upper() for term in ["CONSULT", "PROGRESS NOTE", "NOTE", "DISCHARGE", "SUMMARY", "CLINIC"]):
                note.title = clean_title.upper()
                if "PROGRESS" in clean_title.upper():
                    note.note_type = "progress"
                else:
                    note.note_type = "consult"
                idx += 1

        return idx

    @classmethod
    def _extract_header_metadata(cls, lines: List[str], start_idx: int, note: ClinicalNote) -> int:
        idx = start_idx
        while idx < len(lines):
            line = lines[idx].strip()
            if not line:
                idx += 1
                continue

            # Check if this line is a section divider or heading
            if line.startswith("---") or line.startswith("===") or line.startswith("### ") or line.startswith("## "):
                # End of header metadata
                if line.startswith("---") or line.startswith("==="):
                    idx += 1
                break

            # Key: Value pattern
            m = re.match(r"^\*?\*?([A-Z\s/]+)\*?\*?:\s*(.+)$", line)
            if m:
                key = m.group(1).strip().upper()
                val = re.sub(r"^\*+|\*+$", "", m.group(2)).strip()

                if "DATE" in key:
                    note.metadata.date = val
                elif "REQUESTING SERVICE" in key or "SERVICE" in key and "REQUEST" in key:
                    note.metadata.requesting_service = val
                elif "REQUESTING PHYSICIAN" in key or "REQUESTING MD" in key or "REFERRING" in key:
                    note.metadata.requesting_physician = val
                elif "REASON" in key:
                    note.metadata.reason_for_consult = val
                elif "PATIENT" in key or "NAME" in key:
                    note.metadata.patient_name = val
                elif "MRN" in key:
                    note.metadata.mrn = val
                elif "DOB" in key:
                    note.metadata.dob = val
                elif "ROOM" in key or "BED" in key or "UNIT" in key:
                    note.metadata.room_bed = val
                elif "MRP" in key or "ATTENDING" in key:
                    note.metadata.attending_physician = val
                elif "CODE STATUS" in key:
                    note.metadata.code_status = val
                idx += 1
            else:
                # Non-key-value line, check if it's the start of body
                break

        return idx

    @classmethod
    def _extract_sections_and_problems(cls, lines: List[str], start_idx: int, note: ClinicalNote):
        current_section: Optional[ClinicalSection] = None
        current_lines: List[str] = []

        def flush_section():
            nonlocal current_section, current_lines
            if current_section and current_lines:
                current_section.raw_content = "\n".join(current_lines).strip()
                # Parse bullets vs paragraphs
                for l in current_lines:
                    s_line = l.strip()
                    if s_line.startswith("* ") or s_line.startswith("- ") or s_line.startswith("• "):
                        current_section.bullets.append(s_line[2:].strip())
                    elif s_line:
                        current_section.paragraphs.append(s_line)
                note.sections.append(current_section)
                current_section = None
                current_lines = []

        idx = start_idx
        while idx < len(lines):
            line = lines[idx]
            clean = line.strip()

            if clean.startswith("---") or clean.startswith("==="):
                idx += 1
                continue

            # Check if line matches a major section header
            header_match = cls._match_section_header(clean)
            if header_match:
                flush_section()
                current_section = ClinicalSection(title=header_match)
                idx += 1
                continue

            # Accumulate lines into current section
            if current_section:
                current_lines.append(line)
            else:
                # If no section has started yet, create a default "Clinical Summary" section
                if clean:
                    current_section = ClinicalSection(title="CLINICAL OVERVIEW")
                    current_lines.append(line)

            idx += 1

        flush_section()

    @classmethod
    def _match_section_header(cls, line: str) -> Optional[str]:
        # Handle markdown headers (e.g. ### HISTORY OF PRESENT ILLNESS (HPI))
        m = re.match(r"^#{1,4}\s*(.+)$", line)
        if m:
            text = m.group(1).strip()
            # Clean formatting asterisks
            text = re.sub(r"^\*+|\*+$", "", text).strip()
            return text

        # Handle bold headers (e.g. **PHYSICAL EXAMINATION**)
        m2 = re.match(r"^\*{2}([A-Z0-9\s\(\)/&,-]+)\*{2}:?$", line)
        if m2:
            candidate = m2.group(1).strip()
            for h in cls.SECTION_HEADERS:
                if h in candidate.upper():
                    return candidate

        return None

    @classmethod
    def _extract_vitals(cls, note: ClinicalNote):
        """Extracts vital signs from text and stores in note.vitals dictionary."""
        full_text = note.raw_text

        # Standard patterns
        patterns = {
            "BP": r"(?:BP|Blood Pressure):\s*([0-9]{2,3}/[0-9]{2,3}(?:\s*mmHg)?)",
            "HR": r"(?:HR|Heart Rate|Pulse):\s*([0-9]{2,3}(?:\s*bpm)?)",
            "Temp": r"(?:Temp|Temperature|T):\s*([0-9]{2,3}(?:\.[0-9])?\s*(?:°?C|°?F)?)",
            "RR": r"(?:RR|Respiratory Rate):\s*([0-9]{1,2}(?:\s*(?:/min|bpm))?)",
            "SpO2": r"(?:SpO2|SaO2|O2 Sat(?:uration)?):\s*([0-9]{2,3}%\s*(?:\([^)]+\)|on\s+[A-Za-z0-9\s/]+)?)",
            "Weight": r"(?:Weight|Wt):\s*([0-9]{2,3}(?:\.[0-9])?\s*(?:kg|lbs)?)",
            "24h I/O": r"(?:24h\s*I/O|I/O|Net):\s*([+0-9/,\-\s]+(?:mL|cc)?)"
        }

        for key, pat in patterns.items():
            m = re.search(pat, full_text, re.IGNORECASE)
            if m:
                note.vitals[key] = m.group(1).strip()

    @classmethod
    def _extract_allergies(cls, note: ClinicalNote):
        """Extracts allergies list and cleans formatting."""
        for sec in note.sections:
            if "ALLERG" in sec.title.upper():
                note.allergies_list = list(sec.bullets)
                if not note.allergies_list and sec.paragraphs:
                    note.allergies_list = [p for p in sec.paragraphs if p.strip()]
                break

    @classmethod
    def _structure_problems(cls, note: ClinicalNote):
        """Finds problem-based items in Assessment and Plan sections."""
        ap_sections = [
            s for s in note.sections
            if any(k in s.title.upper() for k in ["ASSESSMENT", "PLAN", "IMPRESSION", "RECOMMENDATION"])
        ]

        prob_num = 1
        for sec in ap_sections:
            # Check for numbered items (e.g. 1. **Multifocal Pneumonia:** ...)
            prob_regex = re.compile(r"(?:^|\n)(?:####\s*)?(?:(\d+)\.|\*?\*?Problem\s*#?(\d+):?)\s*\**([^\n\*:]+)\**:?\s*(.*?)(?=\n(?:####\s*)?(?:\d+\.|\*?\*?Problem\s*#?\d+:?)|$)", re.DOTALL)
            matches = prob_regex.findall(sec.raw_content)

            for m in matches:
                p_num = int(m[0] or m[1] or prob_num)
                p_title = m[2].strip()
                p_body = m[3].strip()

                bullets = []
                for line in p_body.splitlines():
                    s = line.strip()
                    if s.startswith("* ") or s.startswith("- ") or s.startswith("• "):
                        bullets.append(s[2:].strip())

                prob = ClinicalProblem(
                    number=p_num,
                    title=p_title,
                    bullets=bullets,
                    raw_content=p_body
                )
                note.problems.append(prob)
                prob_num += 1

    @classmethod
    def _extract_signature(cls, note: ClinicalNote):
        """Extracts provider signature and attestation text from the end of the note."""
        for sec in reversed(note.sections):
            if any(k in sec.title.upper() for k in ["DISCUSSED", "TEAM", "ATTESTATION", "SIGNATURE"]):
                note.attestation_statement = sec.raw_content
                break

        # Check for trailing signature lines (e.g. Alexander Reed, MD, FACP)
        lines = [l.strip() for l in note.raw_text.splitlines() if l.strip()]
        for i in range(len(lines) - 1, max(-1, len(lines) - 8), -1):
            line = lines[i]
            if re.search(r"\b(?:MD|DO|MBBS|FRCPC|FACP|CCFP|PGY\d)\b", line):
                note.signature_name = line.replace("*", "").strip()
            elif "Pager:" in line or "pager" in line.lower():
                note.signature_pager = line.replace("*", "").strip()
            elif "Department of" in line:
                note.signature_title = line.replace("*", "").strip()
