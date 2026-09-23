"""
Interactive Screen Snipper & Clipboard Image Grabber
====================================================
Provides zero-friction capture pathways across both Wayland and X11:
1. WaylandPortalSnipper: Uses XDG Desktop Portal (org.freedesktop.portal.Screenshot)
   for native, high-performance interactive snipping on modern Linux (GNOME / KDE / Wayland).
   Avoids full-screen black/dark overlay freezing caused by Wayland framebuffer isolation.
2. X11OverlaySnipper: Translucent interactive crosshair overlay for traditional X11 desktops.
3. ClipboardGrabber: Instant 1-click ingestion of images already on clipboard
   (from OS shortcuts PrintScreen, Win+Shift+S, Spectacle, Gnome Screenshot, etc.).
"""

import os
import io
import logging
from typing import Optional

from PIL import Image
from PySide6.QtCore import (
    Qt, QObject, QPoint, QRect, QUrl, Signal, Slot, SLOT
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QCursor, QGuiApplication,
    QPixmap, QImage
)
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

logger = logging.getLogger("widget.ocr.capture")


def is_wayland_session() -> bool:
    """Returns True if the current desktop session is running on Wayland."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    return session_type == "wayland" or bool(wayland_display)


def qimage_to_pil(qimage: QImage) -> Image.Image:
    """Converts a PySide6 QImage to a PIL Image."""
    buffer = io.BytesIO()
    qimage.save(buffer, "PNG")
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


class WaylandPortalSnipper(QObject):
    """
    Invokes the native Linux Wayland screenshot portal (org.freedesktop.portal.Screenshot)
    with interactive area selection.
    """

    snip_completed = Signal(object)  # Emits PIL.Image
    snip_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = QDBusConnection.sessionBus()
        self._active_handle: Optional[str] = None

    def start_snip(self):
        try:
            iface = QDBusInterface(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Screenshot",
                self._bus
            )
            if not iface.isValid():
                logger.error("XDG Desktop Portal Screenshot interface is not available.")
                self.snip_cancelled.emit()
                return

            # Request interactive screenshot from compositor
            msg = iface.call("Screenshot", "", {"interactive": True})
            if msg.type() == QDBusMessage.MessageType.ErrorMessage:
                logger.error(f"Portal Screenshot error: {msg.errorMessage()}")
                self.snip_cancelled.emit()
                return

            args = msg.arguments()
            if not args:
                self.snip_cancelled.emit()
                return

            handle = args[0].path() if hasattr(args[0], "path") else str(args[0])
            self._active_handle = handle

            # Listen for portal Response signal
            connected = self._bus.connect(
                "org.freedesktop.portal.Desktop",
                handle,
                "org.freedesktop.portal.Request",
                "Response",
                self,
                SLOT("on_response(uint,QVariantMap)")
            )
            if not connected:
                logger.warning(f"Could not connect to portal Response signal on {handle}")

        except Exception as e:
            logger.error(f"Error starting Wayland portal snip: {e}", exc_info=True)
            self.snip_cancelled.emit()

    @Slot("unsigned int", "QVariantMap")
    def on_response(self, code: int, results: dict):
        # Disconnect listener
        if self._active_handle:
            self._bus.disconnect(
                "org.freedesktop.portal.Desktop",
                self._active_handle,
                "org.freedesktop.portal.Request",
                "Response",
                self,
                SLOT("on_response(uint,QVariantMap)")
            )
            self._active_handle = None

        if code == 0:
            uri = results.get("uri", "")
            if isinstance(uri, str) and uri:
                file_path = QUrl(uri).toLocalFile()
                if file_path and os.path.exists(file_path):
                    try:
                        with Image.open(file_path) as opened:
                            img = opened.convert("RGB")
                        # Attach the temporary file path so the OCR service deletes it after parsing completes
                        img._source_file_path = file_path
                        logger.info(f"Loaded screenshot from portal: {file_path}")
                        self.snip_completed.emit(img)
                        return
                    except Exception as e:
                        logger.error(f"Failed to open portal screenshot image from {file_path}: {e}")
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except Exception:
                                pass

        logger.info("Wayland portal snip was cancelled or empty.")
        self.snip_cancelled.emit()


class X11OverlaySnipper(QWidget):
    """
    Full-screen translucent overlay for traditional X11 desktops.
    """

    snip_completed = Signal(object)  # Emits PIL.Image
    snip_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos = QPoint()
        self._current_pos = QPoint()
        self._is_selecting = False
        self._background_pixmap = QPixmap()

    def start_snip(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            self.snip_cancelled.emit()
            return

        self._background_pixmap = screen.grabWindow(0)
        # CRITICAL: If grabWindow returned null (e.g. on Wayland), do NOT show the black/blue overlay
        if self._background_pixmap.isNull():
            logger.warning("grabWindow(0) returned null; screen capture not supported via overlay.")
            self.snip_cancelled.emit()
            return

        geo = screen.geometry()
        self.setGeometry(geo)
        self._is_selecting = False
        self._start_pos = QPoint()
        self._current_pos = QPoint()

        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)

        # 1. Draw captured background image
        if not self._background_pixmap.isNull():
            painter.drawPixmap(0, 0, self._background_pixmap)

        # 2. Draw dark semi-translucent scrim
        painter.fillRect(self.rect(), QColor(15, 23, 42, 140))

        # 3. Draw active selection rectangle if dragging
        if self._is_selecting:
            selection_rect = QRect(self._start_pos, self._current_pos).normalized()
            if selection_rect.width() > 2 and selection_rect.height() > 2:
                # Clear scrim inside selection to reveal underlying crisp image
                painter.drawPixmap(
                    selection_rect,
                    self._background_pixmap,
                    selection_rect
                )

                # Crisp cyan highlight border
                pen = QPen(QColor("#38bdf8"), 2, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.setBrush(QColor(56, 189, 248, 30))
                painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self._is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            selection_rect = QRect(self._start_pos, self._current_pos).normalized()
            self.hide()

            if selection_rect.width() >= 10 and selection_rect.height() >= 10:
                cropped = self._background_pixmap.copy(selection_rect)
                qimg = cropped.toImage()
                pil_img = qimage_to_pil(qimg)
                self.snip_completed.emit(pil_img)
            else:
                self.snip_cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        super().keyPressEvent(event)

    def _cancel(self):
        self._is_selecting = False
        self.hide()
        self.snip_cancelled.emit()


class ScreenSnipper(QObject):
    """
    Unified Screen Snipper that automatically dispatches to WaylandPortalSnipper
    or X11OverlaySnipper depending on the host display server environment.
    """

    snip_completed = Signal(object)  # Emits PIL.Image
    snip_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wayland_snipper: Optional[WaylandPortalSnipper] = None
        self._x11_snipper: Optional[X11OverlaySnipper] = None

        if is_wayland_session():
            self._wayland_snipper = WaylandPortalSnipper(self)
            self._wayland_snipper.snip_completed.connect(self.snip_completed.emit)
            self._wayland_snipper.snip_cancelled.connect(self.snip_cancelled.emit)
        else:
            self._x11_snipper = X11OverlaySnipper(None)
            self._x11_snipper.snip_completed.connect(self.snip_completed.emit)
            self._x11_snipper.snip_cancelled.connect(self.snip_cancelled.emit)

    def start_snip(self):
        """Starts interactive screen region snip."""
        if is_wayland_session() and self._wayland_snipper:
            self._wayland_snipper.start_snip()
        elif self._x11_snipper:
            self._x11_snipper.start_snip()
        else:
            self.snip_cancelled.emit()


class ClipboardGrabber:
    """Helper to inspect and grab images from the system clipboard."""

    @staticmethod
    def get_clipboard_image() -> Optional[Image.Image]:
        clipboard = QApplication.clipboard()
        qimage = clipboard.image()
        if not qimage.isNull():
            return qimage_to_pil(qimage)

        # Check pixmap fallback
        pixmap = clipboard.pixmap()
        if not pixmap.isNull():
            return qimage_to_pil(pixmap.toImage())

        return None
