"""
Clinical PDF Document Generator
===============================
Converts clinical notes and templates into high-resolution, vector PDF documents
using PySide6 QtPrintSupport (QPrinter & QTextDocument) with exact margins,
Letter paper layout, and page-break handling.
"""

import sys
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
from PySide6.QtCore import QMarginsF
from PySide6.QtPrintSupport import QPrinter

from printing.models import ClinicalNote
from printing.templates import get_template, BasePrintTemplate


class PdfGenerator:
    """Generates crisp vector PDF files from ClinicalNote objects using Qt."""

    @classmethod
    def generate_pdf(
        cls,
        note: ClinicalNote,
        template_id: Optional[str] = "tbrhsc_consult",
        output_path: Optional[str] = None
    ) -> str:
        """
        Renders note using specified template and exports to vector PDF.
        Returns the absolute file path of the generated PDF.
        """
        # Ensure a QApplication instance exists
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        template: BasePrintTemplate = get_template(template_id)
        rendered_html = template.render_html(note)

        # Determine output file path
        if not output_path:
            out_dir = Path("outputs")
            out_dir.mkdir(parents=True, exist_ok=True)
            mrn_str = note.metadata.mrn or "UnknownMRN"
            date_clean = note.metadata.date.replace(" ", "_").replace(",", "")
            t_id = template.template_id
            output_path = str(out_dir / f"{t_id}_{mrn_str}_{date_clean}.pdf")

        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure QPrinter for HighResolution PDF Output
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(out_path))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))

        # Adjust margins based on template density
        if template.template_id == "progress_note":
            margins = QMarginsF(11.0, 10.0, 11.0, 12.0)  # mm
        else:
            margins = QMarginsF(14.0, 14.0, 14.0, 16.0)  # mm

        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.Letter),
            QPageLayout.Orientation.Portrait,
            margins,
            QPageLayout.Unit.Millimeter
        )
        printer.setPageLayout(layout)

        # Render HTML into QTextDocument and print to PDF
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(rendered_html)
        doc.print_(printer)

        return str(out_path)
