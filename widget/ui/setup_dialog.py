"""
Dictation & Telephony Setup Dialog
==================================
Allows the clinician to view and modify settings stored in 'setup.yaml':
- Introduction & Outro
- Hospital Dictation Line (1-800 number, Provider ID, Site Number, Work Type)
- VoIP.ms SIP Trunking Credentials
- Standardized Call Flow Template Sequence
- Audio export and monitoring preferences
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QCheckBox, QComboBox, QDoubleSpinBox,
    QGraphicsDropShadowEffect, QWidget, QStyleOption, QStyle, QScrollArea,
    QFrame
)

from widget.setup_config import DictationSetupConfig


class SetupConfigDialog(QDialog):
    """
    Sleek dark-mode dialog for configuring dictation credentials, hospital line parameters,
    voip.ms SIP account, and call flow templates.
    """

    def __init__(self, parent=None, config: Optional[DictationSetupConfig] = None):
        super().__init__(parent)
        self.config = config or DictationSetupConfig.load()

        self.setWindowTitle("Dictation & Telephony Setup")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(560, 660)

        self._init_ui()
        self._load_values()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        container.setObjectName("setupContainer")
        container.setStyleSheet("""
            #setupContainer {
                background-color: #0b1120;
                border: 1.5px solid #1e293b;
                border-radius: 14px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(10)

        # Header Title
        title_box = QHBoxLayout()
        title_lbl = QLabel("⚙️ Dictation & Telephony Settings", container)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #f8fafc;")
        title_box.addWidget(title_lbl)
        title_box.addStretch()

        close_btn = QPushButton("✕", container)
        close_btn.setFixedSize(22, 22)
        close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                border-radius: 11px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.reject)
        title_box.addWidget(close_btn)
        layout.addLayout(title_box)

        sub_lbl = QLabel("Stored in setup.yaml • Hospital line, DTMF call flow template, and VoIP.ms SIP credentials.", container)
        sub_lbl.setFont(QFont("Segoe UI", 8))
        sub_lbl.setStyleSheet("color: #94a3b8;")
        layout.addWidget(sub_lbl)

        # Scrollable form area
        scroll = QScrollArea(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 4, 6, 4)
        form_layout.setSpacing(10)

        # SECTION 1: Hospital Dictation Line
        sec1_lbl = QLabel("HOSPITAL TELEPHONY & LINE IDENTITY", form_widget)
        sec1_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sec1_lbl.setStyleSheet("color: #38bdf8; border-bottom: 1px solid #1e293b; padding-bottom: 3px;")
        form_layout.addWidget(sec1_lbl)

        hosp_row = QHBoxLayout()
        phone_box = QVBoxLayout()
        phone_lbl = QLabel("HOSPITAL PHONE (1-800):", form_widget)
        phone_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        phone_lbl.setStyleSheet("color: #94a3b8;")
        phone_box.addWidget(phone_lbl)
        self.phone_edit = QLineEdit(form_widget)
        self.phone_edit.setPlaceholderText("18005551234")
        self.phone_edit.setStyleSheet(self._input_style())
        phone_box.addWidget(self.phone_edit)
        hosp_row.addLayout(phone_box, stretch=2)

        site_box = QVBoxLayout()
        site_lbl = QLabel("SITE NUMBER (#):", form_widget)
        site_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        site_lbl.setStyleSheet("color: #94a3b8;")
        site_box.addWidget(site_lbl)
        self.site_edit = QLineEdit(form_widget)
        self.site_edit.setPlaceholderText("01")
        self.site_edit.setStyleSheet(self._input_style())
        site_box.addWidget(self.site_edit)
        hosp_row.addLayout(site_box, stretch=1)
        form_layout.addLayout(hosp_row)

        prov_row = QHBoxLayout()
        prov_box = QVBoxLayout()
        prov_lbl = QLabel("PROVIDER NUMBER (#):", form_widget)
        prov_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        prov_lbl.setStyleSheet("color: #94a3b8;")
        prov_box.addWidget(prov_lbl)
        self.prov_edit = QLineEdit(form_widget)
        self.prov_edit.setPlaceholderText("6740")
        self.prov_edit.setStyleSheet(self._input_style())
        prov_box.addWidget(self.prov_edit)
        prov_row.addLayout(prov_box, stretch=1)

        wt_box = QVBoxLayout()
        wt_lbl = QLabel("DEFAULT WORK TYPE (#):", form_widget)
        wt_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        wt_lbl.setStyleSheet("color: #94a3b8;")
        wt_box.addWidget(wt_lbl)
        self.wt_edit = QLineEdit(form_widget)
        self.wt_edit.setPlaceholderText("001")
        self.wt_edit.setStyleSheet(self._input_style())
        wt_box.addWidget(self.wt_edit)
        prov_row.addLayout(wt_box, stretch=1)
        form_layout.addLayout(prov_row)

        # SECTION 2: Call Flow Template
        sec2_lbl = QLabel("CALL FLOW SEQUENCE TEMPLATE", form_widget)
        sec2_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sec2_lbl.setStyleSheet("color: #38bdf8; border-bottom: 1px solid #1e293b; padding-bottom: 3px; margin-top: 6px;")
        form_layout.addWidget(sec2_lbl)

        template_help = QLabel("Standardized variables: {{hospital_phone_number}}, {{provider_number}}#, {{site_number}}#, {{work_type}}#, {{patient_mrn}}#", form_widget)
        template_help.setFont(QFont("Segoe UI", 7))
        template_help.setStyleSheet("color: #64748b;")
        form_layout.addWidget(template_help)

        self.seq_edit = QTextEdit(form_widget)
        self.seq_edit.setFixedHeight(50)
        self.seq_edit.setFont(QFont("Segoe UI", 8))
        self.seq_edit.setStyleSheet(self._input_style())
        form_layout.addWidget(self.seq_edit)

        # SECTION 3: VoIP.ms SIP Trunking
        sec3_lbl = QLabel("VOIP.MS SIP TRUNKING CREDENTIALS", form_widget)
        sec3_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sec3_lbl.setStyleSheet("color: #38bdf8; border-bottom: 1px solid #1e293b; padding-bottom: 3px; margin-top: 6px;")
        form_layout.addWidget(sec3_lbl)

        voip_row1 = QHBoxLayout()
        vserver_box = QVBoxLayout()
        vserver_lbl = QLabel("SIP SERVER:", form_widget)
        vserver_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        vserver_lbl.setStyleSheet("color: #94a3b8;")
        vserver_box.addWidget(vserver_lbl)
        self.voip_server_edit = QLineEdit(form_widget)
        self.voip_server_edit.setPlaceholderText("toronto.voip.ms")
        self.voip_server_edit.setStyleSheet(self._input_style())
        vserver_box.addWidget(self.voip_server_edit)
        voip_row1.addLayout(vserver_box, stretch=2)

        vport_box = QVBoxLayout()
        vport_lbl = QLabel("PORT:", form_widget)
        vport_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        vport_lbl.setStyleSheet("color: #94a3b8;")
        vport_box.addWidget(vport_lbl)
        self.voip_port_edit = QLineEdit(form_widget)
        self.voip_port_edit.setText("5060")
        self.voip_port_edit.setStyleSheet(self._input_style())
        vport_box.addWidget(self.voip_port_edit)
        voip_row1.addLayout(vport_box, stretch=1)
        form_layout.addLayout(voip_row1)

        voip_row2 = QHBoxLayout()
        vuser_box = QVBoxLayout()
        vuser_lbl = QLabel("SIP USERNAME / SUBACCOUNT:", form_widget)
        vuser_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        vuser_lbl.setStyleSheet("color: #94a3b8;")
        vuser_box.addWidget(vuser_lbl)
        self.voip_user_edit = QLineEdit(form_widget)
        self.voip_user_edit.setPlaceholderText("e.g. 123456_dictation")
        self.voip_user_edit.setStyleSheet(self._input_style())
        vuser_box.addWidget(self.voip_user_edit)
        voip_row2.addLayout(vuser_box)

        vpass_box = QVBoxLayout()
        vpass_lbl = QLabel("SIP PASSWORD:", form_widget)
        vpass_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        vpass_lbl.setStyleSheet("color: #94a3b8;")
        vpass_box.addWidget(vpass_lbl)
        self.voip_pass_edit = QLineEdit(form_widget)
        self.voip_pass_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.voip_pass_edit.setPlaceholderText("••••••••")
        self.voip_pass_edit.setStyleSheet(self._input_style())
        vpass_box.addWidget(self.voip_pass_edit)
        voip_row2.addLayout(vpass_box)
        form_layout.addLayout(voip_row2)

        # SECTION 3B: Submission Channel & Bluetooth Gateway
        sec3b_lbl = QLabel("TELEPHONY CHANNEL & BLUETOOTH GATEWAY", form_widget)
        sec3b_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sec3b_lbl.setStyleSheet("color: #38bdf8; border-bottom: 1px solid #1e293b; padding-bottom: 3px; margin-top: 6px;")
        form_layout.addWidget(sec3b_lbl)

        chan_box = QVBoxLayout()
        chan_lbl = QLabel("DEFAULT SUBMISSION CHANNEL:", form_widget)
        chan_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        chan_lbl.setStyleSheet("color: #94a3b8;")
        chan_box.addWidget(chan_lbl)

        self.sub_chan_combo = QComboBox(form_widget)
        self.sub_chan_combo.addItem("📞 VoIP.ms SIP Trunk", "voip")
        self.sub_chan_combo.addItem("📱 Bluetooth Mobile Phone Gateway", "bluetooth")
        self.sub_chan_combo.setStyleSheet(self._input_style())
        chan_box.addWidget(self.sub_chan_combo)
        form_layout.addLayout(chan_box)

        bt_row = QHBoxLayout()
        bt_name_box = QVBoxLayout()
        bt_name_lbl = QLabel("BLUETOOTH DEVICE NAME:", form_widget)
        bt_name_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        bt_name_lbl.setStyleSheet("color: #94a3b8;")
        bt_name_box.addWidget(bt_name_lbl)
        self.bt_name_edit = QLineEdit(form_widget)
        self.bt_name_edit.setPlaceholderText("Pixel 7 Pro DK")
        self.bt_name_edit.setStyleSheet(self._input_style())
        bt_name_box.addWidget(self.bt_name_edit)
        bt_row.addLayout(bt_name_box, stretch=2)

        bt_mac_box = QVBoxLayout()
        bt_mac_lbl = QLabel("DEVICE MAC:", form_widget)
        bt_mac_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        bt_mac_lbl.setStyleSheet("color: #94a3b8;")
        bt_mac_box.addWidget(bt_mac_lbl)
        self.bt_mac_edit = QLineEdit(form_widget)
        self.bt_mac_edit.setPlaceholderText("D4:3A:2C:A5:93:9D")
        self.bt_mac_edit.setStyleSheet(self._input_style())
        bt_mac_box.addWidget(self.bt_mac_edit)
        bt_row.addLayout(bt_mac_box, stretch=1)
        form_layout.addLayout(bt_row)

        # SECTION 4: Clinician Introduction & Outro
        sec4_lbl = QLabel("CLINICIAN PREAMBLE & OUTRO", form_widget)
        sec4_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sec4_lbl.setStyleSheet("color: #38bdf8; border-bottom: 1px solid #1e293b; padding-bottom: 3px; margin-top: 6px;")
        form_layout.addWidget(sec4_lbl)

        intro_lbl = QLabel("INTRODUCTION:", form_widget)
        intro_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        intro_lbl.setStyleSheet("color: #94a3b8;")
        form_layout.addWidget(intro_lbl)
        self.intro_edit = QTextEdit(form_widget)
        self.intro_edit.setFixedHeight(50)
        self.intro_edit.setFont(QFont("Segoe UI", 8))
        self.intro_edit.setStyleSheet(self._input_style())
        form_layout.addWidget(self.intro_edit)

        outro_lbl = QLabel("OUTRO:", form_widget)
        outro_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        outro_lbl.setStyleSheet("color: #94a3b8;")
        form_layout.addWidget(outro_lbl)
        self.outro_edit = QLineEdit(form_widget)
        self.outro_edit.setFont(QFont("Segoe UI", 8))
        self.outro_edit.setStyleSheet(self._input_style())
        form_layout.addWidget(self.outro_edit)

        # Preferences Row
        pref_row = QHBoxLayout()
        opt_box = QVBoxLayout()
        opt_lbl = QLabel("DEFAULT OUTPUT:", form_widget)
        opt_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        opt_lbl.setStyleSheet("color: #94a3b8;")
        opt_box.addWidget(opt_lbl)
        self.output_combo = QComboBox(form_widget)
        self.output_combo.addItem("📞 Telephone Dial", "dial")
        self.output_combo.addItem("🎵 MP3 File", "mp3")
        self.output_combo.setStyleSheet(self._input_style())
        opt_box.addWidget(self.output_combo)
        pref_row.addLayout(opt_box)

        spd_box = QVBoxLayout()
        spd_lbl = QLabel("DICTATION SPEED:", form_widget)
        spd_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        spd_lbl.setStyleSheet("color: #94a3b8;")
        spd_box.addWidget(spd_lbl)
        self.speed_spin = QDoubleSpinBox(form_widget)
        self.speed_spin.setRange(0.8, 2.0)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setValue(1.18)
        self.speed_spin.setStyleSheet(self._input_style())
        spd_box.addWidget(self.speed_spin)
        pref_row.addLayout(spd_box)
        form_layout.addLayout(pref_row)

        self.listen_cb = QCheckBox("🎧 Listen to telephone dictation in real time by default", form_widget)
        self.listen_cb.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.listen_cb.setStyleSheet("""
            QCheckBox { color: #e2e8f0; spacing: 8px; }
            QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #475569; background-color: #1e293b; }
            QCheckBox::indicator:checked { background-color: #0284c7; border-color: #38bdf8; }
        """)
        form_layout.addWidget(self.listen_cb)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        cancel_btn = QPushButton("Cancel", container)
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
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Save Settings", container)
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
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
        save_btn.clicked.connect(self._save_values)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)
        main_layout.addWidget(container)

    def _input_style(self) -> str:
        return """
            background-color: #0f172a;
            color: #f8fafc;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 5px 8px;
        """

    def _load_values(self):
        self.phone_edit.setText(self.config.hospital_phone_number or "")
        self.site_edit.setText(self.config.site_number or "")
        self.prov_edit.setText(self.config.provider_number or "")
        self.wt_edit.setText(self.config.work_type or "001")
        self.seq_edit.setPlainText(self.config.call_sequence_summary or "")
        self.voip_server_edit.setText(self.config.voip_server or "toronto.voip.ms")
        self.voip_port_edit.setText(str(self.config.voip_port or 5060))
        self.voip_user_edit.setText(self.config.voip_username or "")
        self.voip_pass_edit.setText(self.config.voip_password or "")
        self.intro_edit.setPlainText(self.config.introduction or "")
        self.outro_edit.setText(self.config.outro or "")
        self.listen_cb.setChecked(self.config.listen_in_real_time)
        self.speed_spin.setValue(self.config.tts_speed or 1.18)

        idx = self.output_combo.findData(self.config.default_output_option)
        if idx >= 0:
            self.output_combo.setCurrentIndex(idx)

        chan_idx = self.sub_chan_combo.findData(getattr(self.config, "submission_channel", "voip"))
        if chan_idx >= 0:
            self.sub_chan_combo.setCurrentIndex(chan_idx)

        self.bt_name_edit.setText(getattr(self.config, "bluetooth_device_name", "Pixel 7 Pro DK") or "")
        self.bt_mac_edit.setText(getattr(self.config, "bluetooth_device_mac", "D4:3A:2C:A5:93:9D") or "")

    def _save_values(self):
        self.config.hospital_phone_number = self.phone_edit.text().strip()
        self.config.site_number = self.site_edit.text().strip()
        self.config.provider_number = self.prov_edit.text().strip()
        self.config.work_type = self.wt_edit.text().strip() or "001"
        self.config.call_sequence_summary = self.seq_edit.toPlainText().strip()
        self.config.voip_server = self.voip_server_edit.text().strip()
        try:
            self.config.voip_port = int(self.voip_port_edit.text().strip() or "5060")
        except ValueError:
            self.config.voip_port = 5060
        self.config.voip_username = self.voip_user_edit.text().strip()
        self.config.voip_password = self.voip_pass_edit.text().strip()
        self.config.introduction = self.intro_edit.toPlainText().strip()
        self.config.outro = self.outro_edit.text().strip()
        self.config.default_output_option = self.output_combo.currentData()
        self.config.submission_channel = self.sub_chan_combo.currentData() or "voip"
        self.config.bluetooth_device_name = self.bt_name_edit.text().strip()
        self.config.bluetooth_device_mac = self.bt_mac_edit.text().strip()
        self.config.listen_in_real_time = self.listen_cb.isChecked()
        self.config.tts_speed = float(self.speed_spin.value())

        self.config.save()
        self.accept()
