"""
Printer Service
===============
Manages discovery of local and network printers (e.g. Brother MFC-9320CW, CUPS),
handles direct printing, and launches native system print dialogs.
"""

import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
from PySide6.QtCore import QMarginsF
from PySide6.QtPrintSupport import QPrinterInfo, QPrinter, QPrintDialog

from printing.models import ClinicalNote
from printing.templates import get_template, BasePrintTemplate
from printing.pdf_generator import PdfGenerator

logger = logging.getLogger("printing.printer_service")


class PrinterService:
    """Manages system/network printer discovery and document printing."""

    @classmethod
    def get_available_printers(cls) -> List[str]:
        """Returns list of all available network and local printer names."""
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        printers = list(QPrinterInfo.availablePrinterNames())
        if not printers:
            # Fallback to lpstat
            try:
                out = subprocess.check_output(["lpstat", "-p"], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] == "printer":
                        printers.append(parts[1])
            except Exception:
                pass

        return printers

    @classmethod
    def get_default_printer(cls) -> Optional[str]:
        """Returns name of the default printer or first available printer."""
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        default_info = QPrinterInfo.defaultPrinter()
        if default_info and not default_info.isNull() and default_info.printerName():
            return default_info.printerName()

        available = cls.get_available_printers()
        return available[0] if available else None

    @classmethod
    def print_document(
        cls,
        note: ClinicalNote,
        template_id: str = "tbrhsc_consult",
        printer_name: Optional[str] = None,
        copies: int = 1,
        show_dialog: bool = False,
        parent_widget: Optional[QWidget] = None
    ) -> bool:
        """
        Prints the clinical note using the specified template.
        If show_dialog is True, presents the native OS QPrintDialog.
        Otherwise prints directly to printer_name.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        template: BasePrintTemplate = get_template(template_id)
        rendered_html = template.render_html(note)

        # Setup printer
        if printer_name:
            p_info = QPrinterInfo.printerInfo(printer_name)
            printer = QPrinter(p_info, QPrinter.PrinterMode.HighResolution)
        else:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        printer.setCopyCount(max(1, copies))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))

        # Margin setup
        if template_id == "progress_note":
            margins = QMarginsF(11.0, 10.0, 11.0, 12.0)
        else:
            margins = QMarginsF(14.0, 14.0, 14.0, 16.0)

        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.Letter),
            QPageLayout.Orientation.Portrait,
            margins,
            QPageLayout.Unit.Millimeter
        )
        printer.setPageLayout(layout)

        # Optional QPrintDialog
        if show_dialog:
            dialog = QPrintDialog(printer, parent_widget)
            dialog.setWindowTitle(f"Print - {note.title}")
            if dialog.exec() != QPrintDialog.DialogCode.Accepted:
                logger.info("Print cancelled by user in print dialog.")
                return False

        # Render and print
        try:
            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setHtml(rendered_html)
            doc.print_(printer)
            logger.info(f"Document successfully sent to printer: {printer.printerName()}")
            return True
        except Exception as e:
            logger.error(f"Error printing document: {e}", exc_info=True)
            # Try lp CLI fallback
            try:
                pdf_path = PdfGenerator.generate_pdf(note, template_id)
                cmd = ["lp"]
                if printer_name:
                    cmd.extend(["-d", printer_name])
                if copies > 1:
                    cmd.extend(["-n", str(copies)])
                cmd.append(pdf_path)
                subprocess.run(cmd, check=True)
                logger.info(f"Printed via CLI fallback: {' '.join(cmd)}")
                return True
            except Exception as ex:
                logger.error(f"CLI fallback failed: {ex}")
                return False
