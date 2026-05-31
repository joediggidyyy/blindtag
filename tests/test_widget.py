"""
tests/test_widget.py
====================
Tests for Pass D–M widget surfaces:
  - TestEmojiLibrary          — headless; no QApplication needed
  - TestGuidancePanel         — requires qapp fixture (session-scoped)
  - TestEmojiFlyout           — requires qapp fixture (session-scoped)
  - TestEncodeResolution      — headless; no QApplication needed
    - TestGlyphCodeParsing      — headless; no QApplication needed
  - TestNotificationWidget    — headless; MagicMock as main_win
  - TestBackgroundPosture     — requires qapp fixture (session-scoped)
    - TestLibraryEditorColumns  — requires qapp fixture (session-scoped)
    - TestActionButtonCleanup   — requires qapp fixture (session-scoped)
    - TestHiddenNotificationAnchor — requires qapp fixture (session-scoped)

Run with:
    pytest tests/test_widget.py -v
"""

import json
import re
import shutil
from unittest.mock import MagicMock

import pytest

import blindtag.notification as notification_module
from blindtag.notification import NotificationWidget, NOTIFY_MARGIN_PX
from blindtag.widget import (
    EmojiLibrary,
    _DEFAULT_LIBRARY_PATH,
    _CARD_CONTENT,
    _EmojiCard,
    _EmojiFlyout,
    _GuidancePanel,
    _LibraryEditorPanel,
    _format_codepoints,
    _parse_glyph_or_code,
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


class TestGlyphCodeParsing:
    def test_format_codepoints_single(self) -> None:
        assert _format_codepoints("👎") == "U+1F44E"

    def test_format_codepoints_multi(self) -> None:
        assert _format_codepoints("❤️") == "U+2764 U+FE0F"

    def test_parse_glyph_literal(self) -> None:
        assert _parse_glyph_or_code("👎") == "👎"

    def test_parse_unicode_token(self) -> None:
        assert _parse_glyph_or_code("U+1F44E") == "👎"

    def test_parse_unicode_sequence(self) -> None:
        assert _parse_glyph_or_code("U+2764 U+FE0F") == "❤️"

    def test_parse_alias_rejected(self) -> None:
        assert _parse_glyph_or_code(":thumbsdown:") is None


# =============================================================================
# TestNotificationWidget — headless (MagicMock as main_win)
# =============================================================================

NOTIFY_DURATION_MS = 4_500


class TestNotificationWidget:
    """NotificationWidget instantiated with MagicMock; no window is shown."""

    def _make(self) -> NotificationWidget:
        return NotificationWidget(MagicMock(), NOTIFY_DURATION_MS)

    def test_construction_no_error(self, qapp) -> None:
        widget = self._make()
        assert widget is not None

    def test_show_for_sets_label_text(self, qapp) -> None:
        widget = self._make()
        widget.show_for("hello world")
        assert "hello world" in widget._label.text()

    def test_timer_fires_hide(self, qapp) -> None:
        """Timer fires hide; use a very short duration so the test completes fast."""
        widget = NotificationWidget(MagicMock(), duration_ms=1)
        visible_before = True  # we don't actually show it to avoid desktop flicker
        widget._timer.start(1)
        # Pump events briefly so the timer fires.
        from PySide6.QtCore import QCoreApplication
        for _ in range(50):
            QCoreApplication.processEvents()
        # After timer fires, widget should be hidden (timer.timeout -> hide())
        assert not widget._timer.isActive()

    def test_persistent_show_for_does_not_start_timer(self, qapp) -> None:
        widget = NotificationWidget(MagicMock(), duration_ms=1)
        widget.show_for("hello world", persistent=True)
        assert not widget._timer.isActive()

    def test_target_screen_prefers_cursor_screen(self, qapp, monkeypatch) -> None:
        widget = self._make()
        cursor_screen = object()
        monkeypatch.setattr(notification_module.QCursor, "pos", lambda: MagicMock())
        monkeypatch.setattr(notification_module.QGuiApplication, "screenAt", lambda point: cursor_screen)
        monkeypatch.setattr(notification_module.QGuiApplication, "primaryScreen", lambda: object())
        assert widget._target_screen() is cursor_screen

    def test_target_screen_falls_back_to_main_window_screen(self, qapp, monkeypatch) -> None:
        main_win = MagicMock()
        fallback_screen = object()
        main_win.windowHandle.return_value = None
        main_win.screen.return_value = fallback_screen
        widget = NotificationWidget(main_win, NOTIFY_DURATION_MS)
        monkeypatch.setattr(notification_module.QCursor, "pos", lambda: MagicMock())
        monkeypatch.setattr(notification_module.QGuiApplication, "screenAt", lambda point: None)
        monkeypatch.setattr(notification_module.QGuiApplication, "primaryScreen", lambda: object())
        assert widget._target_screen() is fallback_screen

    def test_body_click_shows_main_win(self, qapp) -> None:
        mock_win = MagicMock()
        widget = NotificationWidget(mock_win, NOTIFY_DURATION_MS)
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import Qt, QPointF
        event = MagicMock()
        event.button.return_value = Qt.LeftButton
        widget.mousePressEvent(event)
        mock_win.show.assert_called_once()
        mock_win.raise_.assert_called_once()
        mock_win.activateWindow.assert_called_once()

    def test_hover_pauses_timer(self, qapp) -> None:
        widget = self._make()
        widget._timer.start(NOTIFY_DURATION_MS)
        assert widget._timer.isActive()
        widget.enterEvent(MagicMock())
        assert not widget._timer.isActive()
        widget.leaveEvent(MagicMock())
        assert widget._timer.isActive()
        widget._timer.stop()

    def test_close_button_hides_only(self, qapp) -> None:
        """× button hides widget but does NOT call main_win.show."""
        mock_win = MagicMock()
        widget = NotificationWidget(mock_win, NOTIFY_DURATION_MS)
        widget._close_btn.click()
        mock_win.show.assert_not_called()


# =============================================================================
# TestBackgroundPosture — requires qapp fixture
# =============================================================================

class TestBackgroundPosture:
    """BlindTagWindow background-monitoring posture state machine."""

    def _make_window(self):
        from blindtag.widget import BlindTagWindow
        return BlindTagWindow()

    def test_posture_defaults_foreground(self, qapp) -> None:
        win = self._make_window()
        assert win._posture == "foreground"
        win.close()

    def test_hide_to_background_sets_posture_and_hides_window(self, qapp) -> None:
        win = self._make_window()
        win.show()
        win._hide_to_background()
        assert win._posture == "background"
        assert not win.isVisible()
        win.close()

    def test_show_event_resets_posture_to_foreground(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        win.show()
        assert win._posture == "foreground"
        win.close()

    def test_notify_payload_routes_bg_notif_in_background_posture(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        from unittest.mock import patch
        with patch.object(win._bg_notif, "show_for") as mock_show_for:
            win._notify_payload("secret message", "raw_encoded")
            mock_show_for.assert_called_once()
            call_arg = mock_show_for.call_args[0][0]
            assert "secret message" in call_arg or len(call_arg) <= 50
            assert mock_show_for.call_args.kwargs["persistent"] is True
        win.close()

    def test_notify_payload_routes_inline_banner_in_foreground_posture(self, qapp) -> None:
        win = self._make_window()
        win.show()
        win._posture = "foreground"
        from unittest.mock import patch
        with patch.object(win._bg_notif, "show_for") as mock_show_for:
            win._notify_payload("visible message", "raw_encoded")
            mock_show_for.assert_not_called()
        win.close()

    def test_close_event_stops_watcher_in_foreground_posture(self, qapp) -> None:
        win = self._make_window()
        win._posture = "foreground"
        win._toggle_watcher(True)
        win.close()
        assert not win._watcher_active

    def test_close_event_stops_watcher_in_background_posture(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        win._toggle_watcher(True)
        win.close()
        assert not win._watcher_active

    def test_close_event_tolerates_deleted_notification_widget(self, qapp) -> None:
        from PySide6.QtCore import QCoreApplication

        win = self._make_window()
        win._bg_notif.deleteLater()
        for _ in range(20):
            QCoreApplication.processEvents()
        win.close()

    def test_background_notification_is_recreated_if_deleted(self, qapp) -> None:
        from PySide6.QtCore import QCoreApplication

        win = self._make_window()
        win._bg_notif.deleteLater()
        for _ in range(20):
            QCoreApplication.processEvents()
        win._posture = "background"
        win._notify_payload("secret", "raw")
        assert win._bg_notif is not None
        assert win._bg_notif.isVisible()
        win.close()


class TestLibraryEditorColumns:
    def _make_panel(self, tmp_path):
        from PySide6.QtWidgets import QWidget

        class _StubParent(QWidget):
            def _return_from_editor(self) -> None:
                return None

        shutil.copy(_DEFAULT_LIBRARY_PATH, tmp_path / "emoji_library_default.json")
        lib = EmojiLibrary(tmp_path / "emoji_library_default.json")
        parent = _StubParent()
        panel = _LibraryEditorPanel(parent, lib)  # type: ignore[arg-type]
        panel.refresh()
        return panel, lib

    def test_row_shows_glyph_code_alias_label_columns(self, qapp, tmp_path) -> None:
        panel, lib = self._make_panel(tmp_path)
        row = panel._make_row(lib.load()[4])
        labels = [lbl.text() for lbl in row.findChildren(type(panel._validation_lbl))]
        assert "👎" in labels
        assert "U+1F44E" in labels
        assert ":thumbsdown:" in labels
        assert "thumbs down" in labels

    def test_codepoint_display_derived_from_emoji_char(self, qapp, tmp_path) -> None:
        panel, lib = self._make_panel(tmp_path)
        row = panel._make_row(lib.load()[2])
        labels = [lbl.text() for lbl in row.findChildren(type(panel._validation_lbl))]
        assert "U+2764 U+FE0F" in labels

    def test_add_row_accepts_glyph_input_and_derives_code(self, qapp, tmp_path) -> None:
        panel, lib = self._make_panel(tmp_path)
        panel._add_glyph_code.setText("🧪")
        panel._add_alias.setText(":test:")
        panel._add_label.setText("test tube")
        panel._do_add()
        added = lib.load()[-1]
        assert added["emoji"] == "🧪"
        assert added["alias"] == ":test:"
        assert _format_codepoints(added["emoji"]) == "U+1F9EA"

    def test_add_row_accepts_unicode_input_and_derives_glyph(self, qapp, tmp_path) -> None:
        panel, lib = self._make_panel(tmp_path)
        panel._add_glyph_code.setText("U+1F9EA")
        panel._add_alias.setText(":test:")
        panel._add_label.setText("test tube")
        panel._do_add()
        added = lib.load()[-1]
        assert added["emoji"] == "🧪"
        assert added["alias"] == ":test:"

    def test_add_row_rejects_alias_as_glyph_code_source(self, qapp, tmp_path) -> None:
        panel, lib = self._make_panel(tmp_path)
        before = len(lib.load())
        panel._add_glyph_code.setText(":thumbsdown:")
        panel._add_alias.setText(":test:")
        panel._add_label.setText("test")
        panel._do_add()
        assert len(lib.load()) == before
        assert "Glyph/code must be a glyph or U+XXXX token." in panel._validation_lbl.text()


class TestActionButtonCleanup:
    def _make_window(self):
        from blindtag.widget import BlindTagWindow
        return BlindTagWindow()

    def test_encode_panel_has_only_encode_and_copy_action(self, qapp) -> None:
        win = self._make_window()
        buttons = [b.text() for b in win._encode_panel.findChildren(type(win._btn_encode))]
        assert "Encode & Copy" in buttons
        assert "Encode" not in buttons
        assert "⬡  Obfuscate & Copy" not in buttons
        win.close()

    def test_decode_panel_has_only_decode_action(self, qapp) -> None:
        win = self._make_window()
        buttons = [b.text() for b in win._decode_panel.findChildren(type(win._btn_decode))]
        assert buttons.count("Decode") >= 1
        assert "⬇  Paste & Decode" not in buttons
        win.close()

    def test_mode_toggle_buttons_match_narrow_tab_contract(self, qapp) -> None:
        win = self._make_window()
        assert win._btn_encode.text() == "Encode"
        assert win._btn_decode.text() == "Decode"
        assert win._btn_encode.width() == 78
        assert win._btn_decode.width() == 78
        win.close()


class TestHiddenNotificationAnchor:
    def _make_window(self):
        from blindtag.widget import BlindTagWindow
        return BlindTagWindow()

    def test_hidden_notification_persists_until_dismissed_or_replaced(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        win._notify_payload("secret one", "raw1")
        assert win._bg_notif.isVisible()
        assert not win._bg_notif._timer.isActive()
        first_text = win._bg_notif._label.text()
        win._notify_payload("secret two", "raw2")
        assert win._bg_notif.isVisible()
        assert first_text != win._bg_notif._label.text()
        win.close()

    def test_hidden_notification_body_restores_main_window(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        win._notify_payload("secret", "raw_encoded")
        win._bg_notif.mousePressEvent(MagicMock())
        assert win.isVisible()
        assert win._posture == "foreground"
        assert win._stack.currentWidget() is win._decode_panel
        assert win._decode_output.toPlainText() == "secret"
        win.close()

    def test_hidden_notification_close_only_dismisses_anchor(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        win._notify_payload("secret", "raw_encoded")
        win._bg_notif._close_btn.click()
        assert not win._bg_notif.isVisible()
        assert not win.isVisible()
        win.close()

    def test_new_hidden_notification_replaces_previous_anchor(self, qapp) -> None:
        win = self._make_window()
        win._posture = "background"
        win._notify_payload("first secret", "raw1")
        win._notify_payload("second secret", "raw2")
        assert "second secret" in win._bg_notif._label.text()
        assert win._raw_input.toPlainText() == "raw2"
        assert win._decode_output.toPlainText() == "second secret"
        win.close()
