"""
Floating Interactive Dictation Box Widget
=========================================
Dragon-style floating text editor that allows real-time dictation,
click-to-position text insertion, template bracket navigation ([***]),
interactive picklist dropdowns ([No/Yes], [DOAC/LMWH]), live field highlighting,
keyboard manual editing, and one-click transfer to active documents.
"""

import re
import logging
from typing import Optional

from PySide6.QtCore import Qt, QPoint, Signal, QTimer
from PySide6.QtGui import (
    QFont, QColor, QPainter, QTextCursor, QClipboard,
    QTextCharFormat, QSyntaxHighlighter, QTextDocument
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QGraphicsDropShadowEffect, QApplication,
    QStyleOption, QStyle, QFrame, QMenu, QInputDialog
)

from widget.lexer.rule_engine import MedicalRuleEngine
from widget.templates.parser import TemplateParser, TemplateField, FieldType
from widget.ui.field_popup import FieldPopupWidget
from widget.ocr.service import ClinicalOcrService
from widget.ocr.llm_transformer import LLMTransformer, TransformWorker

logger = logging.getLogger("widget.dictation_box")


class ClinicalFieldHighlighter(QSyntaxHighlighter):
    """
    Live syntax highlighter rendering bracket fields as clean badges:
    - [***]: Amber alert badge (needs fill)
    - [No]: Emerald green default badge
    - [No/Yes]: Sky blue interactive picklist badge
    """

    def __init__(self, parent_doc):
        super().__init__(parent_doc)
        # 1. Regular template wildcard format: benign, calm, non-abrasive soft sky/slate pill
        self.wildcard_fmt = QTextCharFormat()
        self.wildcard_fmt.setForeground(QColor("#93c5fd"))  # Soft calming blue
        self.wildcard_fmt.setBackground(QColor("#1e293b"))  # Slate-800 capsule
        self.wildcard_fmt.setFontWeight(QFont.Weight.DemiBold)

        # 2. Choice with free-text wildcard: gentle, non-abrasive muted warm peach
        self.wildcard_picklist_fmt = QTextCharFormat()
        self.wildcard_picklist_fmt.setForeground(QColor("#fed7aa"))  # Soft warm peach
        self.wildcard_picklist_fmt.setBackground(QColor("#2d1f18"))  # Muted warm slate
        self.wildcard_picklist_fmt.setFontWeight(QFont.Weight.DemiBold)

        # 3. Default format: gentle sage green
        self.default_fmt = QTextCharFormat()
        self.default_fmt.setForeground(QColor("#86efac"))    # Emerald-300
        self.default_fmt.setBackground(QColor("#064e3b"))    # Emerald-950
        self.default_fmt.setFontWeight(QFont.Weight.DemiBold)

        # 4. Interactive picklist format: sleek cyan/sky blue
        self.picklist_fmt = QTextCharFormat()
        self.picklist_fmt.setForeground(QColor("#38bdf8"))   # Sky-400
        self.picklist_fmt.setBackground(QColor("#0c4a6e"))   # Sky-950
        self.picklist_fmt.setFontWeight(QFont.Weight.DemiBold)

    def highlightBlock(self, text: str):
        fields = TemplateParser.parse_fields(text)
        for field in fields:
            length = field.end_pos - field.start_pos
            if field.field_type == FieldType.WILDCARD:
                self.setFormat(field.start_pos, length, self.wildcard_fmt)
            elif field.field_type == FieldType.WILDCARD_PICKLIST:
                self.setFormat(field.start_pos, length, self.wildcard_picklist_fmt)
            elif field.field_type == FieldType.DEFAULT:
                self.setFormat(field.start_pos, length, self.default_fmt)
            elif field.field_type == FieldType.PICKLIST:
                self.setFormat(field.start_pos, length, self.picklist_fmt)


class ClinicalTextEdit(QTextEdit):
    """
    Enhanced clinical text editor with zero-latency template navigation,
    Tab/Shift+Tab field cycling, numeric picklist shortcuts (1-9),
    and mouse click detection for interactive bracket dropdowns.
    """

    def __init__(self, parent_box: "DictationBoxWidget"):
        super().__init__(parent_box.container)
        self.parent_box = parent_box

    def keyPressEvent(self, event):
        popup = getattr(self.parent_box, "field_popup", None)
        popup_visible = popup is not None and popup.isVisible()

        key = event.key()
        modifiers = event.modifiers()

        # Tab navigation for fields (without losing focus)
        if key == Qt.Key.Key_Tab and not (modifiers & Qt.KeyboardModifier.ShiftModifier):
            self.parent_box.navigate_next_field()
            event.accept()
            return

        if key == Qt.Key.Key_Backtab or (key == Qt.Key.Key_Tab and (modifiers & Qt.KeyboardModifier.ShiftModifier)):
            self.parent_box.navigate_prev_field()
            event.accept()
            return

        # Interactive popup controls when open
        if popup_visible:
            if key == Qt.Key.Key_Escape:
                popup.hide()
                event.accept()
                return

            if key == Qt.Key.Key_Down:
                popup.move_selection(1)
                event.accept()
                return

            if key == Qt.Key.Key_Up:
                popup.move_selection(-1)
                event.accept()
                return

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                popup.select_current()
                event.accept()
                return

            # Digits 1-9 to select numbered options
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                idx = key - Qt.Key.Key_1  # 0 to 8
                if popup.has_index(idx):
                    popup.select_index(idx)
                    event.accept()
                    return

            # If user starts typing standard alphanumeric text or backspace, hide popup and let editor type
            if key not in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                popup.hide()

        # Screen Snip & Clipboard Parse shortcuts
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            if key == Qt.Key.Key_S:
                self.parent_box.trigger_screen_snip()
                event.accept()
                return
            elif key == Qt.Key.Key_V:
                self.parent_box.parse_clipboard_image()
                event.accept()
                return
            elif key == Qt.Key.Key_B:
                self.parent_box.toggle_batch_mode()
                event.accept()
                return

        # LLM Template Transformation: Ctrl+Alt+T or Ctrl+Alt+L
        if (modifiers & Qt.KeyboardModifier.ControlModifier) and (modifiers & Qt.KeyboardModifier.AltModifier):
            if key in (Qt.Key.Key_T, Qt.Key.Key_L):
                self.parent_box.run_llm_transform("pertinent_labs")
                event.accept()
                return

        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.parent_box.check_field_at_cursor()


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
    Spacious, clean, professional clinical text canvas with interactive picklists.
    """

    text_transferred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rule_engine = MedicalRuleEngine()

        self._init_window_flags()
        self._init_ui()

        self.field_popup = FieldPopupWidget(self)
        self.field_popup.option_selected.connect(self._on_field_option_selected)

        self.highlighter = ClinicalFieldHighlighter(self.text_edit)

        self.ocr_service = ClinicalOcrService(self)
        self.ocr_service.parsing_started.connect(self._on_ocr_started)
        self.ocr_service.parsing_completed.connect(self._on_ocr_completed)
        self.ocr_service.parsing_failed.connect(self._on_ocr_failed)
        self.ocr_service.batch_updated.connect(self._on_batch_updated)

    def _init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(660, 400)
        self.setMinimumSize(520, 320)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def hideEvent(self, event):
        if hasattr(self, "field_popup") and self.field_popup:
            self.field_popup.hide()
        super().hideEvent(event)

    def moveEvent(self, event):
        if hasattr(self, "field_popup") and self.field_popup:
            self.field_popup.hide()
        super().moveEvent(event)

    def closeEvent(self, event):
        if hasattr(self, "field_popup") and self.field_popup:
            self.field_popup.close()
        super().closeEvent(event)

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
        self.text_edit = ClinicalTextEdit(self)
        self.text_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.text_edit.setFont(QFont("Segoe UI", 11))
        self.text_edit.setPlaceholderText(
            "Dictate or type clinical notes... Say 'Next field' to navigate [***] or [No/Yes] fields."
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

        # Snip Labs Button
        self.snip_btn = QPushButton("📷 Snip Labs", footer)
        self.snip_btn.setToolTip("Drag crosshair over Meditech / Citrix to parse labs (Ctrl+Shift+S)")
        self.snip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snip_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.snip_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 7px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: white;
            }
        """)
        self.snip_btn.clicked.connect(self.trigger_screen_snip)
        footer_layout.addWidget(self.snip_btn)

        # Batch Multi-Page Snip Button
        self.batch_btn = QPushButton("📑 Batch Snip", footer)
        self.batch_btn.setToolTip("Snip multiple Meditech tabs/pages and merge into a single consult report (Ctrl+Shift+B)")
        self.batch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self._reset_batch_btn_style()
        self.batch_btn.clicked.connect(self.toggle_batch_mode)
        footer_layout.addWidget(self.batch_btn)

        # Parse Clipboard Image Button
        self.parse_clipboard_btn = QPushButton("📋 Parse Image", footer)
        self.parse_clipboard_btn.setToolTip("Parse screenshot currently on clipboard (Ctrl+Shift+V)")
        self.parse_clipboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.parse_clipboard_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.parse_clipboard_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 7px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        self.parse_clipboard_btn.clicked.connect(self.parse_clipboard_image)
        footer_layout.addWidget(self.parse_clipboard_btn)

        # LLM Template / Transformation Button
        self.llm_btn = QPushButton("✨ LLM Template", footer)
        self.llm_btn.setToolTip("Transform text or filter labs using AI rules (Ctrl+Alt+T)")
        self.llm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.llm_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #c084fc;
                border: 1px solid #7c3aed;
                border-radius: 7px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #5b21b6;
                color: white;
            }
        """)
        self.llm_btn.clicked.connect(self.show_llm_transform_menu)
        footer_layout.addWidget(self.llm_btn)

        # Shortcut hint
        hint_lbl = QLabel("Toggle: [Ctrl+D] • Snip: [Ctrl+Shift+S] • Batch: [Ctrl+Shift+B] • LLM: [Ctrl+Alt+T] • Field: [Tab]", footer)
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

    def check_field_at_cursor(self):
        """
        Inspects cursor position after mouse click.
        If inside or selecting a bracket field:
        - Selects the entire bracket field.
        - If field is a choice (has multiple options), opens FieldPopupWidget.
        - Else hides popup.
        """
        cursor = self.text_edit.textCursor()
        pos = cursor.position()
        text = self.text_edit.toPlainText()

        fields = TemplateParser.parse_fields(text)
        active_field = None
        for f in fields:
            if cursor.hasSelection():
                if f.start_pos <= cursor.selectionStart() and cursor.selectionEnd() <= f.end_pos:
                    active_field = f
                    break
            else:
                if f.start_pos <= pos < f.end_pos:
                    active_field = f
                    break

        if active_field:
            if cursor.selectionStart() != active_field.start_pos or cursor.selectionEnd() != active_field.end_pos:
                sel_cursor = self.text_edit.textCursor()
                sel_cursor.setPosition(active_field.start_pos)
                sel_cursor.setPosition(active_field.end_pos, QTextCursor.MoveMode.KeepAnchor)
                self.text_edit.setTextCursor(sel_cursor)

            if active_field.is_choice:
                self._show_field_popup(active_field)
            else:
                if self.field_popup:
                    self.field_popup.hide()
        else:
            if self.field_popup:
                self.field_popup.hide()

    def _show_field_popup(self, field: TemplateField):
        if not self.field_popup:
            return
        cursor_rect = self.text_edit.cursorRect()
        global_pos = self.text_edit.viewport().mapToGlobal(cursor_rect.bottomLeft())
        if self.windowHandle() and self.field_popup.windowHandle():
            self.field_popup.windowHandle().setTransientParent(self.windowHandle())
        self.field_popup.show_for_field(field, global_pos)

    def _on_field_option_selected(self, option_text: str):
        if self.field_popup:
            self.field_popup.hide()

        cursor = self.text_edit.textCursor()
        if not (cursor.hasSelection() and cursor.selectedText().startswith("[") and cursor.selectedText().endswith("]")):
            pos = cursor.position()
            text = self.text_edit.toPlainText()
            for f in TemplateParser.parse_fields(text):
                if f.start_pos <= pos <= f.end_pos:
                    cursor.setPosition(f.start_pos)
                    cursor.setPosition(f.end_pos, QTextCursor.MoveMode.KeepAnchor)
                    break

        cursor.insertText(option_text)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        self.text_edit.setFocus()

        self.navigate_next_field()

    def navigate_next_field(self) -> bool:
        """
        Advances to the next template field:
        1. If active/selected field has a default (e.g. [No/Yes] or [No]), replaces with default.
        2. Closes popup.
        3. Finds next '[' bracket in document (looping back to start if needed).
        4. Selects bracket and shows popup if it is a picklist choice.
        """
        if self.field_popup:
            self.field_popup.hide()

        cursor = self.text_edit.textCursor()
        doc = self.text_edit.document()
        full_text = self.text_edit.toPlainText()

        resolved_current = False

        # Step 1: Check if current selection or position is on a field with a default
        active_field = None
        if cursor.hasSelection():
            sel_text = cursor.selectedText()
            active_field = TemplateParser.parse_field_string(sel_text)
        else:
            pos = cursor.position()
            for f in TemplateParser.parse_fields(full_text):
                if f.start_pos <= pos <= f.end_pos:
                    active_field = f
                    cursor.setPosition(f.start_pos)
                    cursor.setPosition(f.end_pos, QTextCursor.MoveMode.KeepAnchor)
                    break

        if active_field and active_field.has_default:
            cursor.insertText(active_field.default_value)
            self.text_edit.setTextCursor(cursor)
            resolved_current = True

        # Step 2: Search for next '[' bracket after cursor
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            cursor.setPosition(cursor.selectionEnd())

        found_cursor = doc.find("[", cursor)

        # Loop back to document start if no more brackets after cursor
        if found_cursor.isNull():
            start_cursor = QTextCursor(doc)
            found_cursor = doc.find("[", start_cursor)

        if not found_cursor.isNull():
            close_cursor = doc.find("]", found_cursor)
            if not close_cursor.isNull():
                found_cursor.setPosition(close_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
            self.text_edit.setTextCursor(found_cursor)
            self.text_edit.ensureCursorVisible()

            bracket_str = found_cursor.selectedText()
            next_field = TemplateParser.parse_field_string(bracket_str)
            if next_field and next_field.is_choice:
                self._show_field_popup(next_field)

            return True

        return resolved_current

    def navigate_prev_field(self) -> bool:
        """Jumps to the previous template field in the document."""
        if self.field_popup:
            self.field_popup.hide()

        cursor = self.text_edit.textCursor()
        doc = self.text_edit.document()

        search_cursor = QTextCursor(cursor)
        if search_cursor.hasSelection():
            search_cursor.setPosition(search_cursor.selectionStart())

        found_cursor = doc.find("[", search_cursor, QTextDocument.FindFlag.FindBackward)
        if found_cursor.isNull():
            end_cursor = QTextCursor(doc)
            end_cursor.movePosition(QTextCursor.MoveOperation.End)
            found_cursor = doc.find("[", end_cursor, QTextDocument.FindFlag.FindBackward)

        if not found_cursor.isNull():
            close_cursor = doc.find("]", found_cursor)
            if not close_cursor.isNull():
                found_cursor.setPosition(close_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
            self.text_edit.setTextCursor(found_cursor)
            self.text_edit.ensureCursorVisible()

            bracket_str = found_cursor.selectedText()
            field = TemplateParser.parse_field_string(bracket_str)
            if field and field.is_choice:
                self._show_field_popup(field)

            return True

        return False

    def focus_first_field(self, from_pos: int = 0) -> bool:
        """
        Finds and selects the first [***] or [...] bracket field starting at or after from_pos.
        If none found after from_pos, searches from document start (pos=0).
        """
        if self.field_popup:
            self.field_popup.hide()

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

            bracket_str = found_cursor.selectedText()
            field = TemplateParser.parse_field_string(bracket_str)
            if field and field.is_choice:
                self._show_field_popup(field)

            return True
        return False

    def insert_at_cursor(self, new_text: str):
        """
        Context-aware insertion at active cursor position:
        - Directly inserts newlines and whitespace commands.
        - Preserves multi-line templates without flattening.
        - Matches spoken picklist choices against open popup.
        - Adjusts capitalization and spacing according to surrounding text.
        """
        if not new_text:
            return

        # 1. Direct handling of newlines and whitespace commands
        if new_text in ("\n", "\n\n", "\t"):
            if self.field_popup:
                self.field_popup.hide()
            cursor = self.text_edit.textCursor()
            cursor.insertText(new_text)
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
            return

        # 2. Direct handling of multi-line templates (preserving exact casing and lines)
        if "\n" in new_text:
            if self.field_popup:
                self.field_popup.hide()
            self.insert_template(new_text)
            return

        if not new_text.strip():
            return

        # 3. Check if popup is currently open and speech matches one of the picklist options
        if self.field_popup and self.field_popup.isVisible():
            active_options = self.field_popup.current_options
            cleaned_input = new_text.strip().lower()
            matched_option = None
            for opt in active_options:
                if cleaned_input == opt.lower():
                    matched_option = opt
                    break

            if matched_option:
                self._on_field_option_selected(matched_option)
                return

            self.field_popup.hide()

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

    def append_transcription(self, new_text: str):
        """Alias for insert_at_cursor."""
        self.insert_at_cursor(new_text)

    def clear_text(self):
        if self.field_popup:
            self.field_popup.hide()
        self.text_edit.clear()

    def transfer_text(self):
        """
        Resolves all template defaults across the entire note:
        - [No] -> No
        - [No/Yes] -> No
        - [***/DOAC/LMWH] -> [***]
        - [***] -> counted as unfilled wildcards
        Copies fully resolved note to clipboard, updates UI, and emits transfer signal.
        """
        if self.field_popup:
            self.field_popup.hide()

        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            return

        resolved_text, unfilled_count = TemplateParser.resolve_all_defaults(raw_text)

        # Update text edit so the clinician sees all defaults cleanly resolved
        if resolved_text != raw_text:
            cursor_pos = self.text_edit.textCursor().position()
            self.text_edit.setPlainText(resolved_text)
            new_cursor = self.text_edit.textCursor()
            new_cursor.setPosition(min(cursor_pos, len(resolved_text)))
            self.text_edit.setTextCursor(new_cursor)

        clipboard = QApplication.clipboard()
        clipboard.setText(resolved_text, QClipboard.Mode.Clipboard)
        clipboard.setText(resolved_text, QClipboard.Mode.Selection)

        if unfilled_count > 0:
            self.transfer_btn.setText(f"⚠️ Copied ({unfilled_count} unfilled [***])")
            self.transfer_btn.setStyleSheet("""
                QPushButton {
                    background-color: #9a3412;
                    color: #ffedd5;
                    border-radius: 7px;
                    padding: 6px 18px;
                    font-weight: bold;
                    border: none;
                }
            """)
        else:
            self.transfer_btn.setText("✓ Transferred to Clipboard!")
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

        QTimer.singleShot(2500, lambda: self._reset_transfer_btn())
        self.text_transferred.emit(resolved_text)

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

    # -----------------------------------------------------------------
    # Screen Snip & Clipboard OCR Ingestion
    # -----------------------------------------------------------------
    def trigger_screen_snip(self):
        """Launches interactive full-screen crosshair overlay to snip Meditech/Citrix."""
        if hasattr(self, "ocr_service") and self.ocr_service:
            self.ocr_service.trigger_screen_snip()

    def parse_clipboard_image(self):
        """Parses screenshot currently sitting on system clipboard."""
        if hasattr(self, "ocr_service") and self.ocr_service:
            success = self.ocr_service.parse_clipboard_image()
            if not success:
                self._show_ocr_status("⚠️ No image on clipboard", is_error=True)

    def toggle_batch_mode(self):
        """Toggles multi-page batch mode. When active, subsequent snips accumulate until finished."""
        if hasattr(self, "ocr_service") and self.ocr_service:
            if self.ocr_service.is_batch_mode:
                self.ocr_service.finish_batch_mode()
                self._reset_batch_btn_style()
            else:
                self.ocr_service.start_batch_mode()
                self._set_batch_btn_active(0)
                self._show_ocr_status("📑 Batch Mode: Snip Page 1...")

    def _on_batch_updated(self, count: int, summary: str):
        self._set_batch_btn_active(count)
        self._show_ocr_status(f"📑 Page {count} Added ({summary}) • Snip next or click Finish")

    def _set_batch_btn_active(self, count: int):
        if hasattr(self, "batch_btn"):
            self.batch_btn.setText(f"✅ Finish Batch ({count})")
            self.batch_btn.setStyleSheet("""
                QPushButton {
                    background-color: #065f46;
                    color: #6ee7b7;
                    border: 1px solid #10b981;
                    border-radius: 7px;
                    padding: 5px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #047857;
                    color: white;
                }
            """)

    def _reset_batch_btn_style(self):
        if hasattr(self, "batch_btn"):
            self.batch_btn.setText("📑 Batch Snip")
            self.batch_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #a78bfa;
                    border: 1px solid #8b5cf6;
                    border-radius: 7px;
                    padding: 5px 10px;
                }
                QPushButton:hover {
                    background-color: #6d28d9;
                    color: white;
                }
            """)

    def auto_crawl_meditech(self):
        """Autonomously crawls Meditech tabs on screen and compiles lab report."""
        if hasattr(self, "ocr_service") and self.ocr_service:
            self.ocr_service.trigger_auto_crawl()

    # -----------------------------------------------------------------
    # LLM Template & Text Transformation
    # -----------------------------------------------------------------
    def show_llm_transform_menu(self):
        """Displays menu of clinical LLM transformation presets."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #6d28d9;
                color: white;
            }
        """)

        a1 = menu.addAction("🎯 Filter Pertinent Labs (Select core & abnormal labs)")
        a2 = menu.addAction("📝 Summarize for Dictation / Rounds")
        a3 = menu.addAction("📋 Format as SOAP Note")
        menu.addSeparator()
        a4 = menu.addAction("✏️ Custom Prompt...")

        btn_pos = self.llm_btn.mapToGlobal(QPoint(0, -140))
        action = menu.exec(btn_pos)
        if action == a1:
            self.run_llm_transform("pertinent_labs")
        elif action == a2:
            self.run_llm_transform("summarize_dictation")
        elif action == a3:
            self.run_llm_transform("soap_format")
        elif action == a4:
            self._prompt_custom_transform()

    def _prompt_custom_transform(self):
        prompt, ok = QInputDialog.getText(
            self,
            "Custom LLM Transformation",
            "Enter instruction prompt for transforming the text:"
        )
        if ok and prompt.strip():
            self.run_llm_transform(preset="custom", custom_prompt=prompt.strip())

    def run_llm_transform(self, preset: str = "pertinent_labs", custom_prompt: str = ""):
        """Executes LLM transformation on selected text (or all text if none selected)."""
        cursor = self.text_edit.textCursor()
        has_selection = cursor.hasSelection()

        if has_selection:
            target_text = cursor.selectedText().replace("\u2029", "\n")
        else:
            target_text = self.text_edit.toPlainText().strip()

        if not target_text:
            self._show_ocr_status("⚠️ No text to transform", is_error=True)
            return

        self._show_ocr_status("⏳ Transforming with LLM...")

        self._transform_worker = TransformWorker(target_text, preset=preset, custom_prompt=custom_prompt, parent=self)
        self._transform_worker.transformation_completed.connect(
            lambda result: self._on_transform_completed(result, has_selection)
        )
        self._transform_worker.transformation_failed.connect(
            lambda err: self._show_ocr_status(f"⚠️ {err}", is_error=True)
        )
        self._transform_worker.start()

    def _on_transform_completed(self, transformed_text: str, had_selection: bool):
        if not transformed_text.strip():
            self._show_ocr_status("⚠️ Empty transformation result", is_error=True)
            return

        cursor = self.text_edit.textCursor()
        if had_selection and cursor.hasSelection():
            cursor.beginEditBlock()
            cursor.insertText(transformed_text)
            cursor.endEditBlock()
        else:
            self.text_edit.setPlainText(transformed_text)

        self._show_ocr_status("✓ Text Transformed with LLM!")

    def _on_ocr_started(self):
        self._show_ocr_status("⏳ Parsing Labs...")

    def _on_ocr_completed(self, formatted_text: str):
        self._reset_batch_btn_style()
        self.insert_template(formatted_text)
        self._show_ocr_status("✓ Labs Ingested!")

    def _on_ocr_failed(self, error_msg: str):
        self._show_ocr_status(f"⚠️ {error_msg}", is_error=True)

    def _show_ocr_status(self, message: str, is_error: bool = False):
        self.status_badge.setText(message)
        if is_error:
            self.status_badge.setStyleSheet("""
                color: #f87171;
                background-color: #450a0a;
                padding: 2px 8px;
                border-radius: 10px;
            """)
        else:
            self.status_badge.setStyleSheet("""
                color: #34d399;
                background-color: #064e3b;
                padding: 2px 8px;
                border-radius: 10px;
            """)
        QTimer.singleShot(3500, lambda: self._reset_status_badge())

    def _reset_status_badge(self):
        self.status_badge.setText("● Active Target")
        self.status_badge.setStyleSheet("""
            color: #38bdf8;
            background-color: #0c4a6e;
            padding: 2px 8px;
            border-radius: 10px;
        """)
