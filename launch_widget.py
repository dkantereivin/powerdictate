#!/usr/bin/env python3
"""
PowerDictate Medical Companion Widget Launcher
==============================================
Forces XWayland (QT_QPA_PLATFORM=xcb) for full Always-On-Top stacking
and seamless desktop overlay compatibility.
"""

import os
import sys

# Force XWayland / X11 platform backend for true Always-On-Top stacking
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["GDK_BACKEND"] = "x11"

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PySide6.QtWidgets import QApplication
from widget.ui.pill_widget import FloatingPillWidget


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PowerDictate Medical Companion")
    widget = FloatingPillWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
