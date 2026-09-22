"""
Dragon Medical One Style Floating Dictation Box (Interactive & Context-Aware)
=============================================================================
A floating, collapsible text editor window with full focus, manual typing,
context-aware mid-sentence cursor insertions, newlines, and one-click transfer.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPainter, QClipboard, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QGraphicsDropShadowEffect, QStyleOption, QStyle
)

from widget.lexer.rule_engine import MedicalRuleEngine


class DictationBoxHeader(QWidget):
    """Draggable header bar for the Dictation Box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.drag_position = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.parent_window:
            self.drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.parent_window:
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


class DictationBoxWidget(QWidget):
    """
    Floating, Always-on-Top Dragon-style Interactive Dictation Box.
    """

    text_transferred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rule_engine = MedicalRuleEngine()

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self):
        # Window + Frameless + AlwaysOnTop (Allows standard keyboard & mouse focus)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(440, 260)

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
        self.container.setObjectName("boxContainer")
        self.container.setStyleSheet("""
            #boxContainer {
                background-color: #0f172a;
                border: 1.5px solid #334155;
                border-radius: 14px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        box_layout = QVBoxLayout(self.container)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(8)

        # 1. Draggable Header Bar
        self.header = DictationBoxHeader(self)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        # Title & Icon
        title_lbl = QLabel("📝 Dictation Box", self.header)
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #f8fafc;")
        header_layout.addWidget(title_lbl)

        # Status badge
        self.status_badge = QLabel("● Active Target", self.header)
        self.status_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.status_badge.setStyleSheet("color: #38bdf8; padding-left: 4px;")
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        # Word count label
        self.stats_lbl = QLabel("0 words", self.header)
        self.stats_lbl.setFont(QFont("Segoe UI", 8))
        self.stats_lbl.setStyleSheet("color: #64748b;")
        header_layout.addWidget(self.stats_lbl)

        # Close button
        close_btn = QPushButton("✕", self.header)
        close_btn.setToolTip("Close Dictation Box (Ctrl+D)")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(close_btn)

        box_layout.addWidget(self.header)

        # 2. Interactive & Modifiable Text Editor Area
        self.text_edit = QTextEdit(self.container)
        self.text_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.text_edit.setFont(QFont("Segoe UI", 10))
        self.text_edit.setPlaceholderText("Dictate or type here. Click anywhere to move cursor and insert midway...")
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #0284c7;
            }
            QTextEdit:focus {
                border: 1.5px solid #0284c7;
            }
        """)
        self.text_edit.textChanged.connect(self._update_stats)
        box_layout.addWidget(self.text_edit)

        # 3. Action Footer Bar
        footer = QWidget(self.container)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        # Clear Button
        clear_btn = QPushButton("🗑️ Clear", footer)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        clear_btn.clicked.connect(self.clear_text)
        footer_layout.addWidget(clear_btn)

        # Shortcut hint
        hint_lbl = QLabel("Toggle Box: [Ctrl+D]", footer)
        hint_lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        hint_lbl.setStyleSheet("color: #64748b;")
        footer_layout.addWidget(hint_lbl)

        footer_layout.addStretch()

        # Transfer / Paste Button
        self.transfer_btn = QPushButton("📋 Transfer / Paste", footer)
        self.transfer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.transfer_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border-radius: 6px;
                padding: 5px 14px;
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
        - Adjusts capitalization and spacing according to surrounding text.
        """
        if not new_text or not new_text.strip():
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

        self.transfer_btn.setText("✓ Copied to Clipboard!")
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border-radius: 6px;
                padding: 5px 14px;
                border: none;
            }
        """)
        QTimer.singleShot(2000, lambda: self._reset_transfer_btn())
        self.text_transferred.emit(text)

    def _reset_transfer_btn(self):
        self.transfer_btn.setText("📋 Transfer / Paste")
        self.transfer_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                border-radius: 6px;
                padding: 5px 14px;
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
        self.stats_lbl.setText(f"{words} words ({chars} chars)")
