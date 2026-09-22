"""
Voice Command Execution Engine
==============================
Dispatches vocal navigation, template jumping, and text editing commands
to either the active OS window (via X11 XTest) or the Dictation Box.
"""

import sys
import time
import logging
import yaml
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger("widget.commands")

COMMANDS_YAML = Path(__file__).resolve().parent.parent.parent / "rules" / "commands.yaml"

# Try initializing X11 XTest for active window hardware keypresses
HAS_XTEST = False
try:
    if sys.platform.startswith("linux"):
        import Xlib.display
        import Xlib.X
        import Xlib.XK
        import Xlib.ext.xtest
        disp_test = Xlib.display.Display()
        if disp_test.has_extension('XTEST'):
            HAS_XTEST = True
except Exception:
    HAS_XTEST = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except Exception:
    HAS_PYAUTOGUI = False


class CommandExecutor:
    """
    Executes voice commands across active OS applications or the Dictation Box.
    """

    def __init__(self):
        self.commands_def: Dict[str, dict] = {}
        self.x11_disp = None
        self.key_map = {}
        self._init_x11()
        self.load_commands()

    def _init_x11(self):
        if HAS_XTEST:
            try:
                self.x11_disp = Xlib.display.Display()
                for key_name in ['Tab', 'BackSpace', 'Return', 'Home', 'End', 'Control_L', 'Shift_L', 'a', 'z']:
                    sym = Xlib.XK.string_to_keysym(key_name)
                    self.key_map[key_name] = self.x11_disp.keysym_to_keycode(sym)
                logger.info("X11 XTest Command Executor initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize X11 keycodes: {e}")

    def load_commands(self):
        """Loads command mappings from rules/commands.yaml."""
        if COMMANDS_YAML.exists():
            try:
                with open(COMMANDS_YAML, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.commands_def = data.get("commands", {})
                    logger.info(f"Loaded {len(self.commands_def)} voice commands from YAML.")
            except Exception as e:
                logger.error(f"Error loading commands YAML: {e}")

    def execute_command(self, trigger: str, target: str = "cursor", dictation_box=None) -> bool:
        """
        Executes the voice command on the specified target.
        """
        clean_trigger = trigger.lower().strip()
        cmd_info = self.commands_def.get(clean_trigger)
        if not cmd_info:
            logger.warning(f"Command '{clean_trigger}' not found in registry.")
            return False

        action_name = cmd_info.get("action", "")
        logger.info(f"Executing voice command '{cmd_info.get('name')}' (action: {action_name}) -> target: {target}")

        # Target 1: Dictation Box
        if target == "box" and dictation_box is not None and dictation_box.isVisible():
            return self._execute_on_dictation_box(action_name, dictation_box)

        # Target 2: Active OS Window
        return self._execute_on_active_window(action_name)

    def _execute_on_dictation_box(self, action: str, dictation_box) -> bool:
        """Executes editing/navigation commands directly inside Dictation Box."""
        try:
            from PySide6.QtGui import QTextCursor, QTextDocument
            text_edit = dictation_box.text_edit

            if action == "navigate_next_field":
                # Template jumping: Find next '[' bracket or '[***]' field
                cursor = text_edit.textCursor()
                doc = text_edit.document()
                found_cursor = doc.find("[", cursor)
                if not found_cursor.isNull():
                    # Check for closing bracket ']'
                    close_cursor = doc.find("]", found_cursor)
                    if not close_cursor.isNull():
                        found_cursor.setPosition(close_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
                    text_edit.setTextCursor(found_cursor)
                    return True

            elif action == "navigate_prev_field":
                cursor = text_edit.textCursor()
                doc = text_edit.document()
                found_cursor = doc.find("[", cursor, QTextDocument.FindFlag.FindBackward)
                if not found_cursor.isNull():
                    text_edit.setTextCursor(found_cursor)
                    return True

            elif action == "undo":
                text_edit.undo()
                return True

            elif action == "select_all":
                text_edit.selectAll()
                return True

            elif action == "clear_field":
                text_edit.clear()
                return True

            elif action == "cursor_end":
                text_edit.moveCursor(QTextCursor.MoveOperation.End)
                return True

            elif action == "cursor_start":
                text_edit.moveCursor(QTextCursor.MoveOperation.Start)
                return True

        except Exception as e:
            logger.error(f"Error executing command on Dictation Box: {e}")

        return False

    def _execute_on_active_window(self, action: str) -> bool:
        """Executes key combinations into active OS focused window."""
        if self.x11_disp is not None:
            try:
                import Xlib.X
                import Xlib.ext.xtest

                if action == "navigate_next_field":
                    self._press_key('Tab')
                    return True

                elif action == "navigate_prev_field":
                    self._press_hotkey('Shift_L', 'Tab')
                    return True

                elif action == "undo":
                    self._press_hotkey('Control_L', 'z')
                    return True

                elif action == "select_all":
                    self._press_hotkey('Control_L', 'a')
                    return True

                elif action == "clear_field":
                    self._press_hotkey('Control_L', 'a')
                    time.sleep(0.01)
                    self._press_key('BackSpace')
                    return True

                elif action == "cursor_end":
                    self._press_key('End')
                    return True

                elif action == "cursor_start":
                    self._press_key('Home')
                    return True

            except Exception as e:
                logger.error(f"XTest execution error: {e}")

        # Fallback PyAutoGUI
        if HAS_PYAUTOGUI:
            try:
                if action == "navigate_next_field":
                    pyautogui.press('tab')
                elif action == "navigate_prev_field":
                    pyautogui.hotkey('shift', 'tab')
                elif action == "undo":
                    pyautogui.hotkey('ctrl', 'z')
                elif action == "select_all":
                    pyautogui.hotkey('ctrl', 'a')
                elif action == "clear_field":
                    pyautogui.hotkey('ctrl', 'a')
                    pyautogui.press('backspace')
                elif action == "cursor_end":
                    pyautogui.press('end')
                elif action == "cursor_start":
                    pyautogui.press('home')
                return True
            except Exception as e:
                logger.error(f"PyAutoGUI command error: {e}")

        return False

    def _press_key(self, key_name: str):
        code = self.key_map.get(key_name)
        if code and self.x11_disp:
            import Xlib.X
            import Xlib.ext.xtest
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyPress, code)
            self.x11_disp.flush()
            time.sleep(0.01)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyRelease, code)
            self.x11_disp.flush()
            time.sleep(0.01)

    def _press_hotkey(self, mod_name: str, key_name: str):
        mod_code = self.key_map.get(mod_name)
        key_code = self.key_map.get(key_name)
        if mod_code and key_code and self.x11_disp:
            import Xlib.X
            import Xlib.ext.xtest
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyPress, mod_code)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyPress, key_code)
            self.x11_disp.flush()
            time.sleep(0.01)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyRelease, key_code)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyRelease, mod_code)
            self.x11_disp.flush()
            time.sleep(0.01)
