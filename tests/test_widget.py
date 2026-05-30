"""
tests/test_widget.py
====================
Tests for Pass D widget surfaces:
  - TestEmojiLibrary  — headless; no QApplication needed
  - TestGuidancePanel — requires qapp fixture (session-scoped)
  - TestEmojiFlyout   — requires qapp fixture (session-scoped)

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
    """Flyout cell count and alias-append contract."""

    def _make_flyout(self, qapp):
        from PySide6.QtWidgets import QWidget
        stub = QWidget()
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        self._last_alias: str = ""

        def on_select(alias):
            self._last_alias = alias

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
        from PySide6.QtWidgets import QPushButton
        flyout = self._make_flyout(qapp)
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        expected = len(lib.load())
        # Emoji buttons have a toolTip set to the alias; Edit library button does not
        emoji_btns = [
            b for b in flyout.findChildren(QPushButton)
            if b.toolTip() != ""
        ]
        assert len(emoji_btns) == expected

    def test_click_appends_alias(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton
        from blindtag.widget import BlindTagWindow
        lib = EmojiLibrary(_DEFAULT_LIBRARY_PATH)
        entries = lib.load()
        first_entry = entries[0]

        win = BlindTagWindow()
        win._open_emoji_flyout()

        emoji_btns = [
            b for b in win._emoji_flyout.findChildren(QPushButton)
            if b.toolTip() != ""
        ]
        emoji_btns[0].click()

        anchor_text = win._anchor_input.toPlainText()
        payload_text = win._hidden_input.toPlainText()
        assert first_entry["emoji"] in anchor_text, (
            f"expected glyph {first_entry['emoji']!r} in anchor field, got {anchor_text!r}"
        )
        assert first_entry["alias"] in payload_text, (
            f"expected alias {first_entry['alias']!r} in payload field, got {payload_text!r}"
        )
