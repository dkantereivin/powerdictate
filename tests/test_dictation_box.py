import pytest
from PySide6.QtWidgets import QApplication
from widget.ui.dictation_box import DictationBoxWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dictation_box_append_and_clear(qapp):
    box = DictationBoxWidget()
    assert box.text_edit.toPlainText() == ""

    # Append first chunk
    box.append_transcription("Patient presents with acute shortness of breath.")
    assert "shortness of breath" in box.text_edit.toPlainText()

    # Append second chunk
    box.append_transcription("Assessment and plan: congestive heart failure.")
    text = box.text_edit.toPlainText().strip()
    assert "shortness of breath." in text
    assert "congestive heart failure." in text

    # Transfer text
    transferred = []
    box.text_transferred.connect(lambda t: transferred.append(t))
    box.transfer_text()
    assert len(transferred) == 1
    assert transferred[0] == text

    # Clear
    box.clear_text()
    assert box.text_edit.toPlainText() == ""
