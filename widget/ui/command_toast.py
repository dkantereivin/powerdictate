"""
Transient 3-Second Command Toast Widget
======================================
Displays a glowing visual badge beside the floating pill toolbar
when a voice command is triggered, with an animated 3.0s countdown bar.
"""

import time
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QGraphicsDropShadowEffect, QStyleOption, QStyle
)


class CommandToastWidget(QWidget):
    """
    Sleek 3.0-second visual command notification badge.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration_secs = 3.0
        self.start_time = 0.0

        # Animation timer (30fps)
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(33)
        self.anim_timer.timeout.connect(self._update_progress)

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resize(230, 54)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Container Frame
        self.container = QWidget(self)
        self.container.setObjectName("toastContainer")
        self.container.setStyleSheet("""
            #toastContainer {
                background-color: #0f172a;
                border: 1.5px solid #0284c7;
                border-radius: 18px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(2, 132, 199, 140))  # Glowing cyan shadow
        shadow.setOffset(0, 2)
        self.container.setGraphicsEffect(shadow)

        box_layout = QVBoxLayout(self.container)
        box_layout.setContentsMargins(10, 6, 10, 6)
        box_layout.setSpacing(4)

        # Top line: ⚡ COMMAND: [Name] [Hotkey]
        top_line = QWidget(self.container)
        top_layout = QHBoxLayout(top_line)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        self.cmd_lbl = QLabel("⚡ Next Field", top_line)
        self.cmd_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.cmd_lbl.setStyleSheet("color: #38bdf8;")
        top_layout.addWidget(self.cmd_lbl)

        top_layout.addStretch()

        self.hotkey_badge = QLabel("Tab", top_line)
        self.hotkey_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.hotkey_badge.setStyleSheet("""
            background-color: #0369a1;
            color: #f8fafc;
            border-radius: 4px;
            padding: 1px 5px;
        """)
        top_layout.addWidget(self.hotkey_badge)

        box_layout.addWidget(top_line)

        # Bottom line: Animated 3-second progress bar
        self.progress_bar = QProgressBar(self.container)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 1.5px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 1.5px;
            }
        """)
        box_layout.addWidget(self.progress_bar)

        layout.addWidget(self.container)

    def show_command(self, command_name: str, hotkey: str, pill_geo):
        """Displays toast next to the pill toolbar for 3.0 seconds."""
        self.cmd_lbl.setText(f"⚡ {command_name}")
        self.hotkey_badge.setText(hotkey)

        # Position to the left of the floating pill
        toast_x = max(20, pill_geo.x() - self.width() - 8)
        toast_y = pill_geo.y()
        self.move(toast_x, toast_y)

        self.start_time = time.time()
        self.progress_bar.setValue(1000)
        self.show()
        self.anim_timer.start()

    def _update_progress(self):
        elapsed = time.time() - self.start_time
        remaining = max(0.0, self.duration_secs - elapsed)
        progress = int((remaining / self.duration_secs) * 1000.0)

        self.progress_bar.setValue(progress)

        if elapsed >= self.duration_secs:
            self.anim_timer.stop()
            self.hide()
