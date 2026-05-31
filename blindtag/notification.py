"""
blindtag.notification
====================
Bottom-right corner notification for background monitoring posture.

Shown when ``BlindTagWindow`` is hidden and the clipboard watcher detects a
payload. Clicking the body reopens the main window; the ``×`` button
dismisses silently. In persistent mode, the notification remains visible as a
click-to-relaunch anchor until dismissed or replaced.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QMainWindow

NOTIFY_MARGIN_PX: int = 16
CLOSE_BTN_TEXT: str = "×"

# Style constants — kept local so notification.py has zero import dependency on
# widget.py's colour tokens (avoids circular import).
_BG         = "#10161f"
_BORDER     = "#263546"
_TEXT       = "#edf2f7"
_MUTED      = "#9aa9bc"
_ACCENT     = "#3dd5f3"


class NotificationWidget(QWidget):
    """
    Single-instance, single-use corner notification owned by ``BlindTagWindow``.

    Usage::

        notif = NotificationWidget(main_win, duration_ms=4500)
        notif.show_for("hello, world…")
    """

    def __init__(self, main_win: "QMainWindow", duration_ms: int) -> None:
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self._main_win = main_win
        self._duration_ms = duration_ms
        self._persistent = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QWidget {{ background-color: {_BG}; border: 1px solid {_BORDER}; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        self._label = QLabel("BlindTag — Payload detected")
        self._label.setStyleSheet(
            f"color: {_TEXT}; font-size: 9pt; background: transparent; border: none;"
        )

        self._close_btn = QPushButton(CLOSE_BTN_TEXT)
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setFlat(True)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ color: {_MUTED}; background: transparent; border: none; font-size: 11pt; }}"
            f"QPushButton:hover {{ color: {_TEXT}; }}"
        )
        self._close_btn.clicked.connect(self.hide)

        layout.addWidget(self._label, stretch=1)
        layout.addWidget(self._close_btn)
        self.adjustSize()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_for(self, preview: str, persistent: bool = False) -> None:
        """Display notification with *preview* text.

        When *persistent* is True, the notification remains visible until the
        user dismisses it or a later notification replaces it.
        """
        self._persistent = persistent
        self._label.setText(f"\u2b21  BlindTag  \u00b7  {preview}")
        self.adjustSize()
        self._reposition()
        if self._persistent:
            self._timer.stop()
        else:
            self._timer.start(self._duration_ms)
        self.show()
        self.raise_()

    # ------------------------------------------------------------------
    # Positioning
    # ------------------------------------------------------------------

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.right() - self.width() - NOTIFY_MARGIN_PX,
            geo.bottom() - self.height() - NOTIFY_MARGIN_PX,
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """Body click — dismiss and restore main window."""
        self.hide()
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        """Hovering over the notification pauses auto-dismiss."""
        if not self._persistent:
            self._timer.stop()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        """Leaving restarts the full auto-dismiss timer."""
        if not self._persistent:
            self._timer.start(self._duration_ms)
