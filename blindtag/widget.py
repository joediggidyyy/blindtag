"""
blindtag.widget
===============
Low-profile desktop observer widget for rapid BlindTag encode/decode workflows.

Visual Identity
---------------
  Background (primary):  #0a0d12  Deep Cool Navy
  Surface (secondary):   #10161f  Navy Surface
  Raised surface:        #16212d  Navy Card
  Accent:                #3dd5f3  Brand Cyan
  Accent hover:          #62daf7  Cyan Highlight
  Text (primary):        #edf2f7  Cool Near-White
  Text (muted):          #9aa9bc  Cool Blue-Gray
  Success:               #4fc08d  Confirmation Green
  Warning:               #f3a948  Amber Alert
  Error:                 #e25757  Alert Red
  Border/line:           #263546  Navy-tinted Divider

Panel Layout
------------
  ┌──────────────────────────────────────────┐
  │ ⬡ BlindTag                       ─   ✕  │  ← draggable title bar
  ├──────────────────────────────────────────┤
  │ [ Encode ] [ Decode ]   [ Clip Watch ]   │  ← segmented toggle (glow button)
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

import ctypes
import json
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .core import decode, encode, strip_plane14
from .exceptions import InvalidPayloadError

# ─── Asset paths ──────────────────────────────────────────────────────────────

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "images"
_DEFAULT_LIBRARY_PATH = Path(__file__).resolve().parent.parent / "assets" / "emoji_library_default.json"

# ─── Colour palette ───────────────────────────────────────────────────────────

C_BG        = "#0a0d12"   # Deep Cool Navy  — window background
C_SECONDARY = "#10161f"   # Navy Surface     — title bar, toggle strip, status bar
C_SURFACE   = "#16212d"   # Navy Card        — read-only output fields
C_ACCENT    = "#3dd5f3"   # Brand Cyan       — indicators and tints only; never a fill
C_ACCENT_H  = "#62daf7"   # Cyan Highlight   — hover state
C_LINE      = "#263546"   # Navy-tinted Line — borders and dividers
C_TEXT      = "#edf2f7"   # Cool Near-White  — primary text
C_MUTED     = "#9aa9bc"   # Cool Blue-Gray   — labels, hints, secondary text
C_SUCCESS   = "#4fc08d"   # Confirmation Green
C_WARNING   = "#f3a948"   # Amber Alert
C_ERROR     = "#e25757"   # Alert Red

# ─── Timing ───────────────────────────────────────────────────────────────────

NOTIFY_DURATION_MS: int = 4_500  # Notification overlay auto-dismiss duration

# ─── Emoji library ────────────────────────────────────────────────────────────

_CODE_RE = re.compile(r"^[ -~]+$")  # printable ASCII 0x20–0x7E

# ─── Anchor token resolution regexes ─────────────────────────────────────────

_U_TOKEN_RE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
_ALIAS_RE = re.compile(r":[a-z0-9_]+:")


def _resolve_anchor_tokens(text: str, library: EmojiLibrary) -> str:
    """
    Resolve U+XXXX and :alias: tokens in *text* to their Unicode/glyph equivalents.

    Resolution order (left-to-right, non-overlapping):
      1. ``U+XXXX`` (4–6 hex digits) → ``chr(codepoint)``.  Invalid codepoints
         (> 0x10FFFF, surrogates 0xD800–0xDFFF) pass through unchanged.
      2. ``:alias:`` → emoji glyph from *library* ``codes`` membership.
         Unknown aliases pass through unchanged.
      3. Everything else passes through unchanged.

    Bare uppercase keywords are intentionally excluded — resolving them
    would corrupt natural-language anchor text.

    This function performs no I/O; *library* is expected to be an already-
    instantiated ``EmojiLibrary`` whose entries are loaded inside this call.
    """
    if not text:
        return text

    entries = library.load()
    # Build alias→glyph map once
    alias_map: dict[str, str] = {}
    for entry in entries:
        for code in entry["codes"]:
            # codes may already be colon-wrapped (e.g. ":smile:") or bare (e.g. "SMILE")
            if code.startswith(":") and code.endswith(":") and len(code) > 2:
                alias_map[code] = entry["emoji"]
            else:
                alias_map[f":{code}:"] = entry["emoji"]

    result: list[str] = []
    i = 0
    while i < len(text):
        # Try U+ token
        m_u = _U_TOKEN_RE.match(text, i)
        if m_u:
            hex_str = m_u.group(1)
            cp = int(hex_str, 16)
            if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
                result.append(m_u.group(0))
            else:
                result.append(chr(cp))
            i = m_u.end()
            continue
        # Try :alias: token
        m_a = _ALIAS_RE.match(text, i)
        if m_a:
            token = m_a.group(0)
            result.append(alias_map.get(token, token))
            i = m_a.end()
            continue
        # Plain character
        result.append(text[i])
        i += 1
    return "".join(result)


class EmojiLibrary:
    """
    Headless load/save/validate manager for the emoji alias library.

    Accepts an explicit ``path`` for dependency injection (tests pass a
    ``tmp_path`` copy; production code passes ``_DEFAULT_LIBRARY_PATH``).
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self) -> list[dict]:
        """Load and validate entries.  Returns [] on malformed JSON."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Caller may surface this to the status bar.
            self._warn = str(exc)
            return []
        entries: list[dict] = []
        for item in raw:
            if self.validate_entry(item):
                entries.append(item)
            # silently drop invalid entries (schema drift protection)
        return entries

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_codes(codes: list[str]) -> bool:
        """Return True if every code is non-empty printable ASCII."""
        if not codes:
            return False
        return all(isinstance(c, str) and bool(_CODE_RE.match(c)) for c in codes)

    @classmethod
    def validate_entry(cls, entry: dict) -> bool:
        """Return True if entry satisfies the schema contract."""
        required = {"emoji", "alias", "codes", "label"}
        if not required.issubset(entry):
            return False
        if not isinstance(entry["codes"], list) or not cls.validate_codes(entry["codes"]):
            return False
        if entry["alias"] not in entry["codes"]:
            return False
        return True

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def _save(self, entries: list[dict]) -> None:
        """Atomic write: write to .tmp then rename."""
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path)

    def add_entry(self, entry: dict) -> None:
        entries = self.load()
        entries.append(entry)
        self._save(entries)

    def remove_entry(self, emoji: str) -> None:
        entries = [e for e in self.load() if e["emoji"] != emoji]
        self._save(entries)

    def set_active_alias(self, emoji: str, code: str) -> None:
        entries = self.load()
        for e in entries:
            if e["emoji"] == emoji:
                if code in e["codes"]:
                    e["alias"] = code
                break
        self._save(entries)


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
        f"border: 1px solid {C_LINE}; border-radius: 6px; "
        f"font-family: 'Courier New'; font-size: 11pt; padding: 4px;"
        f"}}"
    )


def _btn_primary_style() -> str:
    # Primary action — deepest visual weight, through depth not brightness.
    return (
        f"QPushButton {{"
        f"background-color: #14384f; color: #c9e8ef; "
        f"font-weight: bold; border: 1px solid #2a6b85; border-radius: 6px; padding: 8px 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: #1a4d68; border-color: #3a8faa; }}"
    )


def _clip_watch_active_style() -> str:
    """Clip Watch button — active: soft teal text and single-pixel teal border. No fill."""
    return (
        f"QPushButton {{"
        f"background-color: transparent; color: #7ab8c9; "
        f"border: 1px solid #2a6b85; border-radius: 5px; "
        f"font-size: 9pt; padding: 5px 12px;"
        f"}}"
        f"QPushButton:hover {{ color: {C_TEXT}; border-color: #3a8faa; }}"
    )


def _clip_watch_inactive_style() -> str:
    """Clip Watch button — idle: barely visible; recedes until needed."""
    return (
        f"QPushButton {{"
        f"background-color: transparent; color: {C_MUTED}; "
        f"border: 1px solid {C_LINE}; border-radius: 5px; "
        f"font-size: 9pt; padding: 5px 12px;"
        f"}}"
        f"QPushButton:hover {{ border-color: #2a6b85; color: {C_TEXT}; }}"
    )


def _btn_secondary_style() -> str:
    return (
        f"QPushButton {{"
        f"background-color: {C_SURFACE}; color: {C_TEXT}; "
        f"border: 1px solid {C_LINE}; border-radius: 6px; padding: 8px 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: #1d2c3d; }}"
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
    # Selected mode: elevated surface + bright text. No fill color.
    # Active state is read through text brightness vs inactive muting.
    return (
        f"QPushButton {{"
        f"background-color: #1c2d3d; color: {C_TEXT}; "
        f"border: 1px solid {C_LINE}; border-radius: 4px; padding: 6px 18px;"
        f"}}"
    )


def _toggle_inactive_style() -> str:
    # Unselected mode: transparent, muted text. Fades to background.
    return (
        f"QPushButton {{"
        f"background-color: transparent; color: {C_MUTED}; "
        f"border: 1px solid transparent; border-radius: 4px; padding: 6px 18px;"
        f"}}"
        f"QPushButton:hover {{ color: {C_TEXT}; }}"
    )


# ─── Guidance panel ──────────────────────────────────────────────────────────

_CARD_CONTENT: list[tuple[str, str]] = [
    (
        "Anchor text",
        "The visible text your payload will be hidden inside. "
        "Any readable string works. The receiver sees only this "
        "text unless they decode it.",
    ),
    (
        "Hidden payload",
        "The secret message to embed. Must be printable characters "
        "(letters, numbers, punctuation, spaces). Max ~9,000 characters. "
        "When you pick an emoji from the selector, its alias (e.g. :smile:) "
        "is automatically appended here alongside the glyph in the anchor text.",
    ),
    (
        "Emoji aliases",
        "The emoji selector inserts the raw glyph into your anchor text. "
        "Box 1 is format-agnostic: you can also type a U+XXXX codepoint or "
        "a :alias: code and it will be resolved automatically at encode time. "
        "Edit the library to add your own glyphs.",
    ),
    (
        "Obfuscate & Copy",
        "Runs encode and immediately copies the result to your clipboard. "
        "The output looks identical to your anchor text — the payload is invisible.",
    ),
    (
        "Clip Watch",
        "Monitors your clipboard. When you copy text that contains a hidden payload, "
        "BlindTag automatically detects and shows it. No data leaves your machine.",
    ),
]


class _EmojiCard(QWidget):
    """Collapsible help card with caret toggle."""

    def __init__(self, title: str, body: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._expanded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Header row
        self._header = QPushButton(f"\u25b6  {title}")
        self._header.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_TEXT}; "
            f"font-size: 9pt; font-weight: bold; text-align: left; border: none; padding: 2px 0; }}"
            f"QPushButton:hover {{ color: {C_ACCENT}; }}"
        )
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # Body label (hidden until expanded)
        self._body = QLabel(body)
        self._body.setWordWrap(True)
        self._body.setStyleSheet(
            f"color: {C_TEXT}; font-size: 10pt; background: transparent; padding: 0 4px 4px 18px;"
        )
        self._body.setVisible(False)
        layout.addWidget(self._body)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        caret = "\u25bc" if self._expanded else "\u25b6"
        title = self._header.text()[2:]  # strip old caret + space
        self._header.setText(f"{caret}  {title}")
        self._body.setVisible(self._expanded)


class _GuidancePanel(QWidget):
    """Left-side slide-out help panel — 200px overlay, z-ordered above _stack."""

    def __init__(self, parent: "BlindTagWindow") -> None:
        super().__init__(parent)
        self.setFixedWidth(200)
        # Use a class-specific selector so the global QWidget{background} rule
        # in _APP_STYLESHEET cannot bleed through via inheritance.
        self.setStyleSheet(
            f"_GuidancePanel, QWidget#guidance_panel {{"
            f" background-color: {C_SECONDARY}; border-right: 1px solid {C_LINE}; }}"
        )
        self.setObjectName("guidance_panel")
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        header = QLabel("  HELP")
        header.setStyleSheet(
            f"color: {C_MUTED}; font-size: 9pt; font-weight: bold; "
            f"padding: 4px 8px 8px 8px; background: transparent;"
        )
        layout.addWidget(header)

        for title, body in _CARD_CONTENT:
            layout.addWidget(_EmojiCard(title, body))

        layout.addStretch()

    def reposition(self, parent_height: int, top_offset: int, bottom_offset: int) -> None:
        """Resize/reposition to fill the area between toggle strip and status bar."""
        h = parent_height - top_offset - bottom_offset
        self.setGeometry(0, top_offset, 200, h)


# ─── Emoji flyout ─────────────────────────────────────────────────────────────


class _EmojiFlyout(QFrame):
    """Floating glyph-grid flyout anchored below the \u263a trigger button."""

    def __init__(
        self,
        parent: "BlindTagWindow",
        library: EmojiLibrary,
        on_select,
        on_edit_library,
    ) -> None:
        super().__init__(parent)
        self._parent_win = parent
        self._on_select = on_select

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background-color: {C_SURFACE}; border: 1px solid {C_LINE}; border-radius: 6px; }}"
        )
        self.setFixedWidth(240)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 4)
        outer.setSpacing(4)

        # Scrollable grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setMaximumHeight(190)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        entries = library.load()
        self._entries = entries
        COLS = 6
        for idx, entry in enumerate(entries):
            btn = QPushButton(entry["emoji"])
            btn.setFixedSize(44, 44)
            btn.setToolTip(entry["alias"])
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; border-radius: 4px; "
                f"font-size: 18pt; padding: 0; }}"
                f"QPushButton:hover {{ background-color: {C_LINE}; }}"
            )
            alias = entry["alias"]
            emoji = entry["emoji"]
            btn.clicked.connect(lambda checked=False, g=emoji: self._pick(g))
            grid.addWidget(btn, idx // COLS, idx % COLS)

        scroll.setWidget(grid_widget)
        outer.addWidget(scroll)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color: {C_LINE};")
        outer.addWidget(div)

        # Edit library link
        btn_edit = QPushButton("Edit library  \u2699")
        btn_edit.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; "
            f"font-size: 9pt; border: none; text-align: left; padding: 2px 4px; }}"
            f"QPushButton:hover {{ color: {C_TEXT}; }}"
        )
        btn_edit.clicked.connect(on_edit_library)
        outer.addWidget(btn_edit)

        self.adjustSize()
        # Install event filter on parent to dismiss on click-outside
        parent.installEventFilter(self)

    def _pick(self, emoji: str) -> None:
        self._on_select(emoji)
        self.hide()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.MouseButtonPress and self.isVisible():
            if not self.geometry().contains(event.position().toPoint()):
                self.hide()
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()
        super().keyPressEvent(event)


# ─── Library editor panel ─────────────────────────────────────────────────────


class _LibraryEditorPanel(QWidget):
    """Fourth _stack panel — entered from flyout, exited via Back button."""

    def __init__(self, parent: "BlindTagWindow", library: EmojiLibrary) -> None:
        super().__init__(parent)
        self._win = parent
        self._library = library

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # Header row
        header_row = QWidget()
        hl = QHBoxLayout(header_row)
        hl.setContentsMargins(0, 0, 0, 0)
        btn_back = QPushButton("\u2190  Back")
        btn_back.setStyleSheet(_btn_ghost_style())
        btn_back.setFixedHeight(28)
        btn_back.clicked.connect(parent._return_from_editor)
        hl.addWidget(btn_back)
        lbl = QLabel("Emoji Library")
        lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: bold; font-size: 10pt; background: transparent;")
        hl.addWidget(lbl)
        hl.addStretch()
        root.addWidget(header_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color: {C_LINE};")
        root.addWidget(div)

        # Scrollable entry list
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        self._list_scroll.setWidget(self._list_container)
        root.addWidget(self._list_scroll, stretch=1)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet(f"color: {C_LINE};")
        root.addWidget(div2)

        # Add-entry form
        form_lbl = QLabel("+ Add entry")
        form_lbl.setStyleSheet(f"color: {C_MUTED}; font-size: 9pt; background: transparent;")
        root.addWidget(form_lbl)

        form_row = QWidget()
        fl = QHBoxLayout(form_row)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(4)

        self._add_emoji = QLineEdit()
        self._add_emoji.setPlaceholderText("\U0001f60a or :alias:")
        self._add_emoji.setStyleSheet(self._field_style())

        self._add_label = QLineEdit()
        self._add_label.setPlaceholderText("label")
        self._add_label.setFixedWidth(90)
        self._add_label.setStyleSheet(self._field_style())

        btn_add = QPushButton("Add")
        btn_add.setStyleSheet(_btn_secondary_style())
        btn_add.setFixedHeight(30)
        btn_add.clicked.connect(self._do_add)

        fl.addWidget(self._add_emoji, stretch=1)
        fl.addWidget(self._add_label)
        fl.addWidget(btn_add)
        root.addWidget(form_row)

        self._validation_lbl = QLabel("")
        self._validation_lbl.setStyleSheet(f"color: {C_ERROR}; font-size: 9pt; background: transparent;")
        root.addWidget(self._validation_lbl)

    @staticmethod
    def _field_style(invalid: bool = False) -> str:
        border = C_ERROR if invalid else C_LINE
        return (
            f"QLineEdit {{ background-color: {C_SECONDARY}; color: {C_TEXT}; "
            f"border: 1px solid {border}; border-radius: 4px; padding: 3px 6px; font-size: 9pt; }}"
        )

    def refresh(self) -> None:
        """Reload entries from library and rebuild the list UI."""
        # Remove all rows except the trailing stretch
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self._library.load()
        for entry in entries:
            self._list_layout.insertWidget(self._list_layout.count() - 1, self._make_row(entry))

    def _make_row(self, entry: dict) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 2, 0, 2)
        hl.setSpacing(6)

        # Glyph with tooltip showing active alias
        lbl_glyph = QLabel(entry["emoji"])
        lbl_glyph.setStyleSheet(f"font-size: 14pt; background: transparent; color: {C_TEXT};")
        lbl_glyph.setFixedWidth(28)
        lbl_glyph.setToolTip(entry["alias"])
        hl.addWidget(lbl_glyph)

        # Label
        lbl_name = QLabel(entry["label"])
        lbl_name.setStyleSheet(f"color: {C_MUTED}; font-size: 9pt; background: transparent;")
        hl.addWidget(lbl_name, stretch=1)

        # Delete button
        btn_del = QPushButton("\u2715")
        btn_del.setFixedSize(22, 22)
        btn_del.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C_MUTED}; border: none; font-size: 10pt; }}"
            f"QPushButton:hover {{ color: {C_ERROR}; }}"
        )
        btn_del.clicked.connect(lambda checked=False, em=entry["emoji"]: self._do_delete(em))
        hl.addWidget(btn_del)

        return row

    def _do_add(self) -> None:
        self._validation_lbl.setText("")
        raw_input = self._add_emoji.text().strip()
        label = self._add_label.text().strip()

        if not raw_input:
            self._validation_lbl.setText("Emoji or code is required.")
            self._add_emoji.setStyleSheet(self._field_style(invalid=True))
            return
        if not label:
            self._validation_lbl.setText("Label is required.")
            self._add_label.setStyleSheet(self._field_style(invalid=True))
            return

        # Detect glyph vs code string
        is_glyph = any(ord(c) > 0x7E for c in raw_input)
        if is_glyph:
            emoji_val = raw_input
            alias = f":{label.lower().replace(' ', '_')}:"
        else:
            # Code string — must be printable ASCII; try to resolve glyph from library
            if not _CODE_RE.match(raw_input):
                self._validation_lbl.setText("Code must be printable ASCII only.")
                self._add_emoji.setStyleSheet(self._field_style(invalid=True))
                return
            alias = raw_input
            existing = self._library.load()
            glyph_match = next(
                (e["emoji"] for e in existing if raw_input in e["codes"]), None
            )
            if not glyph_match:
                self._validation_lbl.setText("Code not in library — paste the emoji glyph instead.")
                self._add_emoji.setStyleSheet(self._field_style(invalid=True))
                return
            emoji_val = glyph_match

        # Reset field borders
        self._add_emoji.setStyleSheet(self._field_style())
        self._add_label.setStyleSheet(self._field_style())

        entry = {"emoji": emoji_val, "alias": alias, "codes": [alias], "label": label}
        self._library.add_entry(entry)
        self._add_emoji.clear()
        self._add_label.clear()
        self.refresh()

    def _do_delete(self, emoji: str) -> None:
        self._library.remove_entry(emoji)
        self.refresh()


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

        # Help button
        self._btn_help = QPushButton("?")
        self._btn_help.setFixedSize(26, 26)
        self._btn_help.setStyleSheet(_btn_ghost_style())
        layout.addWidget(self._btn_help)

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

        icon_path = _ASSETS_DIR / "blindtag_thumbnail_basic.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Runtime state
        self._current_panel: str = "encode"
        self._watcher_active: bool = False
        self._notify_widget: Optional[QWidget] = None
        self._notify_timer = QTimer(self)
        self._notify_timer.setSingleShot(True)
        self._notify_timer.timeout.connect(self._dismiss_notify)
        self._emoji_flyout: Optional[_EmojiFlyout] = None
        self._prev_panel: str = "encode"  # restore after library editor

        # Emoji library
        self._library = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        warn = getattr(self._library, "_warn", None)

        # Build UI
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._title_bar = _TitleBar(self)
        self._title_bar._btn_help.clicked.connect(self._toggle_guidance_panel)
        root.addWidget(self._title_bar)

        self._toggle_strip = self._build_toggle_strip()
        root.addWidget(self._toggle_strip)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._encode_panel = self._build_encode_panel()
        self._decode_panel = self._build_decode_panel()
        self._library_editor = _LibraryEditorPanel(self, self._library)
        self._stack.addWidget(self._encode_panel)    # index 0
        self._stack.addWidget(self._decode_panel)    # index 1
        self._stack.addWidget(self._library_editor)  # index 2

        self._status_bar = self._build_status_bar()
        root.addWidget(self._status_bar)

        # Guidance panel (overlays _stack)
        self._guidance_panel = _GuidancePanel(self)

        self._bind_hotkeys()
        self._show_encode()

        if warn:
            self._set_status(f"\u26a0  Emoji library: {warn}", C_WARNING)

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

        self._watcher_btn = QPushButton(" Clip Watch")
        self._watcher_btn.setCheckable(True)
        self._watcher_btn.setStyleSheet(_clip_watch_inactive_style())
        self._watcher_btn.toggled.connect(self._toggle_watcher)
        layout.addWidget(self._watcher_btn)

        return strip

    def _build_encode_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        # ANCHOR TEXT row with emoji trigger
        anchor_row = QWidget()
        anchor_row.setStyleSheet("background: transparent;")
        ar = QHBoxLayout(anchor_row)
        ar.setContentsMargins(0, 0, 0, 0)
        ar.setSpacing(4)
        ar.addWidget(self._section_label("ANCHOR TEXT  \u00b7  visible cover"), stretch=1)
        self._btn_emoji = QPushButton("\u263a")
        self._btn_emoji.setFixedSize(26, 26)
        self._btn_emoji.setStyleSheet(_btn_ghost_style())
        self._btn_emoji.clicked.connect(self._open_emoji_flyout)
        ar.addWidget(self._btn_emoji)
        layout.addWidget(anchor_row)
        self._anchor_input = self._make_textbox(82)
        layout.addWidget(self._anchor_input)

        layout.addWidget(self._section_label("HIDDEN PAYLOAD  \u00b7  printable ASCII only"))

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
        self._prev_panel = "encode"
        self._btn_encode.setStyleSheet(_toggle_active_style())
        self._btn_decode.setStyleSheet(_toggle_inactive_style())

    def _show_decode(self) -> None:
        self._stack.setCurrentWidget(self._decode_panel)
        self._current_panel = "decode"
        self._prev_panel = "decode"
        self._btn_encode.setStyleSheet(_toggle_inactive_style())
        self._btn_decode.setStyleSheet(_toggle_active_style())

    def _show_library_editor(self) -> None:
        self._library_editor.refresh()
        self._stack.setCurrentWidget(self._library_editor)
        self._current_panel = "library"

    def _return_from_editor(self) -> None:
        if self._prev_panel == "decode":
            self._show_decode()
        else:
            self._show_encode()

    # =========================================================================
    # Guidance panel
    # =========================================================================

    def _toggle_guidance_panel(self) -> None:
        if self._guidance_panel.isVisible():
            self._guidance_panel.hide()
        else:
            self._reposition_guidance_panel()
            self._guidance_panel.show()
            self._guidance_panel.raise_()

    def _reposition_guidance_panel(self) -> None:
        top = self._title_bar.height() + self._toggle_strip.height()
        bottom = self._status_bar.height()
        self._guidance_panel.reposition(self.height(), top, bottom)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._guidance_panel.isVisible():
            self._reposition_guidance_panel()

    # =========================================================================
    # Emoji flyout
    # =========================================================================

    def _open_emoji_flyout(self) -> None:
        if self._emoji_flyout is not None:
            self._emoji_flyout.hide()
            self._emoji_flyout.deleteLater()
        self._emoji_flyout = _EmojiFlyout(
            self,
            self._library,
            on_select=self._insert_emoji,
            on_edit_library=self._open_library_editor,
        )
        # Position below the emoji trigger button
        btn_pos = self._btn_emoji.mapTo(self, self._btn_emoji.rect().bottomLeft())
        x = btn_pos.x() - self._emoji_flyout.width() + self._btn_emoji.width()
        y = btn_pos.y() + 4
        # Keep within window bounds
        x = max(0, min(x, self.width() - self._emoji_flyout.width()))
        self._emoji_flyout.move(x, y)
        self._emoji_flyout.show()
        self._emoji_flyout.raise_()

    def _insert_emoji(self, emoji: str) -> None:
        """Single-field insert: place raw glyph into anchor input only."""
        cur = self._anchor_input.textCursor()
        cur.insertText(emoji)
        self._anchor_input.setTextCursor(cur)

    def _open_library_editor(self) -> None:
        if self._emoji_flyout is not None:
            self._emoji_flyout.hide()
        self._show_library_editor()

    # =========================================================================
    # Core actions
    # =========================================================================

    def _do_encode(self) -> None:
        raw_anchor = self._anchor_input.toPlainText().strip()
        hidden = self._hidden_input.toPlainText().strip()

        if not raw_anchor:
            self._set_status("⚠  Anchor text is required.", C_WARNING)
            return
        if not hidden:
            self._set_status("⚠  Hidden payload is required.", C_WARNING)
            return

        # Strip any pre-existing Plane 14 tag sequences from the anchor
        # (prevents silent double-encoding when pasting a previously-tagged string).
        anchor = strip_plane14(raw_anchor)
        # Resolve U+XXXX and :alias: tokens to their Unicode/glyph equivalents.
        anchor = _resolve_anchor_tokens(anchor, self._library)

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

    def _toggle_watcher(self, checked: bool) -> None:
        if checked:
            self._watcher_btn.setStyleSheet(_clip_watch_active_style())
            self._start_watcher()
        else:
            self._watcher_btn.setStyleSheet(_clip_watch_inactive_style())
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
        self._watcher_btn.setChecked(not self._watcher_btn.isChecked())

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
    # Register a unique App User Model ID so Windows groups the taskbar button
    # under the app icon rather than the python.exe identity.
    if platform.system() == "Windows":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Polymath.BlindTag.Widget.1"
            )
        except Exception:  # noqa: BLE001
            pass
    _app_icon_path = Path(__file__).resolve().parent.parent / "assets" / "images" / "blindtag_thumbnail_basic.png"
    if _app_icon_path.exists():
        app.setWindowIcon(QIcon(str(_app_icon_path)))
    app.setStyleSheet(_APP_STYLESHEET)
    win = BlindTagWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_widget()
