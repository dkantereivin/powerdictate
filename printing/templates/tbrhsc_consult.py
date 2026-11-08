"""
TBRHSC Consult Note Print Template
==================================
Comprehensive consultation note template for Thunder Bay Regional Health Sciences
Centre (TBRHSC) Internal Medicine & Specialty services.
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


class TBRHSCConsultTemplate(BasePrintTemplate):
    """Formal Thunder Bay Regional Health Sciences Centre Consultation Note template."""

    template_id = "tbrhsc_consult"
    name = "TBRHSC Consult Note"
    description = "Formal institutional consultation note for Thunder Bay Regional Health Sciences Centre with full demographic grid, alert badges, and attestation blocks."

    def render_html(self, note: ClinicalNote) -> str:
        meta = note.metadata

        # Format Allergies Box
        if note.allergies_list:
            allergies_html = " • ".join(
                html.escape(re_fmt(a)) for a in note.allergies_list
            )
            allergies_table = f"""
            <table width="100%" bgcolor="#fef2f2" border="1" bordercolor="#ef4444" cellpadding="5" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td><font color="#b91c1c"><b>⚠️ ALLERGIES / ADVERSE REACTIONS:</b></font> {allergies_html}</td>
                </tr>
            </table>
            """
        elif meta.allergies:
            allergies_table = f"""
            <table width="100%" bgcolor="#fef2f2" border="1" bordercolor="#ef4444" cellpadding="5" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td><font color="#b91c1c"><b>⚠️ ALLERGIES / ADVERSE REACTIONS:</b></font> {html.escape(meta.allergies)}</td>
                </tr>
            </table>
            """
        else:
            allergies_table = """
            <table width="100%" bgcolor="#f0fdf4" border="1" bordercolor="#10b981" cellpadding="5" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td><font color="#047857"><b>✓ ALLERGIES:</b></font> No Known Drug Allergies (NKDA)</td>
                </tr>
            </table>
            """

        # Format Reason for Consult Callout Box
        reason_text = meta.reason_for_consult or "Internal Medicine Consultation & Comorbidity Optimization"
        reason_table = f"""
        <table width="100%" bgcolor="#f0f9ff" border="1" bordercolor="#0284c7" cellpadding="5" cellspacing="0" style="margin-bottom: 8px;">
            <tr>
                <td><font color="#0369a1"><b>REASON FOR CONSULTATION:</b></font> {html.escape(reason_text)}</td>
            </tr>
        </table>
        """

        # Format Demographics Grid
        pt_name = meta.patient_name or "PATIENT RECORD"
        mrn_val = meta.mrn or "—"
        hcn_val = meta.hcn or "—"
        age_sex = meta.age_gender or "—"
        room_val = meta.room_bed or "MCTU Ward"
        date_val = meta.date
        req_svc = meta.requesting_service or "General Medical Service"
        req_md = meta.requesting_physician or "Referring Physician"
        mrp_md = meta.attending_physician or "Dr. Vandermeer, Staff"
        dict_md = meta.dictating_physician or "David Kanter Eivin, PGY1"

        demo_grid = f"""
        <table width="100%" bgcolor="#f8fafc" border="1" bordercolor="#cbd5e1" cellpadding="4" cellspacing="0" style="margin-bottom: 8px;">
            <tr>
                <td bgcolor="#f1f5f9" width="16%"><b>Patient Name:</b></td>
                <td width="34%"><b>{html.escape(pt_name)}</b></td>
                <td bgcolor="#f1f5f9" width="18%"><b>Date of Consult:</b></td>
                <td width="32%">{html.escape(date_val)}</td>
            </tr>
            <tr>
                <td bgcolor="#f1f5f9"><b>MRN:</b></td>
                <td><b>{html.escape(mrn_val)}</b></td>
                <td bgcolor="#f1f5f9"><b>Requesting Service:</b></td>
                <td>{html.escape(req_svc)}</td>
            </tr>
            <tr>
                <td bgcolor="#f1f5f9"><b>Age / Gender:</b></td>
                <td>{html.escape(age_sex)}</td>
                <td bgcolor="#f1f5f9"><b>Requesting MD:</b></td>
                <td>{html.escape(req_md)}</td>
            </tr>
            <tr>
                <td bgcolor="#f1f5f9"><b>Location / Bed:</b></td>
                <td>{html.escape(room_val)}</td>
                <td bgcolor="#f1f5f9"><b>MRP / Attending:</b></td>
                <td><b>{html.escape(mrp_md)}</b></td>
            </tr>
            <tr>
                <td bgcolor="#f1f5f9"><b>Health Card (HCN):</b></td>
                <td>{html.escape(hcn_val)}</td>
                <td bgcolor="#f1f5f9"><b>Dictating Physician:</b></td>
                <td>{html.escape(dict_md)}</td>
            </tr>
        </table>
        """

        # Format Vitals Bar if extracted
        vitals_bar = ""
        if note.vitals:
            v_cells = [f"<b>{k}:</b> {html.escape(v)}" for k, v in note.vitals.items()]
            vitals_bar = f"""
            <table width="100%" bgcolor="#f8fafc" border="1" bordercolor="#e2e8f0" cellpadding="4" cellspacing="0" style="margin-bottom: 8px;">
                <tr>
                    <td><font color="#0369a1"><b>RECORDED VITALS:</b></font> &nbsp;|&nbsp; {" &nbsp;|&nbsp; ".join(v_cells)}</td>
                </tr>
            </table>
            """

        # Format Sections
        sections_html = []
        for sec in note.sections:
            title_upper = sec.title.upper()
            if any(skip in title_upper for skip in ["ALLERG", "IDENTIFYING DATA"]):
                continue

            sec_body = []
            for p in sec.paragraphs:
                clean_p = html_format_markdown_inline(p)
                sec_body.append(f"<p style='margin: 0 0 4px 0; text-align: justify;'>{clean_p}</p>")

            if sec.bullets:
                sec_body.append("<ul style='margin: 2px 0 4px 0; padding-left: 20px;'>")
                for b in sec.bullets:
                    clean_b = html_format_markdown_inline(b)
                    sec_body.append(f"<li style='margin-bottom: 2px;'>{clean_b}</li>")
                sec_body.append("</ul>")

            body_content = "".join(sec_body) if sec_body else f"<p style='margin: 0 0 4px 0;'>{html.escape(sec.raw_content)}</p>"

            sections_html.append(f"""
            <table width="100%" bgcolor="#f1f5f9" cellpadding="4" cellspacing="0" style="margin-top: 10px; margin-bottom: 4px;">
                <tr>
                    <td><font color="#003865" size="2"><b>{html.escape(sec.title.upper())}</b></font></td>
                </tr>
            </table>
            <div style="margin-bottom: 8px; padding-left: 2px;">
                {body_content}
            </div>
            """)

        body_html = "\n".join(sections_html)

        # Attestation Statement
        attestation_stmt = note.attestation_statement or (
            "The findings, diagnostic impressions, and management plans have been discussed "
            "with the patient and primary care team. Internal Medicine will continue to follow."
        )

        signature_table = f"""
        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin-top: 14px;">
            <tr>
                <td colspan="3" style="font-size: 8pt; color: #475569; border-top: 1px dashed #cbd5e1; padding-top: 6px; padding-bottom: 10px;">
                    <em>{html.escape(attestation_stmt)}</em>
                </td>
            </tr>
            <tr>
                <td width="48%" valign="top">
                    <hr color="#334155" size="1" style="margin-bottom: 4px;">
                    <b>{html.escape(dict_md)}</b><br>
                    <font size="1" color="#475569">Internal Medicine Resident / Fellow<br>
                    Thunder Bay Regional Health Sciences Centre<br>
                    Date/Time: {html.escape(date_val)} {html.escape(meta.time)}</font>
                </td>
                <td width="4%"></td>
                <td width="48%" valign="top">
                    <hr color="#334155" size="1" style="margin-bottom: 4px;">
                    <b>{html.escape(mrp_md)}</b><br>
                    <font size="1" color="#475569">Most Responsible Physician (MRP) / Attending Staff<br>
                    <font color="#0284c7"><i>Staff Attestation: Examined patient & reviewed care plan</i></font><br>
                    Date/Time: {html.escape(date_val)}</font>
                </td>
            </tr>
        </table>
        """

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(note.title)}</title>
</head>
<body style="font-family: Arial, Helvetica, sans-serif; font-size: 9.5pt; line-height: 1.35; color: #1e293b;">

    <!-- Institutional Header Banner -->
    <table width="100%" bgcolor="#003865" cellpadding="8" cellspacing="0">
        <tr>
            <td valign="top">
                <font color="#ffffff" size="4"><b>THUNDER BAY REGIONAL HEALTH SCIENCES CENTRE</b></font><br>
                <font color="#7dd3fc" size="2"><b>Department of Internal Medicine • Medicine Teaching Unit (MCTU)</b></font><br>
                <font color="#cbd5e1" size="1">980 Oliver Road, Thunder Bay, ON P7B 6V4 • Hospital Switchboard: (807) 684-6000</font>
            </td>
            <td align="right" valign="middle">
                <table bgcolor="#0284c7" cellpadding="6" cellspacing="0">
                    <tr>
                        <td><font color="#ffffff" size="3"><b>CONSULTATION NOTE</b></font></td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    <hr color="#0284c7" size="3" style="margin: 0 0 8px 0;">

    <!-- Demographics Grid -->
    {demo_grid}

    <!-- Reason for Consult -->
    {reason_table}

    <!-- Allergies Alert -->
    {allergies_table}

    <!-- Vitals Strip -->
    {vitals_bar}

    <!-- Clinical Sections -->
    {body_html}

    <!-- Dual Signature Block -->
    {signature_table}

    <!-- Running Footer -->
    <br>
    <table width="100%" border="0" cellpadding="2" cellspacing="0" style="border-top: 1px solid #cbd5e1; font-size: 7.5pt; color: #94a3b8;">
        <tr>
            <td>Confidential Medical Record • Thunder Bay Regional Health Sciences Centre</td>
            <td align="right">Internal Medicine Clinical Consultation Note</td>
        </tr>
    </table>

</body>
</html>
"""

    def render_docx(self, note: ClinicalNote) -> docx.Document:
        """Renders styled native Microsoft Word .docx document."""
        doc = docx.Document()
        meta = note.metadata

        for section in doc.sections:
            section.top_margin = Inches(0.6)
            section.bottom_margin = Inches(0.6)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)

        p_inst = doc.add_paragraph()
        run_inst = p_inst.add_run(meta.hospital_name.upper())
        run_inst.font.name = "Arial"
        run_inst.font.size = Pt(13)
        run_inst.font.bold = True
        run_inst.font.color.rgb = RGBColor(0, 56, 101)
        p_inst.paragraph_format.space_after = Pt(1)

        p_dept = doc.add_paragraph()
        run_dept = p_dept.add_run(f"{meta.department} • {meta.ward_unit}")
        run_dept.font.name = "Arial"
        run_dept.font.size = Pt(9.5)
        run_dept.font.bold = True
        run_dept.font.color.rgb = RGBColor(2, 132, 199)
        p_dept.paragraph_format.space_after = Pt(4)

        p_title = doc.add_paragraph()
        run_title = p_title.add_run("INTERNAL MEDICINE CONSULTATION NOTE")
        run_title.font.name = "Arial"
        run_title.font.size = Pt(11)
        run_title.font.bold = True
        run_title.font.color.rgb = RGBColor(255, 255, 255)
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        shading = parse_xml(r'<w:shd {} w:fill="003865"/>'.format(nsdecls('w')))
        p_title._p.get_or_add_pPr().append(shading)
        p_title.paragraph_format.space_before = Pt(4)
        p_title.paragraph_format.space_after = Pt(8)

        # Demographics Table
        table = doc.add_table(rows=5, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        demo_data = [
            ("Patient Name:", meta.patient_name or "PATIENT RECORD", "Date of Consult:", meta.date),
            ("MRN:", meta.mrn or "—", "Requesting Service:", meta.requesting_service or "General Medicine"),
            ("Age / Gender:", meta.age_gender or "—", "Requesting MD:", meta.requesting_physician or "Referring MD"),
            ("Location / Bed:", meta.room_bed or "MCTU Ward", "MRP / Attending:", meta.attending_physician or "Dr. Vandermeer"),
            ("Health Card (HCN):", meta.hcn or "—", "Dictating MD:", meta.dictating_physician or "David Kanter Eivin, PGY1")
        ]

        for row_idx, data in enumerate(demo_data):
            row = table.rows[row_idx]
            for col_idx in range(4):
                cell = row.cells[col_idx]
                cell.text = data[col_idx]
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    for r in p.runs:
                        r.font.name = "Arial"
                        r.font.size = Pt(8.5)
                        if col_idx in (0, 2):
                            r.font.bold = True
                            r.font.color.rgb = RGBColor(71, 85, 105)
                        else:
                            r.font.color.rgb = RGBColor(15, 23, 42)

                if col_idx in (0, 2):
                    c_shd = parse_xml(r'<w:shd {} w:fill="F1F5F9"/>'.format(nsdecls('w')))
                    cell._tc.get_or_add_tcPr().append(c_shd)
                else:
                    c_shd = parse_xml(r'<w:shd {} w:fill="F8FAFC"/>'.format(nsdecls('w')))
                    cell._tc.get_or_add_tcPr().append(c_shd)

        # Reason for Consult
        p_rsn = doc.add_paragraph()
        p_rsn.paragraph_format.space_before = Pt(8)
        p_rsn.paragraph_format.space_after = Pt(4)
        run_rsn_lbl = p_rsn.add_run("REASON FOR CONSULTATION: ")
        run_rsn_lbl.font.bold = True
        run_rsn_lbl.font.color.rgb = RGBColor(3, 105, 161)
        run_rsn_lbl.font.size = Pt(8.5)
        run_rsn_val = p_rsn.add_run(meta.reason_for_consult or "Internal Medicine Consultation & Comorbidity Optimization")
        run_rsn_val.font.size = Pt(8.5)
        shd_rsn = parse_xml(r'<w:shd {} w:fill="F0F9FF"/>'.format(nsdecls('w')))
        p_rsn._p.get_or_add_pPr().append(shd_rsn)

        # Allergies
        p_all = doc.add_paragraph()
        p_all.paragraph_format.space_before = Pt(2)
        p_all.paragraph_format.space_after = Pt(8)
        if note.allergies_list or meta.allergies:
            run_all_lbl = p_all.add_run("⚠️ ALLERGIES / ADVERSE REACTIONS: ")
            run_all_lbl.font.bold = True
            run_all_lbl.font.color.rgb = RGBColor(185, 28, 28)
            all_text = " • ".join(re_fmt(a) for a in note.allergies_list) if note.allergies_list else meta.allergies
            run_all_val = p_all.add_run(all_text)
            shd_all = parse_xml(r'<w:shd {} w:fill="FEF2F2"/>'.format(nsdecls('w')))
        else:
            run_all_lbl = p_all.add_run("✓ ALLERGIES: ")
            run_all_lbl.font.bold = True
            run_all_lbl.font.color.rgb = RGBColor(4, 120, 87)
            run_all_val = p_all.add_run("No Known Drug Allergies (NKDA)")
            shd_all = parse_xml(r'<w:shd {} w:fill="F0FDF4"/>'.format(nsdecls('w')))
        run_all_lbl.font.size = Pt(8.5)
        run_all_val.font.size = Pt(8.5)
        p_all._p.get_or_add_pPr().append(shd_all)

        # Sections
        for sec in note.sections:
            if any(skip in sec.title.upper() for skip in ["ALLERG", "IDENTIFYING DATA"]):
                continue

            h = doc.add_heading(sec.title.upper(), level=2)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(3)
            for r in h.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(0, 56, 101)

            for p_text in sec.paragraphs:
                p = doc.add_paragraph(re_fmt(p_text))
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.15
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)

            for b_text in sec.bullets:
                p = doc.add_paragraph(re_fmt(b_text), style='List Bullet')
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.15
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)

        # Dual Signature Block
        doc.add_paragraph().paragraph_format.space_before = Pt(12)
        sig_table = doc.add_table(rows=1, cols=2)
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        sig_table.autofit = True

        cell_res = sig_table.rows[0].cells[0]
        p_res = cell_res.paragraphs[0]
        p_res.add_run("_________________________________________\n").font.color.rgb = RGBColor(71, 85, 105)
        r_r1 = p_res.add_run(f"{meta.dictating_physician}\n")
        r_r1.font.bold = True
        p_res.add_run("Internal Medicine Resident / Fellow\n")
        p_res.add_run("Thunder Bay Regional Health Sciences Centre\n")
        p_res.add_run(f"Date: {meta.date} {meta.time}\n")

        cell_staff = sig_table.rows[0].cells[1]
        p_staff = cell_staff.paragraphs[0]
        p_staff.add_run("_________________________________________\n").font.color.rgb = RGBColor(71, 85, 105)
        r_s1 = p_staff.add_run(f"{meta.attending_physician}\n")
        r_s1.font.bold = True
        p_staff.add_run("Most Responsible Physician (MRP) / Attending Staff\n")
        p_staff.add_run("Attestation: Examined patient & reviewed care plan\n")
        p_staff.add_run(f"Date: {meta.date}\n")

        for c in (cell_res, cell_staff):
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Arial"
                    r.font.size = Pt(8)

        return doc


def re_fmt(text: str) -> str:
    """Strips Markdown bolding and excessive asterisks for plain text insertion."""
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    return cleaned.strip()


def html_format_markdown_inline(text: str) -> str:
    """Converts inline markdown bolding **text** to HTML <strong> tags safely."""
    escaped = html.escape(text)
    bold_sub = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    italic_sub = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", bold_sub)
    return italic_sub
