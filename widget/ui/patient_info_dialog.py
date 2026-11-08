"""
Patient Information Dialog for Telephone Dictation
==================================================
Prompts the clinician for Patient Name, MRN, and Work Type (defaults to 001)
prior to hospital telephony dialing and DTMF submission.
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QCheckBox, QGraphicsDropShadowEffect, QWidget,
    QStyleOption, QStyle
)

from widget.setup_config import DictationSetupConfig


class PatientInfoDialog(QDialog):
    """
    Sleek dark-mode dialog requesting Patient Name, MRN, and Work Type
    before initiating telephone dictation and DTMF transmission.
    """

    def __init__(self, parent=None, config: Optional[DictationSetupConfig] = None):
        super().__init__(parent)
        self.config = config or DictationSetupConfig.load()

        self.setWindowTitle("Telephone Dictation Patient Details")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(480, 420)

        self._init_ui()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Container
        container = QWidget(self)
        container.setObjectName("dialogContainer")
        container.setStyleSheet("""
            #dialogContainer {
                background-color: #0b1120;
                border: 1.5px solid #1e293b;
                border-radius: 14px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(11)

        # Header Title
        title_box = QHBoxLayout()
        title_lbl = QLabel("📞 Hospital Telephony Submission", container)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #f8fafc;")
        title_box.addWidget(title_lbl)
        title_box.addStretch()

        dest_badge = QLabel(f"Line: {self.config.hospital_phone_number} • Site: {self.config.site_number}", container)
        dest_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        dest_badge.setStyleSheet("""
            background-color: #0c4a6e;
            color: #38bdf8;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        title_box.addWidget(dest_badge)
        layout.addLayout(title_box)

        desc_lbl = QLabel(
            "Enter patient identity and dictation work type. Patient name will be spelled out "
            "and MRN digits will be articulated individually for medical records.",
            container
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setFont(QFont("Segoe UI", 8))
        desc_lbl.setStyleSheet("color: #94a3b8; line-height: 1.3;")
        layout.addWidget(desc_lbl)

        # Patient Name Input
        name_lbl = QLabel("PATIENT NAME:", container)
        name_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #38bdf8;")
        layout.addWidget(name_lbl)

        self.name_edit = QLineEdit(container)
        self.name_edit.setPlaceholderText("e.g. Jane Doe")
        self.name_edit.setFont(QFont("Segoe UI", 10))
        self.name_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border: 1.5px solid #38bdf8;
            }
        """)
        layout.addWidget(self.name_edit)

        # MRN and Work Type in horizontal row
        row = QHBoxLayout()
        row.setSpacing(12)

        mrn_box = QVBoxLayout()
        mrn_lbl = QLabel("MEDICAL RECORD NUMBER (MRN):", container)
        mrn_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        mrn_lbl.setStyleSheet("color: #38bdf8;")
        mrn_box.addWidget(mrn_lbl)

        self.mrn_edit = QLineEdit(container)
        self.mrn_edit.setPlaceholderText("e.g. 1234567")
        self.mrn_edit.setFont(QFont("Segoe UI", 10))
        self.mrn_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border: 1.5px solid #38bdf8;
            }
        """)
        mrn_box.addWidget(self.mrn_edit)
        row.addLayout(mrn_box, stretch=2)

        wt_box = QVBoxLayout()
        wt_lbl = QLabel("WORK TYPE:", container)
        wt_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        wt_lbl.setStyleSheet("color: #38bdf8;")
        wt_box.addWidget(wt_lbl)

        self.wt_edit = QLineEdit(container)
        self.wt_edit.setText(self.config.work_type or "001")
        self.wt_edit.setPlaceholderText("001")
        self.wt_edit.setFont(QFont("Segoe UI", 10))
        self.wt_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border: 1.5px solid #38bdf8;
            }
        """)
        wt_box.addWidget(self.wt_edit)
        row.addLayout(wt_box, stretch=1)
        layout.addLayout(row)

        # Submission Channel row
        chan_row = QHBoxLayout()
        chan_lbl = QLabel("CHANNEL:", container)
        chan_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        chan_lbl.setStyleSheet("color: #38bdf8;")
        chan_row.addWidget(chan_lbl)

        self.channel_combo = QComboBox(container)
        self.channel_combo.addItem("📞 VoIP.ms SIP Trunk", "voip")
        bt_name = getattr(self.config, "bluetooth_device_name", "Pixel 7 Pro DK") or "Pixel 7 Pro DK"
        self.channel_combo.addItem(f"📱 Bluetooth Phone ({bt_name})", "bluetooth")
        self.channel_combo.setFont(QFont("Segoe UI", 8))
        self.channel_combo.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        idx = self.channel_combo.findData(getattr(self.config, "submission_channel", "voip"))
        if idx >= 0:
            self.channel_combo.setCurrentIndex(idx)
        chan_row.addWidget(self.channel_combo, stretch=1)
        layout.addLayout(chan_row)

        # Real-time listen checkbox
        self.listen_cb = QCheckBox("🎧 Listen to telephone dictation in real time", container)
        self.listen_cb.setFont(QFont("Segoe UI", 9))
        self.listen_cb.setStyleSheet("""
            QCheckBox {
                color: #e2e8f0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #475569;
                background-color: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)
        self.listen_cb.setChecked(self.config.listen_in_real_time)
        layout.addWidget(self.listen_cb)

        # Button Box
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("✕ Cancel", container)
        cancel_btn.setFont(QFont("Segoe UI", 9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.start_btn = QPushButton("📞 Dial & Dictate", container)
        self.start_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.start_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.start_btn)

        layout.addLayout(btn_layout)
        main_layout.addWidget(container)

    @property
    def patient_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def mrn(self) -> str:
        return self.mrn_edit.text().strip()

    @property
    def work_type(self) -> str:
        return self.wt_edit.text().strip() or "001"

    @property
    def listen_in_real_time(self) -> bool:
        return self.listen_cb.isChecked()

    @property
    def submission_channel(self) -> str:
        return self.channel_combo.currentData() or "voip"
