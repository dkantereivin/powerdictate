"""
Clinical Print Preview & Document Export Dialog
===============================================
Provides an interactive real-time visual preview of clinical notes rendered in
different institutional print templates (TBRHSC Consult Note, Progress Note, Clean Note),
with direct printing to local/network printers (e.g. Brother MFC-9320CW) and export
to vector PDF and editable Word DOCX.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTextBrowser, QFileDialog, QGraphicsDropShadowEffect,
    QWidget, QStyleOption, QStyle, QFrame, QLineEdit, QSplitter
)

from printing.models import ClinicalNote, PatientMetadata
from printing.parser import ClinicalNoteParser
from printing.templates import get_template, list_templates, DEFAULT_TEMPLATE_ID
from printing.pdf_generator import PdfGenerator
from printing.docx_generator import DocxGenerator
from printing.printer_service import PrinterService


class PrintPreviewDialog(QDialog):
    """
    Sleek interactive print formatting, live preview, and document export dialog.
    """

    def __init__(self, raw_note_text: str, parent=None, default_template: str = DEFAULT_TEMPLATE_ID):
        super().__init__(parent)
        self.raw_note_text = raw_note_text
        self.current_template_id = default_template

        # Parse clinical note data
        self.note: ClinicalNote = ClinicalNoteParser.parse(raw_note_text)

        self.setWindowTitle("Clinical Document Print & Export Preview")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(920, 800)
        self.setMinimumSize(700, 600)

        self._init_ui()
        self._load_printers()
        self._update_preview()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        self.setStyleSheet("background-color: #0b1120; color: #f8fafc;")

        # Top Control Bar
        top_bar = QWidget(self)
        top_bar.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 10px;
            padding: 4px;
        """)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(10, 8, 10, 8)
        tb_layout.setSpacing(10)

        # Template Selection Dropdown
        tpl_lbl = QLabel("Template:", top_bar)
        tpl_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        tpl_lbl.setStyleSheet("color: #38bdf8;")
        tb_layout.addWidget(tpl_lbl)

        self.template_combo = QComboBox(top_bar)
        self.template_combo.setMinimumWidth(180)
        self.template_combo.setFont(QFont("Segoe UI", 9))
        self.template_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 10px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #0284c7;
            }
        """)

        for t_info in list_templates():
            icon_prefix = "📋 " if "consult" in t_info["id"] else ("📝 " if "progress" in t_info["id"] else "📄 ")
            self.template_combo.addItem(f"{icon_prefix}{t_info['name']}", t_info["id"])

        idx = self.template_combo.findData(self.current_template_id)
        if idx >= 0:
            self.template_combo.setCurrentIndex(idx)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        tb_layout.addWidget(self.template_combo)

        # Metadata Quick Editor Toggle
        self.meta_toggle_btn = QPushButton("✏️ Patient Info", top_bar)
        self.meta_toggle_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.meta_toggle_btn.setCheckable(True)
        self.meta_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
            QPushButton:checked {
                background-color: #0c4a6e;
                color: #38bdf8;
                border-color: #0284c7;
            }
        """)
        self.meta_toggle_btn.toggled.connect(self._on_meta_toggle)
        tb_layout.addWidget(self.meta_toggle_btn)

        tb_layout.addStretch()

        # Target Printer Selection
        prn_lbl = QLabel("Printer:", top_bar)
        prn_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        prn_lbl.setStyleSheet("color: #38bdf8;")
        tb_layout.addWidget(prn_lbl)

        self.printer_combo = QComboBox(top_bar)
        self.printer_combo.setMinimumWidth(160)
        self.printer_combo.setFont(QFont("Segoe UI", 9))
        self.printer_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 10px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
        """)
        tb_layout.addWidget(self.printer_combo)

        # Action: Direct Print Button
        self.print_btn = QPushButton("🖨️ Print Now", top_bar)
        self.print_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border-radius: 6px;
                padding: 6px 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.print_btn.clicked.connect(self._on_print_clicked)
        tb_layout.addWidget(self.print_btn)

        main_layout.addWidget(top_bar)

        # Middle Metadata Panel (Collapsible)
        self.meta_panel = QWidget(self)
        self.meta_panel.setVisible(False)
        self.meta_panel.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 4px;
        """)
        mp_layout = QHBoxLayout(self.meta_panel)
        mp_layout.setContentsMargins(8, 6, 8, 6)
        mp_layout.setSpacing(8)

        # Patient Name
        mp_layout.addWidget(QLabel("Name:", self.meta_panel))
        self.pt_name_edit = QLineEdit(self.note.metadata.patient_name or "", self.meta_panel)
        self.pt_name_edit.setPlaceholderText("Patient Name")
        self.pt_name_edit.setStyleSheet("background-color: #1e293b; color: white; border: 1px solid #334155; border-radius: 4px; padding: 3px 6px;")
        self.pt_name_edit.textChanged.connect(self._on_meta_edited)
        mp_layout.addWidget(self.pt_name_edit)

        # MRN
        mp_layout.addWidget(QLabel("MRN:", self.meta_panel))
        self.mrn_edit = QLineEdit(self.note.metadata.mrn or "", self.meta_panel)
        self.mrn_edit.setPlaceholderText("MRN")
        self.mrn_edit.setStyleSheet("background-color: #1e293b; color: white; border: 1px solid #334155; border-radius: 4px; padding: 3px 6px;")
        self.mrn_edit.textChanged.connect(self._on_meta_edited)
        mp_layout.addWidget(self.mrn_edit)

        # Attending (MRP)
        mp_layout.addWidget(QLabel("MRP:", self.meta_panel))
        self.mrp_edit = QLineEdit(self.note.metadata.attending_physician or "", self.meta_panel)
        self.mrp_edit.setPlaceholderText("Attending Physician")
        self.mrp_edit.setStyleSheet("background-color: #1e293b; color: white; border: 1px solid #334155; border-radius: 4px; padding: 3px 6px;")
        self.mrp_edit.textChanged.connect(self._on_meta_edited)
        mp_layout.addWidget(self.mrp_edit)

        # Dictator (Resident)
        mp_layout.addWidget(QLabel("Dictator:", self.meta_panel))
        self.dict_edit = QLineEdit(self.note.metadata.dictating_physician or "", self.meta_panel)
        self.dict_edit.setPlaceholderText("Dictating Physician")
        self.dict_edit.setStyleSheet("background-color: #1e293b; color: white; border: 1px solid #334155; border-radius: 4px; padding: 3px 6px;")
        self.dict_edit.textChanged.connect(self._on_meta_edited)
        mp_layout.addWidget(self.dict_edit)

        main_layout.addWidget(self.meta_panel)

        # Center Paper Canvas Preview
        preview_container = QWidget(self)
        preview_container.setStyleSheet("background-color: #030712; border-radius: 10px;")
        pc_layout = QVBoxLayout(preview_container)
        pc_layout.setContentsMargins(20, 16, 20, 16)

        # Simulated Paper View
        self.preview_browser = QTextBrowser(preview_container)
        self.preview_browser.setOpenExternalLinks(True)
        self.preview_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 16px 20px;
                selection-background-color: #0284c7;
            }
        """)

        # Add drop shadow to make it feel like a real physical paper document
        shadow = QGraphicsDropShadowEffect(self.preview_browser)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 4)
        self.preview_browser.setGraphicsEffect(shadow)

        pc_layout.addWidget(self.preview_browser)
        main_layout.addWidget(preview_container, stretch=1)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(4, 2, 4, 2)
        bottom_bar.setSpacing(10)

        self.status_lbl = QLabel("Ready to print or export.", self)
        self.status_lbl.setFont(QFont("Segoe UI", 8))
        self.status_lbl.setStyleSheet("color: #94a3b8;")
        bottom_bar.addWidget(self.status_lbl)

        bottom_bar.addStretch()

        # Save PDF Button
        self.pdf_btn = QPushButton("💾 Save PDF", self)
        self.pdf_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #38bdf8;
            }
        """)
        self.pdf_btn.clicked.connect(self._on_save_pdf_clicked)
        bottom_bar.addWidget(self.pdf_btn)

        # Save Word DOCX Button
        self.docx_btn = QPushButton("📄 Save Word (DOCX)", self)
        self.docx_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.docx_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #38bdf8;
            }
        """)
        self.docx_btn.clicked.connect(self._on_save_docx_clicked)
        bottom_bar.addWidget(self.docx_btn)

        # Copy Rich Text / HTML
        self.copy_btn = QPushButton("📋 Copy HTML", self)
        self.copy_btn.setFont(QFont("Segoe UI", 8))
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                color: #f8fafc;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy_html_clicked)
        bottom_bar.addWidget(self.copy_btn)

        # Close Button
        close_btn = QPushButton("Close", self)
        close_btn.setFont(QFont("Segoe UI", 8))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                padding: 6px 10px;
            }
            QPushButton:hover {
                color: #f8fafc;
            }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

    def _load_printers(self):
        """Populates printer dropdown with available local and network printers."""
        self.printer_combo.clear()
        printers = PrinterService.get_available_printers()

        if printers:
            for p in printers:
                # Add friendly badge for Brother MFC or network laser printers
                display = f"🖨️ {p}"
                if "MFC" in p or "Brother" in p:
                    display += " (Color Laser)"
                self.printer_combo.addItem(display, p)
        else:
            self.printer_combo.addItem("No Printers Detected", None)

        self.printer_combo.addItem("⚙️ System Print Dialog...", "__dialog__")

        # Select default if found
        default_p = PrinterService.get_default_printer()
        if default_p:
            idx = self.printer_combo.findData(default_p)
            if idx >= 0:
                self.printer_combo.setCurrentIndex(idx)

    def _update_preview(self):
        """Renders HTML for active template and displays in paper preview browser."""
        template = get_template(self.current_template_id)
        rendered_html = template.render_html(self.note)
        self.preview_browser.setHtml(rendered_html)
        self.status_lbl.setText(f"Previewing: {template.name} • Ready to print or export.")

    def _on_template_changed(self, index: int):
        self.current_template_id = self.template_combo.currentData()
        self._update_preview()

    def _on_meta_toggle(self, checked: bool):
        self.meta_panel.setVisible(checked)

    def _on_meta_edited(self):
        """Updates ClinicalNote metadata in real-time when user edits top panel."""
        self.note.metadata.patient_name = self.pt_name_edit.text().strip()
        self.note.metadata.mrn = self.mrn_edit.text().strip()
        self.note.metadata.attending_physician = self.mrp_edit.text().strip()
        self.note.metadata.dictating_physician = self.dict_edit.text().strip()
        self._update_preview()

    def _on_print_clicked(self):
        """Prints note directly to selected printer or opens system print dialog."""
        selected_target = self.printer_combo.currentData()
        template = get_template(self.current_template_id)

        self.status_lbl.setText("Sending to printer...")
        self.print_btn.setEnabled(False)

        try:
            if selected_target == "__dialog__":
                success = PrinterService.print_document(
                    self.note,
                    template_id=self.current_template_id,
                    show_dialog=True,
                    parent_widget=self
                )
            else:
                success = PrinterService.print_document(
                    self.note,
                    template_id=self.current_template_id,
                    printer_name=selected_target,
                    show_dialog=False,
                    parent_widget=self
                )

            if success:
                printer_name = selected_target if selected_target != "__dialog__" else "selected printer"
                self.status_lbl.setText(f"✓ Document successfully sent to {printer_name}!")
            else:
                self.status_lbl.setText("⚠️ Printing cancelled or failed.")
        finally:
            self.print_btn.setEnabled(True)

    def _on_save_pdf_clicked(self):
        """Opens save file dialog and exports vector PDF."""
        mrn_str = self.note.metadata.mrn or "UnknownMRN"
        date_clean = self.note.metadata.date.replace(" ", "_").replace(",", "")
        default_name = f"{self.current_template_id}_{mrn_str}_{date_clean}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Note as Vector PDF",
            str(Path("outputs") / default_name),
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not file_path:
            return

        out_path = PdfGenerator.generate_pdf(self.note, self.current_template_id, file_path)
        self.status_lbl.setText(f"✓ Saved PDF: {Path(out_path).name}")

        # Provide option to open in system viewer
        try:
            subprocess.Popen(["xdg-open", out_path])
        except Exception:
            pass

    def _on_save_docx_clicked(self):
        """Opens save file dialog and exports Microsoft Word .docx."""
        mrn_str = self.note.metadata.mrn or "UnknownMRN"
        date_clean = self.note.metadata.date.replace(" ", "_").replace(",", "")
        default_name = f"{self.current_template_id}_{mrn_str}_{date_clean}.docx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Note as Microsoft Word (DOCX)",
            str(Path("outputs") / default_name),
            "Word Documents (*.docx);;All Files (*)"
        )
        if not file_path:
            return

        out_path = DocxGenerator.generate_docx(self.note, self.current_template_id, file_path)
        self.status_lbl.setText(f"✓ Saved DOCX: {Path(out_path).name}")

        try:
            subprocess.Popen(["xdg-open", out_path])
        except Exception:
            pass

    def _on_copy_html_clicked(self):
        """Copies rendered HTML directly to system clipboard for EMR pasting."""
        from PySide6.QtGui import QGuiApplication
        template = get_template(self.current_template_id)
        html_content = template.render_html(self.note)
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(html_content)
        self.status_lbl.setText("✓ Formatted HTML copied to clipboard!")
