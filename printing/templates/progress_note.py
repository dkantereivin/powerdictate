"""
Progress Note Print Template
============================
High-density, problem-oriented inpatient ward progress note template.
Features a compact telemetry/vitals dashboard, SOAP layout, active problem cards,
prophylaxis checklist, and space-optimized typography for daily rounding.
Designed for 100% visual fidelity in Qt QTextDocument PDF rendering and Microsoft Word docx.
"""

import html
import re
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from printing.models import ClinicalNote
from printing.templates.base import BasePrintTemplate
from printing.templates.tbrhsc_consult import re_fmt, html_format_markdown_inline


class ProgressNoteTemplate(BasePrintTemplate):
    """Compact Inpatient / MCTU Ward Progress Note template."""

    template_id = "progress_note"
    name = "Progress Note"
    description = "High-density, problem-oriented SOAP ward progress note with vitals dashboard and active issue cards."

    def render_html(self, note: ClinicalNote) -> str:
        meta = note.metadata

        pt_name = meta.patient_name or "PATIENT RECORD"
        mrn_val = meta.mrn or "—"
        room_val = meta.room_bed or "MCTU Ward"
        hd_val = meta.hospital_day or meta.postop_day or "HD# 1"
        date_val = meta.date
        mrp_md = meta.attending_physician or "Dr. Vandermeer"
        dict_md = meta.dictating_physician or "David Kanter Eivin, PGY1"

        # Allergies text
        if note.allergies_list or meta.allergies:
            all_str = " • ".join(re_fmt(a) for a in note.allergies_list) if note.allergies_list else meta.allergies
            all_badge = f"<font color='#dc2626'><b>⚠️ Allergies:</b> {html.escape(all_str)}</font>"
        else:
            all_badge = "<font color='#059669'><b>✓ NKDA</b></font>"

        # Header Table Strip
        header_table = f"""
        <table width="100%" bgcolor="#0f766e" cellpadding="6" cellspacing="0">
            <tr>
                <td valign="middle">
                    <font color="#ffffff" size="3"><b>INPATIENT PROGRESS NOTE</b></font> &nbsp;
                    <font color="#ccfbf1" size="2"><b>MCTU WARD ROUNDS</b></font>
                </td>
                <td align="right" valign="middle">
                    <font color="#ffffff" size="2"><b>{html.escape(meta.hospital_name)}</b></font>
                </td>
            </tr>
        </table>
        <table width="100%" bgcolor="#f8fafc" border="1" bordercolor="#cbd5e1" cellpadding="3" cellspacing="0" style="margin-bottom: 6px;">
            <tr>
                <td width="25%"><b>Patient:</b> {html.escape(pt_name)}</td>
                <td width="16%"><b>MRN:</b> {html.escape(mrn_val)}</td>
                <td width="16%"><b>Room:</b> {html.escape(room_val)}</td>
                <td width="13%"><b>Day:</b> {html.escape(hd_val)}</td>
                <td width="30%"><b>Date:</b> {html.escape(date_val)}</td>
            </tr>
            <tr>
                <td colspan="2"><b>MRP:</b> {html.escape(mrp_md)}</td>
                <td colspan="2"><b>Author:</b> {html.escape(dict_md)}</td>
                <td>{all_badge}</td>
            </tr>
        </table>
        """

        # Vitals Dashboard Table
        vitals_row = ""
        if note.vitals:
            v_cells = [f"<b>{k}:</b> {html.escape(v)}" for k, v in note.vitals.items()]
            vitals_row = f"""
            <table width="100%" bgcolor="#f0fdfa" border="1" bordercolor="#99f6e4" cellpadding="3" cellspacing="0" style="margin-bottom: 6px;">
                <tr>
                    <td><font color="#0f766e"><b>TELEMETRY / VITALS:</b></font> &nbsp;|&nbsp; {" &nbsp;|&nbsp; ".join(v_cells)}</td>
                </tr>
            </table>
            """

        # Format Sections as Compact Problem Cards
        sections_html = []
        for sec in note.sections:
            title_upper = sec.title.upper()
            if any(skip in title_upper for skip in ["IDENTIFYING DATA", "ALLERG"]):
                continue

            is_plan_sec = any(k in title_upper for k in ["PLAN", "ASSESSMENT", "A/P", "RECOMMENDATION", "PROBLEM"])

            header_bg = "#ccfbf1" if is_plan_sec else "#e2e8f0"
            header_color = "#064e3b" if is_plan_sec else "#0f172a"
            border_color = "#0f766e" if is_plan_sec else "#94a3b8"

            sec_body = []
            for p in sec.paragraphs:
                clean_p = html_format_markdown_inline(p)
                sec_body.append(f"<p style='margin: 0 0 3px 0;'>{clean_p}</p>")

            if sec.bullets:
                sec_body.append("<ul style='margin: 1px 0 3px 0; padding-left: 18px;'>")
                for b in sec.bullets:
                    clean_b = html_format_markdown_inline(b)
                    sec_body.append(f"<li style='margin-bottom: 1.5px;'>{clean_b}</li>")
                sec_body.append("</ul>")

            body_content = "".join(sec_body) if sec_body else f"<p style='margin: 0 0 3px 0;'>{html.escape(sec.raw_content)}</p>"

            sections_html.append(f"""
            <table width="100%" border="1" bordercolor="{border_color}" cellpadding="4" cellspacing="0" style="margin-bottom: 5px;">
                <tr>
                    <td bgcolor="{header_bg}">
                        <font color="{header_color}" size="2"><b>{html.escape(sec.title.upper())}</b></font>
                    </td>
                </tr>
                <tr>
                    <td bgcolor="#ffffff">
                        {body_content}
                    </td>
                </tr>
            </table>
            """)

        body_html = "\n".join(sections_html)

        # Compact Signoff Strip
        signoff_table = f"""
        <table width="100%" border="0" cellpadding="2" cellspacing="0" style="border-top: 1px solid #cbd5e1; margin-top: 8px; font-size: 7.5pt; color: #475569;">
            <tr>
                <td><b>Dictated by:</b> {html.escape(dict_md)} &nbsp;|&nbsp; <b>MRP:</b> {html.escape(mrp_md)}</td>
                <td align="right">Recorded: {html.escape(date_val)} {html.escape(meta.time)} • Confidential Medical Record</td>
            </tr>
        </table>
        """

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Progress Note - {html.escape(pt_name)}</title>
</head>
<body style="font-family: Arial, Helvetica, sans-serif; font-size: 8.8pt; line-height: 1.32; color: #0f172a;">

    <!-- Header Block -->
    {header_table}

    <!-- Vitals Dashboard -->
    {vitals_row}

    <!-- Content Sections / Problem Cards -->
    {body_html}

    <!-- Signoff Strip -->
    {signoff_table}

</body>
</html>
"""

    def render_docx(self, note: ClinicalNote) -> docx.Document:
        """Renders styled high-density progress note in Word .docx format."""
        doc = docx.Document()
        meta = note.metadata

        for section in doc.sections:
            section.top_margin = Inches(0.45)
            section.bottom_margin = Inches(0.45)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)

        p_title = doc.add_paragraph()
        run_title = p_title.add_run("INPATIENT PROGRESS NOTE — MCTU WARD")
        run_title.font.name = "Arial"
        run_title.font.size = Pt(11)
        run_title.font.bold = True
        run_title.font.color.rgb = RGBColor(255, 255, 255)
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        shading = parse_xml(r'<w:shd {} w:fill="0F766E"/>'.format(nsdecls('w')))
        p_title._p.get_or_add_pPr().append(shading)
        p_title.paragraph_format.space_before = Pt(0)
        p_title.paragraph_format.space_after = Pt(4)

        table = doc.add_table(rows=2, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

        pt_data = [
            (f"Patient: {meta.patient_name or 'PATIENT'}", f"MRN: {meta.mrn or '—'}", f"Room: {meta.room_bed or 'Ward'}", f"Date: {meta.date}"),
            (f"MRP: {meta.attending_physician or 'Dr. Vandermeer'}", f"Dictated by: {meta.dictating_physician or 'David Kanter Eivin'}", f"Day: {meta.hospital_day or 'HD# 1'}", "NKDA" if not note.allergies_list else "⚠️ Allergies Noted")
        ]

        for r_idx, row_vals in enumerate(pt_data):
            for c_idx in range(4):
                cell = table.rows[r_idx].cells[c_idx]
                cell.text = row_vals[c_idx]
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(1.5)
                    p.paragraph_format.space_after = Pt(1.5)
                    for r in p.runs:
                        r.font.name = "Arial"
                        r.font.size = Pt(8)
                c_shd = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
                cell._tc.get_or_add_tcPr().append(c_shd)

        for sec in note.sections:
            if any(skip in sec.title.upper() for skip in ["IDENTIFYING DATA", "ALLERG"]):
                continue

            h = doc.add_heading(sec.title.upper(), level=3)
            h.paragraph_format.space_before = Pt(6)
            h.paragraph_format.space_after = Pt(2)
            for r in h.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9)
                r.font.bold = True
                r.font.color.rgb = RGBColor(15, 118, 110)

            for p_text in sec.paragraphs:
                p = doc.add_paragraph(re_fmt(p_text))
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.1
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(8.5)

            for b_text in sec.bullets:
                p = doc.add_paragraph(re_fmt(b_text), style='List Bullet')
                p.paragraph_format.space_after = Pt(1.5)
                p.paragraph_format.line_spacing = 1.1
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(8.5)

        p_sig = doc.add_paragraph()
        p_sig.paragraph_format.space_before = Pt(8)
        p_sig.add_run(f"Electronically signed: {meta.dictating_physician} • MRP: {meta.attending_physician} • {meta.date} {meta.time}").font.size = Pt(7.5)

        return doc
