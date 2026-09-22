import pytest
from PySide6.QtWidgets import QApplication
from widget.commands.executor import CommandExecutor
from widget.ui.dictation_box import DictationBoxWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_command_executor_bracket_navigation(qapp):
    executor = CommandExecutor()
    box = DictationBoxWidget()
    box.show()

    # Set template with bracket placeholder fields
    box.text_edit.setPlainText("Assessment: [***] Plan: [***]")
    box.text_edit.moveCursor(box.text_edit.textCursor().MoveOperation.Start)

    # 1. Jump to first bracket field
    executed = executor.execute_command("next field", target="box", dictation_box=box)
    assert executed
    selected = box.text_edit.textCursor().selectedText()
    assert selected == "[***]"

    # 2. Type/replace field
    box.insert_at_cursor("Acute heart failure.")
    assert "Assessment: Acute heart failure. Plan: [***]" in box.text_edit.toPlainText()


def test_command_executor_editing_commands(qapp):
    executor = CommandExecutor()
    box = DictationBoxWidget()
    box.show()

    box.text_edit.setPlainText("Patient has severe dyspnea.")

    # 1. Select all
    executed = executor.execute_command("select all", target="box", dictation_box=box)
    assert executed
    assert box.text_edit.textCursor().selectedText() == "Patient has severe dyspnea."

    # 2. Clear field
    executed = executor.execute_command("clear field", target="box", dictation_box=box)
    assert executed
    assert box.text_edit.toPlainText() == ""
