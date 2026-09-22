import pytest
from PySide6.QtWidgets import QApplication
from widget.commands.registry import CommandRegistry, register_command
from widget.commands.executor import CommandExecutor
from widget.ui.dictation_box import DictationBoxWidget
from widget.lexer.dragon_fsm import DragonLexer


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_custom_python_command_registration():
    executed_log = []

    @register_command(["test custom action", "custom action"], name="Test Action")
    def my_action(target: str, dictation_box=None):
        executed_log.append((target, "executed"))
        return True

    executor = CommandExecutor()
    assert executor.execute_command("test custom action", target="box")
    assert len(executed_log) == 1
    assert executed_log[0] == ("box", "executed")


def test_bracketed_command_lexer_recognition():
    lexer = DragonLexer()

    # STT outputs bracketed text like "[next field]" or "[scratch that]"
    actions = lexer.process_transcription("Assessment heart failure [next field] plan Lasix")
    types = [a.action_type for a in actions]
    triggers = [a.trigger for a in actions if a.action_type == "COMMAND_TRIGGERED"]

    assert "COMMAND_TRIGGERED" in types
    assert "next field" in triggers


def test_speech_interruption_sequential_field_jump(qapp):
    executor = CommandExecutor()
    box = DictationBoxWidget()
    box.show()

    # Template with two bracket fields
    box.text_edit.setPlainText("Assessment: [***] Plan: [***]")
    box.text_edit.moveCursor(box.text_edit.textCursor().MoveOperation.Start)

    # 1. First "next field" jumps into Assessment
    executor.execute_command("next field", target="box", dictation_box=box)
    assert box.text_edit.textCursor().selectedText() == "[***]"

    # 2. Dictate assessment
    box.insert_at_cursor("Acute heart failure.")
    assert "Assessment: Acute heart failure. Plan: [***]" in box.text_edit.toPlainText()

    # 3. Second "next field" jumps into Plan
    executor.execute_command("next field", target="box", dictation_box=box)
    assert box.text_edit.textCursor().selectedText() == "[***]"

    # 4. Dictate plan
    box.insert_at_cursor("Lasix 40mg IV daily.")
    full = box.text_edit.toPlainText()
    assert "Assessment: Acute heart failure. Plan: Lasix 40mg IV daily." in full
    assert "[***]" not in full


def test_mid_sentence_comma_no_leading_space(qapp):
    box = DictationBoxWidget()
    box.show()
    box.text_edit.setPlainText("Patient presents with chest pain")
    box.text_edit.moveCursor(box.text_edit.textCursor().MoveOperation.End)

    # Insert comma
    box.insert_at_cursor(",")
    assert box.text_edit.toPlainText().endswith("pain,")
