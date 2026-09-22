"""
Cross-Platform Global Hotkey Listener (XWayland, Linux, Windows)
==============================================================
Listens for:
- Right Control & F8: Dictation Start/Stop
- Ctrl + D: Toggle Dictation Box (switches target between Cursor & Box)
"""

import sys
import threading
import logging
from typing import Callable, Optional

logger = logging.getLogger("widget.hotkey")

try:
    import evdev
    from evdev import ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False

try:
    from pynput import keyboard as pynput_kb
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


class GlobalHotkeyManager:
    """
    Direct hardware keyboard listener for Right Control, F8, and Ctrl+D.
    """

    def __init__(
        self,
        hotkey_name: str = "ctrl_r",
        hotkey_mode: str = "toggle",
        on_toggle: Optional[Callable[[], None]] = None,
        on_ptt_press: Optional[Callable[[], None]] = None,
        on_ptt_release: Optional[Callable[[], None]] = None,
        on_toggle_box: Optional[Callable[[], None]] = None,
    ):
        self.hotkey_name = hotkey_name.lower().strip()
        self.hotkey_mode = hotkey_mode.lower().strip()
        self.on_toggle = on_toggle or (lambda: None)
        self.on_ptt_press = on_ptt_press or (lambda: None)
        self.on_ptt_release = on_ptt_release or (lambda: None)
        self.on_toggle_box = on_toggle_box or (lambda: None)

        self.is_running = False
        self.ctrl_held = False
        self._thread = None

    def start(self) -> bool:
        """Starts the global hotkey listener thread."""
        self.is_running = True
        started = False

        if HAS_EVDEV and sys.platform.startswith("linux"):
            started = self._start_evdev_listener()

        if not started and HAS_PYNPUT:
            started = self._start_pynput_listener()

        return started

    def stop(self) -> None:
        """Stops listener."""
        self.is_running = False

    def _start_evdev_listener(self) -> bool:
        """Binds to the primary keyboard evdev device."""
        try:
            device_paths = evdev.list_devices()
            target_device = None

            for path in device_paths:
                try:
                    dev = evdev.InputDevice(path)
                    caps = dev.capabilities()
                    if ecodes.EV_KEY in caps:
                        keys = caps[ecodes.EV_KEY]
                        if ecodes.KEY_RIGHTCTRL in keys and ecodes.KEY_A in keys:
                            if "keyboard" in dev.name.lower():
                                target_device = dev
                                break
                            elif target_device is None:
                                target_device = dev
                except Exception:
                    continue

            if not target_device:
                logger.warning("No evdev keyboard found.")
                return False

            logger.info(f"Binding global hotkey directly to {target_device.name} ({target_device.path})")

            self._thread = threading.Thread(target=self._evdev_loop, args=(target_device,), daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            logger.warning(f"Failed to start evdev listener: {e}")
            return False

    def _evdev_loop(self, device):
        """Reads raw input events from keyboard."""
        try:
            for event in device.read_loop():
                if not self.is_running:
                    break

                if event.type == ecodes.EV_KEY:
                    # Track Ctrl modifier state
                    if event.code in (ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL):
                        self.ctrl_held = (event.value > 0)

                    # 1. Ctrl + D Combination -> Toggle Dictation Box
                    if event.code == ecodes.KEY_D and event.value == 1 and self.ctrl_held:
                        logger.info("Hotkey triggered: Ctrl+D (Toggle Dictation Box)")
                        self.on_toggle_box()
                        continue

                    # 2. Right Control -> Dictate
                    if event.code == ecodes.KEY_RIGHTCTRL:
                        if event.value == 1:  # Down
                            if self.hotkey_mode == "ptt":
                                self.on_ptt_press()
                            else:
                                self.on_toggle()
                        elif event.value == 0:  # Up
                            if self.hotkey_mode == "ptt":
                                self.on_ptt_release()

                    # 3. F8 -> Dictate
                    elif event.code == ecodes.KEY_F8 and event.value == 1:
                        if self.hotkey_mode == "ptt":
                            self.on_ptt_press()
                        else:
                            self.on_toggle()

        except Exception as e:
            logger.debug(f"evdev loop ended for {device.name}: {e}")

    def _start_pynput_listener(self) -> bool:
        """Fallback pynput listener with Ctrl+D support."""
        current_keys = set()

        def on_press(key):
            current_keys.add(key)
            try:
                # Check Ctrl+D
                is_ctrl = any(k in current_keys for k in [pynput_kb.Key.ctrl, pynput_kb.Key.ctrl_l, pynput_kb.Key.ctrl_r])
                is_d = any(hasattr(k, 'char') and k.char and k.char.lower() == 'd' for k in current_keys)

                if is_ctrl and is_d:
                    self.on_toggle_box()
                    return

                k_name = key.name.lower() if hasattr(key, 'name') else ''
                if k_name in ("ctrl_r", "f8"):
                    if self.hotkey_mode == "ptt":
                        self.on_ptt_press()
                    else:
                        self.on_toggle()
            except Exception:
                pass

        def on_release(key):
            try:
                current_keys.discard(key)
                k_name = key.name.lower() if hasattr(key, 'name') else ''
                if k_name in ("ctrl_r", "f8"):
                    if self.hotkey_mode == "ptt":
                        self.on_ptt_release()
            except Exception:
                pass

        try:
            listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            logger.info("Pynput listener started with Ctrl+D.")
            return True
        except Exception as e:
            logger.warning(f"Pynput listener error: {e}")
            return False
