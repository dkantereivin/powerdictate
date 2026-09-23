import pytest
from PySide6.QtWidgets import QApplication
from widget.templates.parser import TemplateParser, FieldType
from widget.ui.dictation_box import DictationBoxWidget
from widget.commands.executor import CommandExecutor


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def box(qapp):
    widget = DictationBoxWidget()
    yield widget
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


def test_template_parser_syntax():
    # 1. Wildcard
    f1 = TemplateParser.parse_field_string("[***]")
    assert f1 is not None
    assert f1.field_type == FieldType.WILDCARD
    assert not f1.has_default
    assert not f1.is_choice

    # 2. Single Default
    f2 = TemplateParser.parse_field_string("[No]")
    assert f2 is not None
    assert f2.field_type == FieldType.DEFAULT
    assert f2.has_default
    assert f2.default_value == "No"
    assert not f2.is_choice

    # 3. Binary Picklist with Default
    f3 = TemplateParser.parse_field_string("[No/Yes]")
    assert f3 is not None
    assert f3.field_type == FieldType.PICKLIST
    assert f3.has_default
    assert f3.default_value == "No"
    assert f3.options == ["No", "Yes"]
    assert f3.is_choice

    # 4. Multi-choice Picklist
    f4 = TemplateParser.parse_field_string("[DOAC/LMWH/Warfarin]")
    assert f4 is not None
    assert f4.field_type == FieldType.PICKLIST
    assert f4.has_default
    assert f4.default_value == "DOAC"
    assert f4.is_choice

    # 5. Wildcard Picklist
    f5 = TemplateParser.parse_field_string("[***/DOAC/LMWH/Warfarin]")
    assert f5 is not None
    assert f5.field_type == FieldType.WILDCARD_PICKLIST
    assert not f5.has_default
    assert f5.default_value == ""
    assert f5.display_options == ["DOAC", "LMWH", "Warfarin"]
    assert f5.is_choice


def test_resolve_all_defaults():
    text = "[No] history of VTE. [No/Yes] anticoagulation with [***/DOAC/LMWH/Warfarin]. Diet: [2g sodium/Regular]."
    resolved, wildcards = TemplateParser.resolve_all_defaults(text)

    expected = "No history of VTE. No anticoagulation with [***]. Diet: 2g sodium."
    assert resolved == expected
    assert wildcards == 1


def test_dictation_box_default_acceptance_on_next_field(box):
    executor = CommandExecutor()
    box.text_edit.setPlainText("Assessment: [No/Yes] Plan: [***]")
    box.text_edit.moveCursor(box.text_edit.textCursor().MoveOperation.Start)

    # 1. Focus first field [No/Yes]
    assert box.navigate_next_field()
    assert box.text_edit.textCursor().selectedText() == "[No/Yes]"
    assert box.field_popup.isVisible()

    # 2. Next field accepts default 'No' and jumps to Plan [***]
    assert executor.execute_command("next field", target="box", dictation_box=box)
    assert "Assessment: No Plan: [***]" in box.text_edit.toPlainText()
    assert box.text_edit.textCursor().selectedText() == "[***]"
    assert not box.field_popup.isVisible()


def test_dictation_box_spoken_option_selection(box):
    box.text_edit.setPlainText("Anticoagulation: [No/Yes] with [DOAC/LMWH/Warfarin]")
    box.focus_first_field(from_pos=0)
    assert box.text_edit.textCursor().selectedText() == "[No/Yes]"
    assert box.field_popup.isVisible()

    # Say 'Yes' -> replaces [No/Yes] with 'Yes' and advances to [DOAC/LMWH/Warfarin]
    box.insert_at_cursor("Yes")
    assert "Anticoagulation: Yes with [DOAC/LMWH/Warfarin]" in box.text_edit.toPlainText()
    assert box.text_edit.textCursor().selectedText() == "[DOAC/LMWH/Warfarin]"
    assert box.field_popup.isVisible()

    # Say 'Warfarin' (case-insensitive) -> replaces and finishes
    box.insert_at_cursor("warfarin")
    assert box.text_edit.toPlainText() == "Anticoagulation: Yes with Warfarin"


def test_dictation_box_transfer_sweeper_skipped_defaults(box):
    # User typed or pasted template and manually clicked elsewhere, skipping fields
    box.text_edit.setPlainText("DVT: [No/Yes]. PE: [No]. Diet: [2g sodium/Cardiac]. Plan: [***]")
    box.text_edit.moveCursor(box.text_edit.textCursor().MoveOperation.End)

    # Transfer note
    box.transfer_text()

    # Text in box and clipboard should have all defaults resolved, leaving only [***]
    expected = "DVT: No. PE: No. Diet: 2g sodium. Plan: [***]"
    assert box.text_edit.toPlainText() == expected

    clipboard = QApplication.clipboard().text()
    assert clipboard == expected
    assert "unfilled" in box.transfer_btn.text().lower()


def test_field_popup_numeric_selection(box):
    box.text_edit.setPlainText("Medication: [DOAC/LMWH/Warfarin]")
    box.focus_first_field(from_pos=0)
    assert box.field_popup.isVisible()

    # Select index 2 (Warfarin)
    box.field_popup.select_index(2)
    assert box.text_edit.toPlainText() == "Medication: Warfarin"
    assert not box.field_popup.isVisible()
