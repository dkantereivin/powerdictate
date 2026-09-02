import time
import pytest
from PySide6.QtWidgets import QApplication
from widget.controller import DictationController, DictationState
from widget.config import WidgetConfig

# Initialize Qt App fixture
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dictation_controller_toggle_flow(qapp):
    config = WidgetConfig(hotkey_mode="toggle")
    controller = DictationController(config)
    assert controller.state == DictationState.IDLE

    # 1. Toggle ON
    controller.toggle()
    assert controller.state == DictationState.RECORDING

    time.sleep(0.2)

    # 2. Toggle OFF
    saved_path = controller.stop_recording()
    assert controller.state == DictationState.IDLE
    if saved_path and saved_path.exists():
        saved_path.unlink()


def test_dictation_controller_ptt_flow(qapp):
    config = WidgetConfig(hotkey_mode="ptt")
    controller = DictationController(config)
    assert controller.state == DictationState.IDLE

    # 1. Press PTT (Down)
    controller.ptt_press()
    assert controller.state == DictationState.RECORDING

    time.sleep(0.2)

    # 2. Release PTT (Up)
    controller.ptt_release()
    assert controller.state == DictationState.IDLE
