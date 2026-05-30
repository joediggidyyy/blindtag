"""
blindtag.widget
===============
Low-profile desktop observer widget for rapid BlindTag encode/decode workflows.

Visual Identity
---------------
  Background (primary):  #121212  Matte Charcoal
  Surface (secondary):   #1E1E1E  Dark Gray
  Raised surface:        #252525  Card Gray
  Accent:                #4A90D9  Technical Blue
  Accent hover:          #5BA3F0  Blue Highlight
  Text (primary):        #E8E8E8  Near-White
  Text (muted):          #888888  Mid-Gray
  Success:               #4CAF6E  Confirmation Green
  Warning:               #E8A838  Amber Alert
  Error:                 #E85555  Alert Red

Panel Layout
------------
  ┌──────────────────────────────────────────┐
  │ ⬡ BlindTag                       ─   ✕  │  ← draggable title bar
  ├──────────────────────────────────────────┤
  │ [ Encode ] [ Decode ]     □ Clip Watch   │  ← segmented toggle
  ├──────────────────────────────────────────┤
  │                                          │
  │  [ANCHOR TEXT / RAW INPUT textbox]       │  ← main input area
  │  [HIDDEN PAYLOAD textbox]  (encode only) │
  │  [OUTPUT textbox]                        │
  │                                          │
  │  [ Encode ]  [ ⬡ Obfuscate & Copy ]     │  ← action row
  │             [ Clear All ]               │
  ├──────────────────────────────────────────┤
  │ Status message                        ●  │  ← status bar
  └──────────────────────────────────────────┘

Hotkeys
-------
  Ctrl+E       Switch to Encode panel
  Ctrl+D       Switch to Decode panel
  Ctrl+W       Toggle Clipboard Watcher
  Ctrl+Return  Execute primary action for active panel
  Escape       Close widget

Clipboard Watcher
-----------------
When active, the Qt clipboard dataChanged signal fires on every clipboard
update. If new content contains a Plane 14 tag payload, the widget surfaces
a notification overlay, switches to the Decode panel, and auto-populates the
output field. No data leaves the local machine.

Dependencies: PySide6 >= 6.8
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .core import decode, encode
from .exceptions import InvalidPayloadError

# ─── Asset paths ──────────────────────────────────────────────────────────────

_ASSETS_DIR = Path(__file__).parent.parent / "assets" / "images"

# ─── Colour palette ───────────────────────────────────────────────────────────

C_BG        = "#121212"   # Matte Charcoal  — window background
C_SECONDARY = "#1E1E1E"   # Dark Gray        — title bar, toggle strip, status bar
C_SURFACE   = "#252525"   # Card Gray        — read-only output fields
C_ACCENT    = "#4A90D9"   # Technical Blue   — primary CTA, watcher indicator
C_ACCENT_H  = "#5BA3F0"   # Blue Highlight   — hover state
C_TEXT      = "#E8E8E8"   # Near-White       — primary text
C_MUTED     = "#888888"   # Mid-Gray         — labels, hints, secondary text
C_SUCCESS   = "#4CAF6E"   # Confirmation Green
C_WARNING   = "#E8A838"   # Amber Alert
C_ERROR     = "#E85555"   # Alert Red

# ─── Timing ───────────────────────────────────────────────────────────────────

NOTIFY_DURATION_MS: int = 4_500  # Notification overlay auto-dismiss duration

# ─── Stylesheet helpers ───────────────────────────────────────────────────────

_APP_STYLESHEET = f"""
QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: "Segoe UI";
    font-size: 10pt;
}}
"""


def _textbox_style(color: str = C_TEXT, bg: str = C_SECONDARY) -> str:
    return (
        f"QTextEdit {{"
        f"background-color: {bg}; color: {color}; "
        f"border: 1px solid #303030; border-radius: 6px; "
        f"font-family: 'Courier New'; font-size: 11pt; padding: 4px;"
        f"}}"
    )


def _btn_primary_style() -> str:
    return (
        f"QPushButton {{"
        f"background-color: {C_ACCENT}; color: #FFFFFF; "
        f"font-weight: bold; border: none; border-radius: 6px; padding: 8px 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {C_ACCENT_H}; }}"
    )


def _btn_secondary_style() -> str:
    return (
        f"QPushButton {{"
        f"background-color: {C_SURFACE}; color: {C_TEXT}; "
        f"border: none; border-radius: 6px; padding: 8px 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: #333333; }}"
    )


def _btn_ghost_style() -> str:
    return (
        f"QPushButton {{"
        f"background-color: transparent; color: {C_MUTED}; "
        f"border: none; border-radius: 6px; font-size: 9pt; padding: 4px 8px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {C_SURFACE}; }}"
    )


def _toggle_active_style() -> str:
    return (
        f"QPushButton {{"
        f"background-color: {C_ACCENT}; color: #FFFFFF; "
        f"border: none; border-radius: 4px; padding: 6px 18px;"
        f"}}"
    )


def _toggle_inactive_style() -> str:
    return (
        f"QPushButton {{"
        f"background-color: {C_SURFACE}; color: {C_TEXT}; "
        f"border: none; border-radius: 4px; padding: 6px 18px;"
        f"}}"
        f"QPushButton:hover {{ background-color: #2C2C2C; }}"
    )


# ─── Title bar ────────────────────────────────────────────────────────────────

class _TitleBar(QWidget):
    """Custom draggable title bar."""

    def __init__(self, parent: "BlindTagWindow") -> None:
        super().__init__(parent)
        self._win = parent
        self._drag_pos = None
        self.setFixedHeight(40)
        self.setStyleSheet(f"background-color: {C_SECONDARY};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(4)

        # Logo icon (graceful fallback if file absent)
        logo_path = _ASSETS_DIR / "blindtag_logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaled(
                28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            lbl_icon = QLabel()
            lbl_icon.setPixmap(pix)
            lbl_icon.setFixedSize(28, 28)
            lbl_icon.setStyleSheet("background: transparent;")
            layout.addWidget(lbl_icon)

        # Title text
        lbl_title = QLabel("BlindTag")
        lbl_title.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 12pt; font-weight: bold; background: transparent;"
        )
        layout.addWidget(lbl_title)
        layout.addStretch()

        # Minimize button
        btn_min = QPushButton("─")
        btn_min.setFixedSize(30, 26)
        btn_min.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; border: none; }}"
            f"QPushButton:hover {{ background-color: {C_SURFACE}; }}"
        )
        btn_min.clicked.connect(parent.showMinimized)
        layout.addWidget(btn_min)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 26)
        btn_close.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; border: none; }}"
            f"QPushButton:hover {{ background-color: {C_ERROR}; color: white; }}"
        )
        btn_close.clicked.connect(parent.close)
        layout.addWidget(btn_close)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._win.move(self._win.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None


# ─── Main widget ──────────────────────────────────────────────────────────────

class BlindTagWindow(QMainWindow):
    """
    BlindTag observer widget — the primary user-facing interface.

    Instantiate via ``run_widget()`` or directly:

        app = QApplication(sys.argv)
        win = BlindTagWindow()
        win.show()
        sys.exit(app.exec())
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("BlindTag")
        self.setMinimumSize(480, 480)
        self.resize(530, 555)
        self.setWindowOpacity(0.96)

        icon_path = _ASSETS_DIR / "blindtag_logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Runtime state
        self._current_panel: str = "encode"
        self._watcher_active: bool = False
        self._notify_widget: Optional[QWidget] = None
        self._notify_timer = QTimer(self)
        self._notify_timer.setSingleShot(True)
        self._notify_timer.timeout.connect(self._dismiss_notify)

        # Build UI
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_TitleBar(self))
        root.addWidget(self._build_toggle_strip())

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._encode_panel = self._build_encode_panel()
        self._decode_panel = self._build_decode_panel()
        self._stack.addWidget(self._encode_panel)
        self._stack.addWidget(self._decode_panel)

        root.addWidget(self._build_status_bar())

        self._bind_hotkeys()
        self._show_encode()

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _build_toggle_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedHeight(46)
        strip.setStyleSheet(f"background-color: {C_SECONDARY};")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(6)

        self._btn_encode = QPushButton("  Encode  ")
        self._btn_encode.clicked.connect(self._show_encode)
        layout.addWidget(self._btn_encode)

        self._btn_decode = QPushButton("  Decode  ")
        self._btn_decode.clicked.connect(self._show_decode)
        layout.addWidget(self._btn_decode)

        layout.addStretch()

        self._watcher_chk = QCheckBox(" Clip Watch")
        self._watcher_chk.setStyleSheet(
            f"QCheckBox {{ color: {C_MUTED}; font-size: 9pt; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; "
            f"border: 1px solid {C_MUTED}; border-radius: 3px; background: transparent; }}"
            f"QCheckBox::indicator:checked {{ background-color: {C_ACCENT}; border-color: {C_ACCENT}; }}"
        )
        self._watcher_chk.stateChanged.connect(self._toggle_watcher)
        layout.addWidget(self._watcher_chk)

        return strip

    def _build_encode_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        layout.addWidget(self._section_label("ANCHOR TEXT  ·  visible cover"))
        self._anchor_input = self._make_textbox(82)
        layout.addWidget(self._anchor_input)

        layout.addWidget(self._section_label("HIDDEN PAYLOAD  ·  printable ASCII only"))
        self._hidden_input = self._make_textbox(68)
        layout.addWidget(self._hidden_input)

        layout.addWidget(self._section_label("OUTPUT  ·  steganographic composite"))
        self._encode_output = self._make_textbox(82, readonly=True)
        layout.addWidget(self._encode_output)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 4)
        row_layout.setSpacing(6)

        btn_encode = QPushButton("Encode")
        btn_encode.setStyleSheet(_btn_secondary_style())
        btn_encode.setFixedHeight(36)
        btn_encode.clicked.connect(self._do_encode)
        row_layout.addWidget(btn_encode)

        btn_obf = QPushButton("⬡  Obfuscate & Copy")
        btn_obf.setStyleSheet(_btn_primary_style())
        btn_obf.setFixedHeight(36)
        btn_obf.clicked.connect(self._encode_and_copy)
        row_layout.addWidget(btn_obf)

        layout.addWidget(row)

        btn_clear = QPushButton("Clear All")
        btn_clear.setStyleSheet(_btn_ghost_style())
        btn_clear.setFixedHeight(24)
        btn_clear.clicked.connect(self._clear_encode)
        layout.addWidget(btn_clear, alignment=Qt.AlignCenter)

        layout.addStretch()
        return panel

    def _build_decode_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        layout.addWidget(
            self._section_label("RAW TEXT INPUT  ·  paste steganographic content here")
        )
        self._raw_input = self._make_textbox(140)
        layout.addWidget(self._raw_input)

        layout.addWidget(self._section_label("EXTRACTED PAYLOAD"))
        self._decode_output = self._make_textbox(120, readonly=True)
        layout.addWidget(self._decode_output)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 4)
        row_layout.setSpacing(6)

        btn_decode = QPushButton("Decode")
        btn_decode.setStyleSheet(_btn_secondary_style())
        btn_decode.setFixedHeight(36)
        btn_decode.clicked.connect(self._do_decode)
        row_layout.addWidget(btn_decode)

        btn_paste = QPushButton("⬇  Paste & Decode")
        btn_paste.setStyleSheet(_btn_primary_style())
        btn_paste.setFixedHeight(36)
        btn_paste.clicked.connect(self._paste_and_decode)
        row_layout.addWidget(btn_paste)

        layout.addWidget(row)

        btn_clear = QPushButton("Clear All")
        btn_clear.setStyleSheet(_btn_ghost_style())
        btn_clear.setFixedHeight(24)
        btn_clear.clicked.connect(self._clear_decode)
        layout.addWidget(btn_clear, alignment=Qt.AlignCenter)

        layout.addStretch()
        return panel

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"background-color: {C_SECONDARY};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)

        self._status_label = QLabel(
            "Ready  ·  Ctrl+E: Encode  ·  Ctrl+D: Decode  ·  Ctrl+W: Watcher"
        )
        self._status_label.setStyleSheet(
            f"color: {C_MUTED}; font-size: 9pt; background: transparent;"
        )
        layout.addWidget(self._status_label)
        layout.addStretch()

        self._indicator = QLabel("●")
        self._indicator.setStyleSheet(
            f"color: {C_SURFACE}; font-size: 10pt; background: transparent;"
        )
        layout.addWidget(self._indicator)

        return bar

    # =========================================================================
    # Shared UI helpers
    # =========================================================================

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 9pt; "
            f"padding-top: 12px; padding-bottom: 3px; background: transparent;"
        )
        return lbl

    @staticmethod
    def _make_textbox(height: int, readonly: bool = False) -> QTextEdit:
        tb = QTextEdit()
        tb.setFixedHeight(height)
        tb.setReadOnly(readonly)
        bg = C_SURFACE if readonly else C_SECONDARY
        tb.setStyleSheet(_textbox_style(C_TEXT, bg))
        return tb

    # =========================================================================
    # Panel switching
    # =========================================================================

    def _show_encode(self) -> None:
        self._stack.setCurrentWidget(self._encode_panel)
        self._current_panel = "encode"
        self._btn_encode.setStyleSheet(_toggle_active_style())
        self._btn_decode.setStyleSheet(_toggle_inactive_style())

    def _show_decode(self) -> None:
        self._stack.setCurrentWidget(self._decode_panel)
        self._current_panel = "decode"
        self._btn_encode.setStyleSheet(_toggle_inactive_style())
        self._btn_decode.setStyleSheet(_toggle_active_style())

    # =========================================================================
    # Core actions
    # =========================================================================

    def _do_encode(self) -> None:
        anchor = self._anchor_input.toPlainText().strip()
        hidden = self._hidden_input.toPlainText().strip()

        if not anchor:
            self._set_status("⚠  Anchor text is required.", C_WARNING)
            return
        if not hidden:
            self._set_status("⚠  Hidden payload is required.", C_WARNING)
            return

        try:
            result = encode(anchor, hidden)
        except (InvalidPayloadError, ValueError) as exc:
            self._set_status(f"✕  {exc}", C_ERROR)
            return

        self._encode_output.setPlainText(result)
        self._set_status(
            f"✓  Encoded {len(hidden)} char payload into "
            f"{len(anchor)} char anchor  ({len(result)} total chars).",
            C_SUCCESS,
        )

    def _encode_and_copy(self) -> None:
        self._do_encode()
        result = self._encode_output.toPlainText()
        if not result:
            return
        QApplication.clipboard().setText(result)
        self._set_status("✓  Obfuscated payload copied to clipboard.", C_SUCCESS)

    def _do_decode(self) -> None:
        raw = self._raw_input.toPlainText()
        if not raw.strip():
            self._set_status("⚠  Paste or type raw text to scan.", C_WARNING)
            return

        try:
            message = decode(raw)
        except InvalidPayloadError as exc:
            self._decode_output.setPlainText(f"[Corrupted payload: {exc}]")
            self._decode_output.setStyleSheet(_textbox_style(C_ERROR, C_SURFACE))
            self._set_status(f"✕  Decode error: {exc}", C_ERROR)
            return

        if message:
            self._decode_output.setPlainText(message)
            self._decode_output.setStyleSheet(_textbox_style(C_SUCCESS, C_SURFACE))
            self._set_status(f"✓  Payload extracted — {len(message)} chars.", C_SUCCESS)
        else:
            self._decode_output.setPlainText("[No Plane 14 payload detected in this text]")
            self._decode_output.setStyleSheet(_textbox_style(C_MUTED, C_SURFACE))
            self._set_status("·  No hidden payload found.", C_MUTED)

    def _paste_and_decode(self) -> None:
        text = QApplication.clipboard().text()
        self._raw_input.setPlainText(text)
        self._do_decode()

    def _clear_encode(self) -> None:
        self._anchor_input.clear()
        self._hidden_input.clear()
        self._encode_output.clear()
        self._set_status("Cleared.", C_MUTED)

    def _clear_decode(self) -> None:
        self._raw_input.clear()
        self._decode_output.clear()
        self._set_status("Cleared.", C_MUTED)

    # =========================================================================
    # Clipboard Watcher
    # =========================================================================

    def _toggle_watcher(self) -> None:
        if self._watcher_chk.isChecked():
            self._start_watcher()
        else:
            self._stop_watcher()

    def _start_watcher(self) -> None:
        """Connect to Qt clipboard dataChanged signal — no polling thread needed."""
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_change)
        self._watcher_active = True
        self._indicator.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 10pt; background: transparent;"
        )
        self._set_status(
            "◉  Clipboard Watcher active — scanning for hidden payloads…", C_ACCENT
        )

    def _stop_watcher(self) -> None:
        try:
            QApplication.clipboard().dataChanged.disconnect(self._on_clipboard_change)
        except RuntimeError:
            pass  # Already disconnected
        self._watcher_active = False
        self._indicator.setStyleSheet(
            f"color: {C_SURFACE}; font-size: 10pt; background: transparent;"
        )
        self._set_status("Clipboard Watcher stopped.", C_MUTED)

    def _on_clipboard_change(self) -> None:
        """Fires on the main thread when clipboard content changes."""
        if not self._watcher_active:
            return
        text = QApplication.clipboard().text()
        if not text:
            return
        try:
            message = decode(text)
            if message:
                self._notify_payload(message, text)
        except (InvalidPayloadError, Exception):
            pass

    def _notify_payload(self, message: str, raw: str) -> None:
        """Surface notification overlay and populate Decode panel."""
        self._dismiss_notify()

        self._show_decode()
        self._raw_input.setPlainText(raw)
        self._decode_output.setPlainText(message)
        self._decode_output.setStyleSheet(_textbox_style(C_SUCCESS, C_SURFACE))

        preview = message[:48] + ("…" if len(message) > 48 else "")
        self._set_status(f"⬡  PAYLOAD DETECTED  →  \"{preview}\"", C_ACCENT)

        # Floating notification banner (child widget — no external window)
        notif = QLabel(f"⬡  PAYLOAD DETECTED  ·  {preview}", self)
        notif.setAlignment(Qt.AlignCenter)
        notif.setStyleSheet(
            f"background-color: {C_ACCENT}; color: white; "
            f"font-weight: bold; font-size: 10pt; "
            f"border-radius: 8px; padding: 9px 14px;"
        )
        notif.adjustSize()
        w = int(self.width() * 0.88)
        notif.setFixedWidth(w)
        notif.move((self.width() - w) // 2, int(self.height() * 0.85))
        notif.show()
        self._notify_widget = notif

        self._notify_timer.start(NOTIFY_DURATION_MS)

        # Bring window to front
        self.raise_()
        self.activateWindow()
        self.setWindowOpacity(1.0)
        QTimer.singleShot(1500, lambda: self.setWindowOpacity(0.96))

    def _dismiss_notify(self) -> None:
        if self._notify_widget is not None:
            self._notify_widget.hide()
            self._notify_widget.deleteLater()
            self._notify_widget = None

    # =========================================================================
    # Status bar
    # =========================================================================

    def _set_status(self, message: str, color: str = C_MUTED) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 9pt; background: transparent;"
        )

    # =========================================================================
    # Hotkeys
    # =========================================================================

    def _bind_hotkeys(self) -> None:
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._show_encode)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._show_decode)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            self._toggle_watcher_hotkey
        )
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(
            self._primary_action
        )
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

    def _toggle_watcher_hotkey(self) -> None:
        self._watcher_chk.setChecked(not self._watcher_chk.isChecked())

    def _primary_action(self) -> None:
        if self._current_panel == "encode":
            self._encode_and_copy()
        else:
            self._paste_and_decode()

    # =========================================================================
    # Window management
    # =========================================================================

    def closeEvent(self, event) -> None:
        self._stop_watcher()
        super().closeEvent(event)


# ─── Entry point ──────────────────────────────────────────────────────────────

def run_widget() -> None:
    """
    Launch the BlindTag observer widget.

    Call this function directly or via the ``blindtag-widget`` console script
    installed by pyproject.toml.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(_APP_STYLESHEET)
    win = BlindTagWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_widget()
