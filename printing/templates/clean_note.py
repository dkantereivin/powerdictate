"""
Clean Standard Note Print Template
==================================
Minimalist, elegant, modern medical letterhead note template.
Features crisp typography, clean horizontal dividers, and a balanced layout
suitable for any specialty consult, clinic note, or discharge summary.
"""

import html
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from printing.models import ClinicalNote
from printing.templates.base import BasePrintTemplate
from printing.templates.tbrhsc_consult import re_fmt, html_format_markdown_inline


class CleanNoteTemplate(BasePrintTemplate):
    """Minimalist, crisp, modern clinical documentation template."""

    template_id = "clean_note"
    name = "Clean Standard Note"
    description = "Crisp, minimalist medical letterhead layout suitable for any general clinical documentation or clinic note."

    def render_html(self, note: ClinicalNote) -> str:
        meta = note.metadata

        pt_name = meta.patient_name or "PATIENT RECORD"
        mrn_val = meta.mrn or "—"
        date_val = meta.date
        mrp_md = meta.attending_physician or "Staff Physician"
        dict_md = meta.dictating_physician or "Dictating Physician"

        # Demographics Banner
        header_banner = f"""
        <div class="clean-header">
            <div class="h-title">{html.escape(note.title or 'CLINICAL NOTE')}</div>
            <div class="h-sub">{html.escape(meta.hospital_name)} • {html.escape(meta.department)}</div>
            <div class="h-meta-row">
                <span><strong>Patient:</strong> {html.escape(pt_name)}</span>
                <span><strong>MRN:</strong> {html.escape(mrn_val)}</span>
                <span><strong>Date:</strong> {html.escape(date_val)}</span>
                <span><strong>MRP:</strong> {html.escape(mrp_md)}</span>
            </div>
        </div>
        """

        # Sections
        sections_html = []
        for sec in note.sections:
            sec_body = []
            for p in sec.paragraphs:
                sec_body.append(f"<p class='sec-p'>{html_format_markdown_inline(p)}</p>")
            if sec.bullets:
                sec_body.append("<ul class='sec-ul'>")
                for b in sec.bullets:
                    sec_body.append(f"<li>{html_format_markdown_inline(b)}</li>")
                sec_body.append("</ul>")

            body_content = "".join(sec_body) if sec_body else f"<p class='sec-p'>{html.escape(sec.raw_content)}</p>"

            sections_html.append(f"""
            <div class="clean-section">
                <div class="sec-heading">{html.escape(sec.title)}</div>
                <div class="sec-content">{body_content}</div>
            </div>
            """)

        body_html = "\n".join(sections_html)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(note.title)}</title>
<style>
    @page {{
        size: letter;
        margin: 15mm 15mm 18mm 15mm;
        @bottom-right {{
            content: "Page " counter(page) " of " counter(pages);
            font-size: 8pt;
            color: #94a3b8;
        }}
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        font-size: 9.5pt;
        line-height: 1.4;
        color: #1e293b;
        margin: 0;
        padding: 0;
        background-color: #ffffff;
    }}
    .clean-header {{
        border-bottom: 2px solid #0f172a;
        padding-bottom: 8px;
        margin-bottom: 12px;
    }}
    .h-title {{
        font-size: 14pt;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: 0.3px;
        margin-bottom: 2px;
    }}
    .h-sub {{
        font-size: 8.5pt;
        color: #64748b;
        margin-bottom: 6px;
    }}
    .h-meta-row {{
        font-size: 8.5pt;
        color: #334155;
        display: flex;
        gap: 16px;
        background-color: #f8fafc;
        padding: 4px 8px;
        border-radius: 4px;
    }}
    .clean-section {{
        margin-bottom: 10px;
        page-break-inside: avoid;
    }}
    .sec-heading {{
        font-size: 9.5pt;
        font-weight: 700;
        color: #0f172a;
        text-transform: uppercase;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 2px;
        margin-bottom: 4px;
        letter-spacing: 0.2px;
    }}
    .sec-p {{
        margin: 0 0 4px 0;
    }}
    .sec-ul {{
        margin: 2px 0 4px 0;
        padding-left: 18px;
    }}
    .clean-footer {{
        margin-top: 16px;
        border-top: 1px solid #e2e8f0;
        padding-top: 6px;
        font-size: 8pt;
        color: #64748b;
        display: flex;
        justify-content: space-between;
    }}
</style>
</head>
<body>
    {header_banner}
    {body_html}
    <div class="clean-footer">
        <div><strong>Dictated by:</strong> {html.escape(dict_md)} &nbsp;|&nbsp; <strong>MRP:</strong> {html.escape(mrp_md)}</div>
        <div>Date: {html.escape(date_val)} • Confidential Medical Record</div>
    </div>
</body>
</html>
"""

    def render_docx(self, note: ClinicalNote) -> docx.Document:
        """Renders minimalist clean note in Word format."""
        doc = docx.Document()
        meta = note.metadata

        for section in doc.sections:
            section.top_margin = Inches(0.6)
            section.bottom_margin = Inches(0.6)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)

        p_t = doc.add_paragraph()
        run_t = p_t.add_run(note.title or "CLINICAL NOTE")
        run_t.font.name = "Arial"
        run_t.font.size = Pt(13)
        run_t.font.bold = True
        p_t.paragraph_format.space_after = Pt(2)

        p_sub = doc.add_paragraph(f"{meta.hospital_name} • {meta.department}")
        p_sub.paragraph_format.space_after = Pt(4)
        for r in p_sub.runs:
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(100, 116, 139)

        p_meta = doc.add_paragraph(f"Patient: {meta.patient_name or '—'}  |  MRN: {meta.mrn or '—'}  |  Date: {meta.date}  |  MRP: {meta.attending_physician}")
        p_meta.paragraph_format.space_after = Pt(10)
        for r in p_meta.runs:
            r.font.size = Pt(8.5)
            r.font.bold = True

        for sec in note.sections:
            h = doc.add_heading(sec.title.upper(), level=2)
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(2)
            for r in h.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                r.font.bold = True
                r.font.color.rgb = RGBColor(15, 23, 42)

            for p_text in sec.paragraphs:
                p = doc.add_paragraph(re_fmt(p_text))
                p.paragraph_format.space_after = Pt(3)
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)

            for b_text in sec.bullets:
                p = doc.add_paragraph(re_fmt(b_text), style='List Bullet')
                p.paragraph_format.space_after = Pt(2)
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)

        p_sig = doc.add_paragraph()
        p_sig.paragraph_format.space_before = Pt(14)
        p_sig.add_run(f"Dictated by: {meta.dictating_physician}  |  MRP: {meta.attending_physician}  |  {meta.date}").font.size = Pt(8)

        return doc
