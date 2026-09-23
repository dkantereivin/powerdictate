"""
Interactive Field Picklist Popup Widget
======================================
Zero-focus-theft floating dropdown menu for clinical template picklists.
Appears anchored directly below active bracket fields ([No/Yes], [DOAC/LMWH]).
Allows instantaneous selection via mouse click, number keys (1-9),
Enter/Tab keys, or direct spoken voice recognition.
"""

import logging
from typing import List, Optional

from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QGraphicsDropShadowEffect, QStyleOption, QStyle,
    QApplication
)

from widget.templates.parser import TemplateField

logger = logging.getLogger("widget.field_popup")


class FieldPopupWidget(QWidget):
    """
    Floating, non-activating picklist popup for template fields.
    Uses Qt.WindowType.ToolTip so it never steals focus from the editor.
    """

    option_selected = Signal(str)
    dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_field: Optional[TemplateField] = None
        self.current_options: List[str] = []

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(0)

        # Container Frame
        self.container = QWidget(self)
        self.container.setObjectName("popupContainer")
        self.container.setStyleSheet("""
            #popupContainer {
                background-color: #0b1120;
                border: 1.5px solid #0284c7;
                border-radius: 10px;
            }
        """)

        # Drop shadow for floating effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        box_layout = QVBoxLayout(self.container)
        box_layout.setContentsMargins(8, 8, 8, 8)
        box_layout.setSpacing(6)

        # Header Hint
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 0, 4, 0)
        
        self.title_lbl = QLabel("Choose option (Click or 1-9):", self.container)
        self.title_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.title_lbl.setStyleSheet("color: #64748b;")
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()

        box_layout.addLayout(header_layout)

        # Options List Widget
        self.list_widget = QListWidget(self.container)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                color: #f1f5f9;
            }
            QListWidget::item {
                padding: 5px 8px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
                color: #38bdf8;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        box_layout.addWidget(self.list_widget)

        main_layout.addWidget(self.container)

    def show_for_field(self, field: TemplateField, global_pos: QPoint):
        """
        Populates options and positions the popup directly below global_pos.
        """
        self.current_field = field
        self.current_options = field.display_options

        if not self.current_options:
            self.hide()
            return

        self.list_widget.clear()

        has_default = field.has_default
        default_val = field.default_value

        max_len = 0
        for i, opt in enumerate(self.current_options):
            num_prefix = f"{i + 1}. " if i < 9 else "   "
            if has_default and opt == default_val:
                label_text = f"{num_prefix}{opt}  ★ default"
            else:
                label_text = f"{num_prefix}{opt}"

            item = QListWidgetItem(label_text)
            item.setData(Qt.ItemDataRole.UserRole, opt)
            self.list_widget.addItem(item)
            max_len = max(max_len, len(label_text))

        # Select first item by default
        self.list_widget.setCurrentRow(0)

        # Calculate dynamic size
        item_height = 30
        list_height = len(self.current_options) * item_height + 8
        popup_height = min(list_height + 42, 280)
        popup_width = max(min(max_len * 9 + 40, 360), 200)

        self.resize(popup_width, popup_height)

        # Screen geometry clamping
        screen = QApplication.screenAt(global_pos)
        if screen is None:
            screen = QApplication.primaryScreen()

        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        x = global_pos.x()
        y = global_pos.y() + 4

        # If goes off bottom of screen, show above
        if y + popup_height > screen_geo.bottom():
            y = global_pos.y() - popup_height - 24

        # Clamp horizontal
        if x + popup_width > screen_geo.right():
            x = screen_geo.right() - popup_width - 8
        if x < screen_geo.left():
            x = screen_geo.left() + 8

        self.move(x, y)
        self.show()
        self.raise_()

    def _on_item_clicked(self, item: QListWidgetItem):
        opt = item.data(Qt.ItemDataRole.UserRole)
        if opt:
            self.option_selected.emit(opt)

    def select_index(self, index: int) -> bool:
        """Selects the item at index (0-based) and emits option_selected."""
        if 0 <= index < len(self.current_options):
            item = self.list_widget.item(index)
            if item:
                opt = item.data(Qt.ItemDataRole.UserRole)
                if opt:
                    self.option_selected.emit(opt)
                    return True
        return False

    def select_current(self) -> bool:
        """Selects currently highlighted item."""
        row = self.list_widget.currentRow()
        if row >= 0:
            return self.select_index(row)
        elif self.current_options:
            return self.select_index(0)
        return False

    def move_selection(self, delta: int):
        """Moves highlighted row up or down."""
        count = self.list_widget.count()
        if count == 0:
            return
        row = (self.list_widget.currentRow() + delta) % count
        self.list_widget.setCurrentRow(row)

    def has_index(self, index: int) -> bool:
        return 0 <= index < len(self.current_options)
