"""
Clinical DOCX Document Generator
================================
Converts clinical notes into native Microsoft Word (.docx) documents
with styled headers, demographic grids, and section typography.
"""

from pathlib import Path
from typing import Optional
from printing.models import ClinicalNote
from printing.templates import get_template, BasePrintTemplate


class DocxGenerator:
    """Generates editable Microsoft Word (.docx) files from ClinicalNote objects."""

    @classmethod
    def generate_docx(
        cls,
        note: ClinicalNote,
        template_id: Optional[str] = "tbrhsc_consult",
        output_path: Optional[str] = None
    ) -> str:
        """
        Renders note using specified template and exports to .docx.
        Returns the absolute file path of the generated Word document.
        """
        template: BasePrintTemplate = get_template(template_id)
        doc = template.render_docx(note)

        if not output_path:
            out_dir = Path("outputs")
            out_dir.mkdir(parents=True, exist_ok=True)
            mrn_str = note.metadata.mrn or "UnknownMRN"
            date_clean = note.metadata.date.replace(" ", "_").replace(",", "")
            t_id = template.template_id
            output_path = str(out_dir / f"{t_id}_{mrn_str}_{date_clean}.docx")

        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_path))

        return str(out_path)
