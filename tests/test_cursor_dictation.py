import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextCursor
from widget.ui.dictation_box import DictationBoxWidget
from widget.ui.pill_widget import FloatingPillWidget
from widget.config import WidgetConfig


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dictation_box_mid_sentence_cursor_insertion(qapp):
    box = DictationBoxWidget()
    box.text_edit.setPlainText("Patient presents with chest pain and shortness of breath.")

    # Move cursor between "with" and "chest pain" (position 22)
    cursor = box.text_edit.textCursor()
    cursor.setPosition(22)
    box.text_edit.setTextCursor(cursor)

    # Insert mid-sentence dictation
    box.insert_at_cursor("severe exertional")

    final_text = box.text_edit.toPlainText()
    assert "severe exertional" in final_text
    assert "presents with severe exertional chest pain" in final_text


def test_dictation_target_auto_switching_via_box_toggle(qapp):
    config = WidgetConfig()
    pill = FloatingPillWidget(config)

    # Initially box is hidden -> target should be "cursor"
    assert not pill.dictation_box.isVisible()
    assert pill.config.dictation_target == "cursor"

    # Toggle box ON -> target switches to "box"
    pill.toggle_dictation_box()
    assert pill.dictation_box.isVisible()
    assert pill.config.dictation_target == "box"

    # Toggle box OFF -> target switches back to "cursor"
    pill.toggle_dictation_box()
    assert not pill.dictation_box.isVisible()
    assert pill.config.dictation_target == "cursor"
