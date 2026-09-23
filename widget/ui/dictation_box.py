"""
Floating Interactive Dictation Box Widget
=========================================
Dragon-style floating text editor that allows real-time dictation,
click-to-position text insertion, template bracket navigation ([***]),
keyboard manual editing, and one-click transfer to active documents.
"""

import re
import logging
from typing import Optional

from PySide6.QtCore import Qt, QPoint, Signal, QTimer
from PySide6.QtGui import (
    QFont, QColor, QPainter, QTextCursor, QClipboard
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGraphicsDropShadowEffect, QApplication,
    QStyleOption, QStyle, QFrame
)

from widget.lexer.rule_engine import MedicalRuleEngine

logger = logging.getLogger("widget.dictation_box")


class DictationBoxHeader(QWidget):
    """Draggable header bar for repositioning the Dictation Box."""

    def __init__(self, parent_box):
        super().__init__(parent_box)
        self.parent_box = parent_box
        self.drag_pos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.parent_box.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.parent_box.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()


class DictationBoxWidget(QWidget):
    """
    Floating, Always-on-Top Dragon-style Interactive Dictation Box.
    Spacious, clean, professional clinical text canvas.
    """

    text_transferred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rule_engine = MedicalRuleEngine()

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Roughly 50% larger than original 440x260 -> 660x400
        self.resize(660, 400)
        self.setMinimumSize(520, 320)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        # Container Frame
        self.container = QWidget(self)
        self.container.setObjectName("boxContainer")
        self.container.setStyleSheet("""
            #boxContainer {
                background-color: #0b1120;
                border: 1.5px solid #1e293b;
                border-radius: 16px;
            }
        """)

        # Sleek layered shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)

        box_layout = QVBoxLayout(self.container)
        box_layout.setContentsMargins(14, 12, 14, 12)
        box_layout.setSpacing(10)

        # 1. Draggable Header Bar
        self.header = DictationBoxHeader(self)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # App Icon & Title
        title_lbl = QLabel("📝 Dictation Canvas", self.header)
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #f8fafc;")
        header_layout.addWidget(title_lbl)

        # Status badge (Target Indicator)
        self.status_badge = QLabel("● Active Target", self.header)
        self.status_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.status_badge.setStyleSheet("""
            color: #38bdf8;
            background-color: #0c4a6e;
            padding: 2px 8px;
            border-radius: 10px;
        """)
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        # Word & Char Count
        self.stats_lbl = QLabel("0 words • 0 chars", self.header)
        self.stats_lbl.setFont(QFont("Segoe UI", 8))
        self.stats_lbl.setStyleSheet("color: #64748b; padding-right: 4px;")
        header_layout.addWidget(self.stats_lbl)

        # Close button
        close_btn = QPushButton("✕", self.header)
        close_btn.setToolTip("Close Dictation Box (Ctrl+D)")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)

        box_layout.addWidget(self.header)

        # 2. Interactive & Modifiable Text Editor Area
        self.text_edit = QTextEdit(self.container)
        self.text_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.text_edit.setFont(QFont("Segoe UI", 11))
        self.text_edit.setPlaceholderText(
            "Dictate or type clinical notes... Say 'Next field' to navigate [***] template fields."
        )
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 12px;
                line-height: 1.45;
                selection-background-color: #0284c7;
            }
            QTextEdit:focus {
                border: 1.5px solid #0284c7;
                background-color: #0f172a;
            }
            QScrollBar:vertical {
                border: none;
                background: #0b1120;
                width: 8px;
                margin: 4px 0 4px 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.text_edit.textChanged.connect(self._update_stats)
        box_layout.addWidget(self.text_edit)

        # 3. Action Footer Bar
        footer = QWidget(self.container)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(10)

        # Clear Button
        clear_btn = QPushButton("🗑️ Clear", footer)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 7px;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        clear_btn.clicked.connect(self.clear_text)
        footer_layout.addWidget(clear_btn)

        # Shortcut hint
        hint_lbl = QLabel("Toggle Box: [Ctrl+D]  •  Next Field: [Tab / Voice]", footer)
        hint_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        hint_lbl.setStyleSheet("color: #475569;")
        footer_layout.addWidget(hint_lbl)

        footer_layout.addStretch()

        # Transfer / Paste Button
        self.transfer_btn = QPushButton("📋 Transfer Note", footer)
        self.transfer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.transfer_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border-radius: 7px;
                padding: 6px 18px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.transfer_btn.clicked.connect(self.transfer_text)
        footer_layout.addWidget(self.transfer_btn)

        box_layout.addWidget(footer)
        main_layout.addWidget(self.container)

    def insert_at_cursor(self, new_text: str):
        """
        Context-aware insertion at active cursor position:
        - Directly inserts newlines and whitespace commands.
        - Preserves multi-line templates without flattening.
        - Adjusts capitalization and spacing according to surrounding text.
        """
        if not new_text:
            return

        # 1. Direct handling of newlines and whitespace commands
        if new_text in ("\n", "\n\n", "\t"):
            cursor = self.text_edit.textCursor()
            cursor.insertText(new_text)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
            return

        # 2. Direct handling of multi-line templates (preserving exact casing and lines)
        if "\n" in new_text:
            self.insert_template(new_text)
            return

        if not new_text.strip():
            return

        cursor = self.text_edit.textCursor()
        pos = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        end_pos = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
        full_text = self.text_edit.toPlainText()

        prefix_text = full_text[:pos]
        suffix_text = full_text[end_pos:]

        # Apply context-aware formatting via Rule Engine
        insert_chunk = self.rule_engine.format_insertion_context(
            prefix_text=prefix_text,
            new_text=new_text,
            suffix_text=suffix_text
        )

        # If inserting punctuation directly after a trailing space, remove the space so it attaches cleanly
        if insert_chunk.lstrip().startswith((".", ",", ";", ":", "!", "?")):
            while pos > 0 and full_text[pos - 1] == " ":
                cursor.deletePreviousChar()
                pos -= 1

        cursor.insertText(insert_chunk)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def insert_template(self, template_text: str):
        """
        Inserts structured multi-line template directly, preserving exact
        capitalization, indentation, newlines, and [***] bracket placeholders.
        """
        if not template_text:
            return

        cursor = self.text_edit.textCursor()
        pos = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        full_text = self.text_edit.toPlainText()

        # If not at start of document and previous text doesn't end with newline, prepend newline
        prefix = full_text[:pos]
        if prefix and not prefix.endswith("\n"):
            cursor.insertText("\n")

        cursor.insertText(template_text)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

        # Automatically focus first field in the template if brackets exist
        if "[" in template_text:
            self.focus_first_field(from_pos=pos)

    def focus_first_field(self, from_pos: int = 0) -> bool:
        """
        Finds and selects the first [***] or [...] bracket field starting at or after from_pos.
        If none found after from_pos, searches from document start (pos=0).
        """
        doc = self.text_edit.document()
        start_cursor = QTextCursor(doc)
        if from_pos > 0:
            start_cursor.setPosition(min(from_pos, max(0, doc.characterCount() - 1)))

        found_cursor = doc.find("[", start_cursor)
        if found_cursor.isNull() and from_pos > 0:
            start_cursor = QTextCursor(doc)
            found_cursor = doc.find("[", start_cursor)

        if not found_cursor.isNull():
            close_cursor = doc.find("]", found_cursor)
            if not close_cursor.isNull():
                found_cursor.setPosition(close_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
            self.text_edit.setTextCursor(found_cursor)
            self.text_edit.ensureCursorVisible()
            return True
        return False

    def append_transcription(self, new_text: str):
        """Alias for insert_at_cursor."""
        self.insert_at_cursor(new_text)

    def clear_text(self):
        self.text_edit.clear()

    def transfer_text(self):
        """Copies text to clipboard and emits transfer signal."""
        text = self.text_edit.toPlainText().strip()
        if not text:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text, QClipboard.Mode.Clipboard)
        clipboard.setText(text, QClipboard.Mode.Selection)

        self.transfer_btn.setText("✓ Copied to Clipboard!")
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border-radius: 7px;
                padding: 6px 18px;
                font-weight: bold;
                border: none;
            }
        """)
        QTimer.singleShot(2000, lambda: self._reset_transfer_btn())
        self.text_transferred.emit(text)

    def _reset_transfer_btn(self):
        self.transfer_btn.setText("📋 Transfer Note")
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border-radius: 7px;
                padding: 6px 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)

    def _update_stats(self):
        text = self.text_edit.toPlainText().strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        self.stats_lbl.setText(f"{words} words • {chars} chars")
