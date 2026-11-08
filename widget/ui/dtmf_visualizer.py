"""
DTMF Telephone Dialing Visualizer & Call Monitor
================================================
Visualizes real-time DTMF tones being pressed on an illuminated telephone keypad,
displays active call status and elapsed duration, shows live audio activity VU meters
for both parties, displays a real-time transcript and prompt event feed, and provides
a live 'Listen in Real Time' mute/unmute toggle.
"""

import time
from typing import Dict, Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPainter, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QCheckBox, QProgressBar, QTextEdit,
    QGraphicsDropShadowEffect, QStyleOption, QStyle
)


class KeypadButton(QPushButton):
    """Telephone keypad key that illuminates during DTMF tone transmission."""

    def __init__(self, char: str, subtext: str = "", parent=None):
        super().__init__(parent)
        self.char = char
        self.subtext = subtext
        self.setFixedSize(52, 44)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(0)

        self.char_lbl = QLabel(char, self)
        self.char_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.char_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(self.char_lbl)

        if subtext:
            self.sub_lbl = QLabel(subtext, self)
            self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sub_lbl.setFont(QFont("Segoe UI", 6, QFont.Weight.DemiBold))
            layout.addWidget(self.sub_lbl)
        else:
            layout.addStretch()

        self.set_active(False)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    border: 2px solid #38bdf8;
                    border-radius: 9px;
                }
            """)
            self.char_lbl.setStyleSheet("color: #ffffff;")
            if hasattr(self, "sub_lbl"):
                self.sub_lbl.setStyleSheet("color: #bae6fd;")
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 9px;
                }
            """)
            self.char_lbl.setStyleSheet("color: #f8fafc;")
            if hasattr(self, "sub_lbl"):
                self.sub_lbl.setStyleSheet("color: #64748b;")


class DTMFVisualizerWidget(QWidget):
    """
    Floating real-time DTMF keypad visualizer, call monitor, and transcript viewer.
    """

    stop_requested = Signal()
    listen_toggled = Signal(bool)

    KEYPAD_LAYOUT = [
        [('1', ''), ('2', 'ABC'), ('3', 'DEF')],
        [('4', 'GHI'), ('5', 'JKL'), ('6', 'MNO')],
        [('7', 'PQRS'), ('8', 'TUV'), ('9', 'WXYZ')],
        [('*', ''), ('0', '+'), ('#', '')],
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons: Dict[str, KeypadButton] = {}
        self.drag_pos = QPoint()
        self.start_time = 0.0

        # Call elapsed timer
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._update_call_timer)

        # Tone turn-off timer
        self._tone_off_timer = QTimer(self)
        self._tone_off_timer.setSingleShot(True)
        self._tone_off_timer.timeout.connect(self._reset_keypad_highlights)
        self._active_key: Optional[str] = None

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(340, 580)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Container
        self.container = QWidget(self)
        self.container.setObjectName("visContainer")
        self.container.setStyleSheet("""
            #visContainer {
                background-color: #0b1120;
                border: 1.5px solid #1e293b;
                border-radius: 14px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header Bar
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel("📞 Telephony Call Monitor", self.container)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #f8fafc;")
        header.addWidget(title_lbl)

        header.addStretch()

        close_btn = QPushButton("✕", self.container)
        close_btn.setFixedSize(20, 20)
        close_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Call Status & Timer Badge
        self.status_box = QWidget(self.container)
        self.status_box.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 3px;
        """)
        sb_layout = QHBoxLayout(self.status_box)
        sb_layout.setContentsMargins(8, 4, 8, 4)

        status_vbox = QVBoxLayout()
        status_vbox.setSpacing(1)
        self.call_status_lbl = QLabel("Ready to connect", self.status_box)
        self.call_status_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.call_status_lbl.setStyleSheet("color: #38bdf8;")
        status_vbox.addWidget(self.call_status_lbl)

        self.channel_badge = QLabel("SIP: VoIP.ms", self.status_box)
        self.channel_badge.setFont(QFont("Segoe UI", 7))
        self.channel_badge.setStyleSheet("color: #64748b;")
        status_vbox.addWidget(self.channel_badge)
        sb_layout.addLayout(status_vbox, stretch=1)

        self.timer_lbl = QLabel("00:00", self.status_box)
        self.timer_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.timer_lbl.setStyleSheet("color: #94a3b8;")
        sb_layout.addWidget(self.timer_lbl)
        layout.addWidget(self.status_box)

        # Dialed Digits Tape
        tape_box = QWidget(self.container)
        tape_box.setStyleSheet("""
            background-color: #030712;
            border: 1px solid #334155;
            border-radius: 7px;
        """)
        tb_layout = QHBoxLayout(tape_box)
        tb_layout.setContentsMargins(8, 4, 8, 4)

        tape_title = QLabel("DTMF:", tape_box)
        tape_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        tape_title.setStyleSheet("color: #64748b;")
        tb_layout.addWidget(tape_title)

        self.digits_tape = QLabel("---", tape_box)
        self.digits_tape.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.digits_tape.setStyleSheet("color: #38bdf8; letter-spacing: 2px;")
        tb_layout.addWidget(self.digits_tape)
        tb_layout.addStretch()
        layout.addWidget(tape_box)

        # 4x3 Keypad Grid
        grid_widget = QWidget(self.container)
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setSpacing(6)

        for row_idx, row in enumerate(self.KEYPAD_LAYOUT):
            for col_idx, (char, sub) in enumerate(row):
                btn = KeypadButton(char, sub, grid_widget)
                self.buttons[char] = btn
                grid.addWidget(btn, row_idx, col_idx)

        layout.addWidget(grid_widget)

        # Live Transcript & Prompt Event Feed
        trans_title = QLabel("📝 LIVE CALL TRANSCRIPT & PROMPTS:", self.container)
        trans_title.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        trans_title.setStyleSheet("color: #64748b; margin-top: 2px;")
        layout.addWidget(trans_title)

        self.transcript_view = QTextEdit(self.container)
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setFixedHeight(120)
        self.transcript_view.setFont(QFont("Segoe UI", 8))
        self.transcript_view.setStyleSheet("""
            QTextEdit {
                background-color: #030712;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 7px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.transcript_view)

        # Audio VU Level Meter
        vu_box = QHBoxLayout()
        vu_box.setSpacing(6)

        rem_lbl = QLabel("Remote:", self.container)
        rem_lbl.setFont(QFont("Segoe UI", 7))
        rem_lbl.setStyleSheet("color: #94a3b8;")
        vu_box.addWidget(rem_lbl)

        self.rem_vu = QProgressBar(self.container)
        self.rem_vu.setRange(0, 100)
        self.rem_vu.setValue(0)
        self.rem_vu.setTextVisible(False)
        self.rem_vu.setFixedHeight(5)
        self.rem_vu.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 2px;
            }
        """)
        vu_box.addWidget(self.rem_vu)

        out_lbl = QLabel("Outbound:", self.container)
        out_lbl.setFont(QFont("Segoe UI", 7))
        out_lbl.setStyleSheet("color: #94a3b8;")
        vu_box.addWidget(out_lbl)

        self.out_vu = QProgressBar(self.container)
        self.out_vu.setRange(0, 100)
        self.out_vu.setValue(0)
        self.out_vu.setTextVisible(False)
        self.out_vu.setFixedHeight(5)
        self.out_vu.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 2px;
            }
        """)
        vu_box.addWidget(self.out_vu)
        layout.addLayout(vu_box)

        # Bottom Bar: Listen toggle & Hangup
        bot_bar = QHBoxLayout()
        self.listen_cb = QCheckBox("🎧 Listen in real time", self.container)
        self.listen_cb.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.listen_cb.setStyleSheet("""
            QCheckBox {
                color: #e2e8f0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #475569;
                background-color: #1e293b;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)
        self.listen_cb.setChecked(True)
        self.listen_cb.toggled.connect(self._on_listen_toggled)
        bot_bar.addWidget(self.listen_cb)
        bot_bar.addStretch()

        self.stop_btn = QPushButton("⏹ End Call", self.container)
        self.stop_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border-radius: 6px;
                padding: 4px 10px;
                border: none;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        bot_bar.addWidget(self.stop_btn)
        layout.addLayout(bot_bar)

        main_layout.addWidget(self.container)

    def closeEvent(self, event):
        self.timer.stop()
        self._tone_off_timer.stop()
        super().closeEvent(event)

    def start_call(self, initial_status: str = "Connecting...", channel: str = "VoIP.ms"):
        """Resets and activates visualizer for a new call."""
        self.digits_tape.setText("")
        self.call_status_lbl.setText(initial_status)
        self.channel_badge.setText(f"Channel: {channel}")
        self.transcript_view.clear()
        self.rem_vu.setValue(0)
        self.out_vu.setValue(0)
        self.start_time = time.time()
        self.timer_lbl.setText("00:00")
        self.timer.start()
        self._reset_keypad_highlights()
        self.show()

    def update_status(self, text: str):
        """Updates call status message."""
        self.call_status_lbl.setText(text)

    @Slot(str, str)
    def append_transcript(self, speaker: str, text: str):
        """Appends a timestamped line to the live call transcript feed."""
        if not text:
            return
        elapsed = int(time.time() - self.start_time) if self.start_time > 0 else 0
        timestamp = f"[{elapsed // 60:02d}:{elapsed % 60:02d}]"

        color_map = {
            "System": "#94a3b8",
            "Outbound": "#38bdf8",
            "Outbound DTMF": "#f59e0b",
            "Outbound Dictation": "#10b981",
            "Hospital Line": "#a855f7",
            "Remote Line": "#a855f7",
        }
        color = color_map.get(speaker, "#e2e8f0")

        html_line = f"<span style='color: #64748b;'>{timestamp}</span> " \
                    f"<strong style='color: {color};'>[{speaker}]</strong> " \
                    f"<span style='color: #f8fafc;'>{text}</span><br>"
        self.transcript_view.append(html_line)
        self.transcript_view.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(str, float)
    def update_audio_activity(self, source: str, level: float):
        """Updates VU meter levels for remote or outbound speech."""
        val = int(min(1.0, max(0.0, level)) * 100)
        if source == "remote":
            self.rem_vu.setValue(val)
        elif source == "outbound":
            self.out_vu.setValue(val)

    @Slot(str, int)
    def highlight_dtmf(self, char: str, duration_ms: int = 140):
        """Highlights a specific keypad key and appends to digits tape."""
        char = str(char).strip().upper()
        if not char:
            return

        current = self.digits_tape.text()
        if current == "---":
            current = ""
        self.digits_tape.setText(f"{current} {char}".strip())

        self._reset_keypad_highlights()
        if char in self.buttons:
            self.buttons[char].set_active(True)
            self._active_key = char
            self._tone_off_timer.start(max(80, duration_ms))

    def _reset_keypad_highlights(self):
        if self._active_key and self._active_key in self.buttons:
            self.buttons[self._active_key].set_active(False)
            self._active_key = None

    def end_call(self, summary: str = "Call Completed"):
        """Stops timer and updates status."""
        self.timer.stop()
        self.call_status_lbl.setText(summary)
        self.rem_vu.setValue(0)
        self.out_vu.setValue(0)
        self._reset_keypad_highlights()

    def _update_call_timer(self):
        if self.start_time > 0:
            elapsed = int(time.time() - self.start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            self.timer_lbl.setText(f"{mins:02d}:{secs:02d}")

    def _on_listen_toggled(self, checked: bool):
        self.listen_toggled.emit(checked)

    def _on_stop_clicked(self):
        self.stop_requested.emit()
        self.end_call("Call Terminated by User")
