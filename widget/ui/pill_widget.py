"""
PySide6 Floating Pill Companion Widget (Phase 3 with Command Interception)
==========================================================================
Frameless, translucent floating toolbar supporting dynamic dictation target
switching, Dragon Dictation Box, and 3-second visual command toasts.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Slot
from PySide6.QtGui import QFont, QColor, QAction, QKeyEvent, QPainter, QActionGroup, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QMenu, QGraphicsDropShadowEffect, QStyleOption, QStyle
)

from widget.config import WidgetConfig
from widget.controller import DictationController, DictationState
from widget.audio.hotkey import GlobalHotkeyManager
from widget.stt import AVAILABLE_MODELS
from widget.ui.dictation_box import DictationBoxWidget
from widget.ui.command_toast import CommandToastWidget


class FloatingPillWidget(QWidget):
    """
    Sleek, permanently always-on-top floating pill companion toolbar.
    """

    def __init__(self, config: Optional[WidgetConfig] = None):
        super().__init__()
        self.config = config or WidgetConfig.load()
        self.controller = DictationController(self.config)

        # Dictation Box Widget
        self.dictation_box = DictationBoxWidget()
        self.dictation_box.hide()  # Default closed -> Dictates to active cursor

        # 3-Second Command Toast Widget
        self.toast = CommandToastWidget()
        self.toast.hide()

        # Ensure target matches initial box state
        self.config.dictation_target = "box" if self.dictation_box.isVisible() else "cursor"

        # Drag state
        self.drag_position = QPoint()

        # Recording timer for live duration display
        self.rec_timer = QTimer(self)
        self.rec_timer.setInterval(200)
        self.rec_timer.timeout.connect(self._update_recording_duration)

        self._init_window_flags()
        self._init_ui()
        self._connect_controller_signals()
        self._init_hotkeys()
        self._init_local_shortcuts()

    def _init_window_flags(self):
        # Frameless, Always on Top, Standalone Window with X11 stacking support
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Position at top-right corner of screen
        screen = QApplication.primaryScreen().geometry()
        pill_width = 345
        pill_height = 54
        x = max(20, screen.width() - pill_width - 30)
        y = 35
        self.setGeometry(x, y, pill_width, pill_height)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)

        # Main Container Pill Frame
        self.container = QWidget(self)
        self.container.setObjectName("pillContainer")
        self.container.setStyleSheet("""
            #pillContainer {
                background-color: #0f172a;
                border: 1.5px solid #334155;
                border-radius: 22px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 3)
        self.container.setGraphicsEffect(shadow)

        pill_layout = QHBoxLayout(self.container)
        pill_layout.setContentsMargins(10, 4, 8, 4)
        pill_layout.setSpacing(7)

        # Drag Handle Grip
        self.drag_handle = QLabel("⠿", self.container)
        self.drag_handle.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.drag_handle.setStyleSheet("color: #64748b; padding-right: 2px;")
        self.drag_handle.setCursor(Qt.CursorShape.SizeAllCursor)
        pill_layout.addWidget(self.drag_handle)

        # Microphone Button
        self.mic_btn = QPushButton("🎙️ MIC", self.container)
        self.mic_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.mic_btn.setFixedHeight(34)
        self.mic_btn.setStyleSheet(self._get_mic_btn_style(False))
        self.mic_btn.clicked.connect(self._on_mic_btn_clicked)
        self.mic_btn.pressed.connect(self._on_mic_btn_pressed)
        self.mic_btn.released.connect(self._on_mic_btn_released)
        pill_layout.addWidget(self.mic_btn)

        # Dictation Box Compact Icon Button (📝)
        self.box_toggle_btn = QPushButton("📝", self.container)
        self.box_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.box_toggle_btn.setToolTip("Toggle Dictation Box (Ctrl+D)")
        self.box_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.box_toggle_btn.setFont(QFont("Segoe UI", 11))
        self.box_toggle_btn.setFixedSize(30, 30)
        self.box_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: white;
            }
        """)
        self.box_toggle_btn.clicked.connect(self.toggle_dictation_box)
        pill_layout.addWidget(self.box_toggle_btn)

        # Hotkey Display Badge
        self.hotkey_badge = QLabel(self._get_hotkey_display(), self.container)
        self.hotkey_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.hotkey_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 5px;
            padding: 2px 6px;
        """)
        pill_layout.addWidget(self.hotkey_badge)

        # Status Label & VU Meter Box
        center_box = QWidget(self.container)
        center_layout = QHBoxLayout(center_box)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        self.status_lbl = QLabel("Ready", center_box)
        self.status_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.status_lbl.setStyleSheet("color: #94a3b8;")
        center_layout.addWidget(self.status_lbl)

        self.vu_bar = QProgressBar(center_box)
        self.vu_bar.setRange(0, 100)
        self.vu_bar.setValue(0)
        self.vu_bar.setTextVisible(False)
        self.vu_bar.setFixedHeight(6)
        self.vu_bar.setFixedWidth(38)
        self.vu_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:0.65 #f59e0b, stop:1 #ef4444);
                border-radius: 3px;
            }
        """)
        center_layout.addWidget(self.vu_bar)
        pill_layout.addWidget(center_box)

        # Side Dropdown Menu Button (⋮)
        self.menu_btn = QPushButton("⋮", self.container)
        self.menu_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.menu_btn.setFixedSize(28, 28)
        self.menu_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        self.menu_btn.clicked.connect(self.show_dropdown_menu)
        pill_layout.addWidget(self.menu_btn)

        layout.addWidget(self.container)

    def _init_local_shortcuts(self):
        """Initializes in-app keyboard shortcuts."""
        box_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        box_shortcut.activated.connect(self.toggle_dictation_box)

    def _on_mic_btn_clicked(self):
        if self.config.hotkey_mode == "toggle":
            self.controller.toggle()

    def _on_mic_btn_pressed(self):
        if self.config.hotkey_mode == "ptt":
            self.controller.ptt_press()

    def _on_mic_btn_released(self):
        if self.config.hotkey_mode == "ptt":
            self.controller.ptt_release()

    def _connect_controller_signals(self):
        """Connects controller signals to UI updates."""
        self.controller.state_changed.connect(self._on_state_changed)
        self.controller.vu_meter_updated.connect(self._on_vu_meter_updated)
        self.controller.recording_saved.connect(self._on_recording_saved)
        self.controller.transcription_received.connect(self._on_transcription_received)
        self.controller.command_recognized.connect(self._on_command_recognized)
        self.controller.execute_command_requested.connect(self._on_execute_command_requested)
        self.controller.model_switched.connect(self._on_model_switched)

    def _init_hotkeys(self):
        """Initializes hardware keyboard hotkey listener."""
        self.hotkey_mgr = GlobalHotkeyManager(
            hotkey_name=self.config.hotkey,
            hotkey_mode=self.config.hotkey_mode,
            on_toggle=self.controller.toggle,
            on_ptt_press=self.controller.ptt_press,
            on_ptt_release=self.controller.ptt_release,
            on_toggle_box=self.toggle_dictation_box
        )
        self.hotkey_mgr.start()

    @Slot(str)
    def _on_state_changed(self, state: str):
        if state == DictationState.RECORDING:
            self.mic_btn.setText("🔴 REC")
            self.mic_btn.setStyleSheet(self._get_mic_btn_style(True))
            self.status_lbl.setText("Recording...")
            self.status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
            self.rec_timer.start()
        else:
            self.rec_timer.stop()
            self.mic_btn.setText("🎙️ MIC")
            self.mic_btn.setStyleSheet(self._get_mic_btn_style(False))
            self.vu_bar.setValue(0)

    @Slot(float)
    def _on_vu_meter_updated(self, vu: float):
        self.vu_bar.setValue(int(vu))

    @Slot(str, float)
    def _on_recording_saved(self, file_name: str, duration: float):
        self.status_lbl.setText(f"Transcribed ({duration:.1f}s)")
        self.status_lbl.setStyleSheet("color: #10b981; font-weight: demi-bold;")
        QTimer.singleShot(3500, lambda: self._reset_status())

    @Slot(str)
    def _on_transcription_received(self, text: str):
        """Inserts recognized text at active cursor position in Dictation Box."""
        if self.dictation_box.isVisible():
            self.dictation_box.insert_at_cursor(text)

    @Slot(str, str, str)
    def _on_command_recognized(self, name: str, hotkey: str, description: str):
        """Displays transient 3.0s command toast badge beside the floating pill."""
        self.toast.show_command(name, hotkey, self.geometry())

    @Slot(str, str)
    def _on_execute_command_requested(self, trigger: str, target: str):
        """Executes voice command on the main GUI thread safely."""
        box = self.dictation_box if self.dictation_box.isVisible() else None
        self.controller.command_executor.execute_command(
            trigger=trigger,
            target=target,
            dictation_box=box
        )

    @Slot(str)
    def _on_model_switched(self, model_name: str):
        short_name = model_name.split()[0]
        self.status_lbl.setText(f"Model: {short_name}")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-weight: demi-bold;")
        QTimer.singleShot(3000, lambda: self._reset_status())

    def toggle_dictation_box(self):
        """
        Toggles visibility of the Dictation Box and dynamically
        routes dictation target:
        - Box Visible -> Dictates into Dictation Box at cursor.
        - Box Hidden  -> Dictates into Active OS Window cursor.
        """
        if self.dictation_box.isVisible():
            self.dictation_box.hide()
            self.config.dictation_target = "cursor"
            self.controller.config.dictation_target = "cursor"
            self.config.save()
            self.status_lbl.setText("Target: Cursor")
            self.status_lbl.setStyleSheet("color: #38bdf8; font-weight: demi-bold;")
            QTimer.singleShot(2500, lambda: self._reset_status())
        else:
            self._position_dictation_box()
            self.dictation_box.show()
            self.config.dictation_target = "box"
            self.controller.config.dictation_target = "box"
            self.config.save()
            self.status_lbl.setText("Target: Box")
            self.status_lbl.setStyleSheet("color: #10b981; font-weight: demi-bold;")
            QTimer.singleShot(2500, lambda: self._reset_status())

    def _position_dictation_box(self):
        """Positions Dictation Box cleanly below the floating pill with screen boundary clamping."""
        pill_geo = self.geometry()
        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry() if screen else None

        x = pill_geo.x() + (pill_geo.width() - self.dictation_box.width())
        y = pill_geo.y() + pill_geo.height() + 8

        if screen_geo:
            x = max(screen_geo.left() + 16, min(x, screen_geo.right() - self.dictation_box.width() - 16))
            y = max(screen_geo.top() + 16, min(y, screen_geo.bottom() - self.dictation_box.height() - 16))

        self.dictation_box.move(x, y)

    def _reset_status(self):
        if self.controller.state == DictationState.IDLE:
            self.status_lbl.setText("Ready")
            self.status_lbl.setStyleSheet("color: #94a3b8;")

    def _update_recording_duration(self):
        if self.controller.state == DictationState.RECORDING:
            elapsed = time.time() - self.controller.recorder.start_time
            self.status_lbl.setText(f"Rec {elapsed:.1f}s")

    def _get_hotkey_display(self) -> str:
        hk = self.config.hotkey.lower()
        if "ctrl_r" in hk or "right" in hk:
            return "RCtrl"
        return self.config.hotkey.upper()

    def _get_mic_btn_style(self, is_rec: bool) -> str:
        if is_rec:
            return """
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 17px;
                    padding: 4px 12px;
                    border: 1.5px solid #f87171;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border-radius: 17px;
                    padding: 4px 12px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
            """

    # Smooth Mouse Dragging Across Any X11/XWayland Desktop
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F8:
            self.controller.toggle()
            event.accept()
        elif event.key() == Qt.Key.Key_D and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.toggle_dictation_box()
            event.accept()
        else:
            super().keyPressEvent(event)

    # Dropdown Menu
    def show_dropdown_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
            }
        """)

        # 1. Model Selection Sub-Menu
        model_menu = menu.addMenu("🧠 STT Model Engine")
        model_menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
            }
        """)

        model_group = QActionGroup(self)
        for key, name in AVAILABLE_MODELS.items():
            action = QAction(name, model_menu, checkable=True)
            action.setChecked(self.config.stt_model == key)
            action.triggered.connect(lambda checked=False, k=key: self.controller.switch_model(k))
            model_group.addAction(action)
            model_menu.addAction(action)

        menu.addSeparator()

        # 2. Toggle Dictation Box Action
        box_text = "✕ Hide Dictation Box [Ctrl+D]" if self.dictation_box.isVisible() else "📝 Show Dictation Box [Ctrl+D]"
        box_action = QAction(box_text, self)
        box_action.triggered.connect(self.toggle_dictation_box)
        menu.addAction(box_action)

        # 3. Open Recordings Folder
        open_rec_action = QAction("📁 Open Recordings Folder", self)
        open_rec_action.triggered.connect(self._open_recordings_dir)
        menu.addAction(open_rec_action)

        # 4. Mode Toggle (Toggle vs PTT)
        mode_text = "Switch to Push-To-Talk (Hold RCtrl/Click)" if self.config.hotkey_mode == "toggle" else "Switch to Toggle Mode (Press RCtrl/Click)"
        mode_action = QAction(mode_text, self)
        mode_action.triggered.connect(self._toggle_ptt_mode)
        menu.addAction(mode_action)

        menu.addSeparator()

        # 5. Close Widget
        quit_action = QAction("✕ Close Companion", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        menu.exec(self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height())))

    def _open_recordings_dir(self):
        rec_path = Path("recordings").resolve()
        rec_path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(rec_path))
        elif sys.platform == "darwin":
            os.system(f"open '{rec_path}'")
        else:
            os.system(f"xdg-open '{rec_path}' &")

    def _toggle_ptt_mode(self):
        self.config.hotkey_mode = "ptt" if self.config.hotkey_mode == "toggle" else "toggle"
        self.config.save()
        self.hotkey_mgr.hotkey_mode = self.config.hotkey_mode
