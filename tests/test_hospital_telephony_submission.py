"""
Unit Tests for Hospital Telephony Submission & Call Flow Templates
==================================================================
Tests:
1. Hospital line configuration (1-800 number, provider ID, site number, work type).
2. Standardized variable resolution in call flow templates.
3. VoIPMsClient configuration and simulated dialing fallback.
4. PatientInfoDialog work_type default (001) and custom overrides.
5. DictationExportWorker step-by-step call flow sequence dispatch.
"""

import pytest
from PySide6.QtWidgets import QApplication

from widget.setup_config import DictationSetupConfig, DEFAULT_CALL_FLOW
from tts.telephony.voip_client import VoIPMsClient
from widget.ui.patient_info_dialog import PatientInfoDialog
from widget.dictation_export_worker import DictationExportWorker


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_hospital_telephony_config_loading():
    """Verifies that hospital phone number, provider number, site number, and work type are loaded."""
    config = DictationSetupConfig.load()

    assert config.hospital_phone_number is not None
    assert len(config.hospital_phone_number) >= 10
    assert config.provider_number == "6740"
    assert config.site_number == "01"
    assert config.work_type == "001"
    assert config.voip_server == "toronto.voip.ms"
    assert len(config.call_flow_template) >= 10


def test_call_flow_template_variable_resolution():
    """
    Verifies that standardized variables:
      {{hospital_phone_number}}
      {{provider_number}}
      {{site_number}}
      {{work_type}}
      {{patient_mrn}}
    are accurately resolved into executable telephone actions.
    """
    config = DictationSetupConfig(
        hospital_phone_number="18005551234",
        provider_number="6740",
        site_number="01",
        work_type="001"
    )

    steps = config.resolve_call_flow(
        patient_name="Jane Doe",
        mrn="9876543",
        work_type="002"  # Custom work type override
    )

    # 1. Dial hospital line
    assert steps[0]["action"] == "dial"
    assert steps[0]["number"] == "18005551234"

    # 2. Wait 3s
    assert steps[1]["action"] == "wait"
    assert steps[1]["seconds"] == 3.0

    # 3. Provider number DTMF + #
    assert steps[2]["action"] == "dtmf"
    assert steps[2]["tones"] == "6740#"

    # 4. Site number DTMF + #
    assert steps[4]["action"] == "dtmf"
    assert steps[4]["tones"] == "01#"

    # 5. Work type DTMF + # (resolved with custom 002)
    assert steps[6]["action"] == "dtmf"
    assert steps[6]["tones"] == "002#"

    # 6. Patient MRN DTMF + #
    assert steps[8]["action"] == "dtmf"
    assert steps[8]["tones"] == "9876543#"

    # 7. Dictate Now trigger
    assert steps[10]["action"] == "dictate_now"

    # 8. Concluding '#'
    assert steps[12]["action"] == "dtmf"
    assert steps[12]["tones"] == "#"

    # 9. Hangup
    assert steps[14]["action"] == "hangup"


def test_voip_ms_client_configuration_and_simulation():
    """Verifies that VoIPMsClient gracefully operates in simulation mode when credentials are blank."""
    client = VoIPMsClient(server="toronto.voip.ms", username="", password="")
    assert client.is_configured is False
    assert client.connect() is False

    # Dial in simulation mode returns True
    assert client.dial("18005551234") is True

    # Send DTMF in simulation mode runs cleanly
    client.send_dtmf("6740#")
    client.hangup()
    client.disconnect()


def test_patient_info_dialog_work_type(qapp):
    """Verifies that PatientInfoDialog defaults work type to '001' and allows customization."""
    config = DictationSetupConfig(work_type="001", hospital_phone_number="18005551234", site_number="01")
    dialog = PatientInfoDialog(config=config)

    assert dialog.work_type == "001"

    # Override work type
    dialog.wt_edit.setText("004")
    assert dialog.work_type == "004"

    dialog.name_edit.setText("Arthur Pendelton")
    dialog.mrn_edit.setText("5544332")

    assert dialog.patient_name == "Arthur Pendelton"
    assert dialog.mrn == "5544332"
