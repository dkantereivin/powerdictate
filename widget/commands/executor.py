"""
Voice Command Execution Engine
==============================
Dispatches vocal navigation, template jumping, and text editing commands
to either the active OS window (via X11 XTest) or the Dictation Box.
Supports both YAML actions and custom Python handlers.
"""

import sys
import time
import logging
from typing import Optional, Dict

from widget.commands.registry import CommandRegistry, CommandDefinition

logger = logging.getLogger("widget.commands.executor")

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
        self.registry = CommandRegistry()
        self.x11_disp = None
        self.key_map = {}
        self._init_x11()

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

    def execute_command(self, trigger: str, target: str = "cursor", dictation_box=None) -> bool:
        """
        Executes the voice command on the specified target.
        Handles both built-in YAML actions and registered Python handlers.
        """
        cmd_def = self.registry.get_command(trigger)
        if not cmd_def:
            logger.warning(f"Command '{trigger}' not found in registry.")
            return False

        logger.info(f"Executing voice command '{cmd_def.name}' (action: {cmd_def.action}) -> target: {target}")

        # 1. Custom Python Handler (if registered)
        if cmd_def.handler is not None:
            try:
                return cmd_def.handler(target=target, dictation_box=dictation_box)
            except Exception as e:
                logger.error(f"Error in custom Python command '{cmd_def.name}': {e}")
                return False

        action_name = cmd_def.action

        # 2. Target: Dictation Box
        if target == "box" and dictation_box is not None:
            return self._execute_on_dictation_box(action_name, dictation_box, cmd_def)

        # 3. Target: Active OS Window
        return self._execute_on_active_window(action_name, cmd_def)

    def _execute_on_dictation_box(self, action: str, dictation_box, cmd_def: Optional[CommandDefinition] = None) -> bool:
        """Executes editing/navigation commands directly inside Dictation Box."""
        try:
            from PySide6.QtGui import QTextCursor, QTextDocument
            text_edit = dictation_box.text_edit

            if action == "insert_template":
                tpl = cmd_def.template_text if cmd_def else ""
                if tpl:
                    dictation_box.insert_template(tpl)
                    return True

            elif action == "insert_text" or (cmd_def and cmd_def.template_text):
                tpl = cmd_def.template_text if cmd_def else ""
                if tpl:
                    dictation_box.insert_at_cursor(tpl)
                    return True

            elif action == "tab_space":
                cursor = text_edit.textCursor()
                cursor.insertText("\t")
                text_edit.setTextCursor(cursor)
                return True

            elif action == "navigate_next_field":
                # Template jumping: Find next '[' bracket or '[***]' field
                cursor = text_edit.textCursor()
                doc = text_edit.document()
                found_cursor = doc.find("[", cursor)

                # Loop back to document start if no more brackets after cursor
                if found_cursor.isNull():
                    start_cursor = QTextCursor(doc)
                    found_cursor = doc.find("[", start_cursor)

                if not found_cursor.isNull():
                    close_cursor = doc.find("]", found_cursor)
                    if not close_cursor.isNull():
                        found_cursor.setPosition(close_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
                    text_edit.setTextCursor(found_cursor)
                    text_edit.ensureCursorVisible()
                    return True

            elif action == "navigate_first_field":
                return dictation_box.focus_first_field(from_pos=0)

            elif action == "navigate_prev_field":
                cursor = text_edit.textCursor()
                doc = text_edit.document()
                found_cursor = doc.find("[", cursor, QTextDocument.FindFlag.FindBackward)
                if not found_cursor.isNull():
                    close_cursor = doc.find("]", found_cursor)
                    if not close_cursor.isNull():
                        found_cursor.setPosition(close_cursor.position(), QTextCursor.MoveMode.KeepAnchor)
                    text_edit.setTextCursor(found_cursor)
                    text_edit.ensureCursorVisible()
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

            elif action == "new_line":
                cursor = text_edit.textCursor()
                cursor.insertText("\n")
                text_edit.setTextCursor(cursor)
                return True

            elif action == "new_paragraph":
                cursor = text_edit.textCursor()
                cursor.insertText("\n\n")
                text_edit.setTextCursor(cursor)
                return True

        except Exception as e:
            logger.error(f"Error executing command on Dictation Box: {e}")

        return False

    def _execute_on_active_window(self, action: str, cmd_def: Optional[CommandDefinition] = None) -> bool:
        """Executes key combinations into active OS focused window."""
        if action in ("insert_template", "insert_text") or (cmd_def and cmd_def.template_text):
            tpl = cmd_def.template_text if cmd_def else ""
            if tpl:
                from widget.injector import InputInjector
                return InputInjector().inject_text(tpl)

        if self.x11_disp is not None:
            try:
                import Xlib.X
                import Xlib.ext.xtest

                if action in ("navigate_next_field", "tab_space"):
                    self._press_key('Tab')
                    return True

                elif action == "navigate_prev_field":
                    self._press_hotkey('Shift_L', 'Tab')
                    return True

                elif action == "navigate_first_field":
                    self._press_hotkey('Control_L', 'Home')
                    time.sleep(0.02)
                    self._press_key('Tab')
                    return True

                elif action == "undo":
                    self._press_hotkey('Control_L', 'z')
                    return True

                elif action == "select_all":
                    self._press_hotkey('Control_L', 'a')
                    return True

                elif action == "clear_field":
                    self._press_hotkey('Control_L', 'a')
                    time.sleep(0.02)
                    self._press_key('BackSpace')
                    return True

                elif action == "cursor_end":
                    self._press_key('End')
                    return True

                elif action == "cursor_start":
                    self._press_key('Home')
                    return True

                elif action == "new_line":
                    self._press_key('Return')
                    return True

                elif action == "new_paragraph":
                    self._press_key('Return')
                    time.sleep(0.01)
                    self._press_key('Return')
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
                elif action == "new_line":
                    pyautogui.press('enter')
                elif action == "new_paragraph":
                    pyautogui.press('enter')
                    pyautogui.press('enter')
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
            time.sleep(0.015)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyRelease, code)
            self.x11_disp.flush()
            time.sleep(0.015)

    def _press_hotkey(self, mod_name: str, key_name: str):
        mod_code = self.key_map.get(mod_name)
        key_code = self.key_map.get(key_name)
        if mod_code and key_code and self.x11_disp:
            import Xlib.X
            import Xlib.ext.xtest
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyPress, mod_code)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyPress, key_code)
            self.x11_disp.flush()
            time.sleep(0.015)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyRelease, key_code)
            Xlib.ext.xtest.fake_input(self.x11_disp, Xlib.X.KeyRelease, mod_code)
            self.x11_disp.flush()
            time.sleep(0.015)
