"""
PowerDictate Medical Companion Widget Entrypoint
================================================
"""

import sys
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
