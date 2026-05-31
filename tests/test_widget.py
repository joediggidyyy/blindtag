"""
tests/test_widget.py
====================
Tests for Pass D–H widget surfaces:
  - TestEmojiLibrary      — headless; no QApplication needed
  - TestGuidancePanel     — requires qapp fixture (session-scoped)
  - TestEmojiFlyout       — requires qapp fixture (session-scoped)
  - TestEncodeResolution  — headless; no QApplication needed

Run with:
    pytest tests/test_widget.py -v
"""

import json
import re
import shutil

import pytest

from blindtag.widget import (
    EmojiLibrary,
    _DEFAULT_LIBRARY_PATH,
    _CARD_CONTENT,
    _EmojiCard,
    _EmojiFlyout,
    _GuidancePanel,
    _resolve_anchor_tokens,
)


# =============================================================================
# TestEmojiLibrary — headless (no QApplication)
# =============================================================================

class TestEmojiLibrary:
    """Load/save/validate logic tested against a tmp_path copy of the library."""

    def test_load_default_library(self) -> None:
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        entries = lib.load()
        assert len(entries) == 20

    def test_schema_completeness(self) -> None:
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        for entry in lib.load():
            assert "emoji" in entry
            assert "alias" in entry
            assert "codes" in entry
            assert "label" in entry

    def test_alias_in_codes(self) -> None:
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        for entry in lib.load():
            assert entry["alias"] in entry["codes"], (
                f"alias {entry['alias']!r} not in codes for {entry['emoji']}"
            )

    def test_all_codes_printable_ascii(self) -> None:
        pattern = re.compile(r"^[ -~]+$")
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        for entry in lib.load():
            for code in entry["codes"]:
                assert pattern.match(code), (
                    f"non-ASCII code {code!r} in entry {entry['emoji']}"
                )

    def test_add_and_remove_entry(self, tmp_path) -> None:
        src = shutil.copy(_DEFAULT_LIBRARY_PATH, tmp_path / "emoji_library_default.json")
        lib = EmojiLibrary(tmp_path / "emoji_library_default.json")
        new_entry = {
            "emoji": "\U0001f9ea",
            "alias": ":test:",
            "codes": [":test:", "TEST"],
            "label": "test tube",
        }
        lib.add_entry(new_entry)
        entries = lib.load()
        assert len(entries) == 21
        assert any(e["emoji"] == "\U0001f9ea" for e in entries)

        lib.remove_entry("\U0001f9ea")
        entries = lib.load()
        assert len(entries) == 20
        assert not any(e["emoji"] == "\U0001f9ea" for e in entries)

    def test_set_active_alias(self, tmp_path) -> None:
        shutil.copy(_DEFAULT_LIBRARY_PATH, tmp_path / "emoji_library_default.json")
        lib = EmojiLibrary(tmp_path / "emoji_library_default.json")
        # First entry is 😀; codes include ":smiley:"
        entries = lib.load()
        emoji = entries[0]["emoji"]
        second_code = entries[0]["codes"][1]

        lib.set_active_alias(emoji, second_code)
        updated = lib.load()
        assert updated[0]["alias"] == second_code

    def test_invalid_code_rejected(self) -> None:
        assert EmojiLibrary.validate_codes([":ok:", "bad\x80code"]) is False

    def test_alias_not_in_codes_rejected(self) -> None:
        entry = {
            "emoji": "\U0001f600",
            "alias": ":missing:",
            "codes": [":smile:"],
            "label": "smile",
        }
        assert EmojiLibrary.validate_entry(entry) is False

    def test_malformed_json_returns_empty(self, tmp_path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid", encoding="utf-8")
        lib = EmojiLibrary(bad_file)
        result = lib.load()
        assert result == []


# =============================================================================
# TestGuidancePanel — requires QApplication
# =============================================================================

class TestGuidancePanel:
    """Smoke tests for the guidance panel and card structure."""

    def test_panel_instantiates(self, qapp) -> None:
        from PySide6.QtWidgets import QMainWindow
        # _GuidancePanel requires a BlindTagWindow parent; use a minimal stub
        from blindtag.widget import BlindTagWindow  # noqa: F401 — import only
        # Verify construction does not raise
        panel = _GuidancePanel.__new__(_GuidancePanel)
        # Use a plain QWidget parent to avoid spawning full BlindTagWindow
        from PySide6.QtWidgets import QWidget
        stub = QWidget()
        _GuidancePanel.__init__(panel, stub)  # type: ignore[arg-type]
        assert panel is not None

    def test_card_count(self, qapp) -> None:
        from PySide6.QtWidgets import QWidget
        stub = QWidget()
        panel = _GuidancePanel.__new__(_GuidancePanel)
        _GuidancePanel.__init__(panel, stub)  # type: ignore[arg-type]
        # _CARD_CONTENT has 5 entries; one _EmojiCard per entry
        cards = [c for c in panel.findChildren(_EmojiCard)]
        assert len(cards) == len(_CARD_CONTENT)

    def test_card_text_not_empty(self, qapp) -> None:
        for title, body in _CARD_CONTENT:
            assert title.strip() != ""
            assert body.strip() != ""


# =============================================================================
# TestEmojiFlyout — requires QApplication
# =============================================================================

class TestEmojiFlyout:
    """Flyout cell count and glyph-insert contract."""

    def _make_flyout(self, qapp):
        from PySide6.QtWidgets import QWidget
        stub = QWidget()
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        self._last_received: str = ""

        def on_select(emoji: str) -> None:
            self._last_received = emoji

        flyout = _EmojiFlyout(
            stub,  # type: ignore[arg-type]
            lib,
            on_select=on_select,
            on_edit_library=lambda: None,
        )
        return flyout

    def test_flyout_instantiates(self, qapp) -> None:
        flyout = self._make_flyout(qapp)
        assert flyout is not None

    def test_cell_count_matches_library(self, qapp) -> None:
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        entries = lib.load()
        flyout = self._make_flyout(qapp)
        from PySide6.QtWidgets import QPushButton
        # Each entry gets one emoji cell button (excluding the edit button)
        cells = [b for b in flyout.findChildren(QPushButton)
                 if len(b.text()) > 0 and b.text() != "Edit library  ⚙"]
        assert len(cells) == len(entries)

    def test_click_inserts_glyph(self, qapp) -> None:
        """Clicking a cell passes the raw glyph to on_select; hidden payload untouched."""
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        first_entry = lib.load()[0]
        flyout = self._make_flyout(qapp)

        from PySide6.QtWidgets import QPushButton
        cells = [b for b in flyout.findChildren(QPushButton)
                 if len(b.text()) > 0 and b.text() != "Edit library  ⚙"]
        cells[0].click()

        # on_select received the raw glyph (not an alias string)
        assert self._last_received == first_entry["emoji"]


# =============================================================================
# TestEncodeResolution — headless (no QApplication)
# =============================================================================

class TestEncodeResolution:
    """Unit tests for the _resolve_anchor_tokens() resolution pipeline."""

    def _lib(self) -> EmojiLibrary:
        return EmojiLibrary(_DEFAULT_LIBRARY_PATH)

    def test_u_token_resolves(self) -> None:
        lib = self._lib()
        first_entry = lib.load()[0]
        cp = ord(first_entry["emoji"])
        token = f"U+{cp:04X}"
        result = _resolve_anchor_tokens(token, lib)
        assert result == first_entry["emoji"]

    def test_alias_token_resolves(self) -> None:
        lib = self._lib()
        first_entry = lib.load()[0]
        alias_code = first_entry["codes"][0]
        token = f":{alias_code}:" if not alias_code.startswith(":") else alias_code
        # Construct a proper :code: token from the first code value
        token = ":" + first_entry["codes"][0].strip(":") + ":"
        result = _resolve_anchor_tokens(token, lib)
        assert result == first_entry["emoji"]

    def test_plain_text_passes_through(self) -> None:
        lib = self._lib()
        text = "Hello, world!"
        assert _resolve_anchor_tokens(text, lib) == text

    def test_invalid_codepoint_passes_through(self) -> None:
        lib = self._lib()
        token = "U+110000"  # > 0x10FFFF
        assert _resolve_anchor_tokens(token, lib) == token

    def test_unknown_alias_passes_through(self) -> None:
        lib = self._lib()
        token = ":notarealemoji:"
        assert _resolve_anchor_tokens(token, lib) == token

    def test_empty_string(self) -> None:
        lib = self._lib()
        assert _resolve_anchor_tokens("", lib) == ""

    def test_surrogate_codepoint_passes_through(self) -> None:
        lib = self._lib()
        token = "U+D800"  # surrogate range
        assert _resolve_anchor_tokens(token, lib) == token


