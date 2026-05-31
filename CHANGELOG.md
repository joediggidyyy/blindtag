# Changelog

All notable changes to BlindTag are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- **Unified CLI** (`blindtag.cli`) — `blindtag` root entry point with `encode`, `decode`, `strip`, `api`, and `widget` subcommands; `--out {text,json}` flag; stdin piping via `-`; locked exit-code contract (0 success, 1 domain error, 2 usage error); see [docs/CLI_SCHEMA.md](docs/CLI_SCHEMA.md) (Pass C — `69cdda4`)
- `blindtag/__main__.py` — enables `python -m blindtag` invocation (Pass C — `69cdda4`)
- `blindtag-api` and `blindtag-widget` console scripts demoted to compat shims delegating to `blindtag.cli` (Pass C — `69cdda4`)
- `blindtag-cli` Calamum test definition added to `catalog/test_definitions.json`; 25 contract tests in `tests/test_cli.py` covering all subcommands, exit codes, JSON output, stdin piping, and shim delegation (Pass C — `69cdda4`, calamum evidence `20260530T202620Z-blindtag-all`)
- CLI design schema locked at [docs/CLI_SCHEMA.md](docs/CLI_SCHEMA.md); implementation record at [docs/CLI_IMPLEMENTATION_CHECKLIST.md](docs/CLI_IMPLEMENTATION_CHECKLIST.md) (planning pass — `3ab3a26`)
- `.env.example` placeholder (Pass A — `181610d`)
- GitHub Actions CI workflow (Pass A — `181610d`)
- Calamum test catalog (`catalog/test_definitions.json`) with `blindtag-core`, `blindtag-api`, `blindtag-all` definitions (Pass A — `181610d`)
- `SECURITY.md` security policy (Pass A — `181610d`)
- `DecodingError` and `InvalidPayloadError` test coverage in `tests/test_core.py` (Pass B — `5a7daf9`)
- CORS integration test coverage in `tests/test_api.py` (Pass B — `5a7daf9`)
- `TAG_CANCEL` round-trip assertion fix in `tests/test_core.py` (Pass B — `5a7daf9`)

### Fixed
- Stale `run_widget.py` docstring: replaced `customtkinter`/`pyperclip`/Linux xclip references with PySide6 requirements (Pass C — `69cdda4`)
- Stale `blindtag/__init__.py` module docstring: widget description updated from `(customtkinter)` to `(PySide6)` (Pass C — `69cdda4`)
- `README.md`: architecture block and Linux clipboard section updated to reflect PySide6 rewrite (planning pass — `3ab3a26`)

**Pass D** — COMPLETE (calamum `20260530T220231Z-blindtag-all`, `decision: go`; see [docs/WIDGET_IMPLEMENTATION_CHECKLIST.md](docs/WIDGET_IMPLEMENTATION_CHECKLIST.md) and [docs/WIDGET_SCHEMA.md](docs/WIDGET_SCHEMA.md)):
- **Widget guidance panel** — left-side slide-out `?` panel with collapsed problem-definition cards (Anchor text, Hidden payload, Emoji aliases, Obfuscate & Copy, Clip Watch)
- **Emoji alias selector** — inline `☺` trigger on the Hidden Payload row; floating `QFrame` flyout showing emoji glyphs only; clicking appends the entry's active alias (printable ASCII) to the payload field
- **Emoji library editor** — fourth panel in `_stack`, accessible from flyout `Edit library` link; per-entry: glyph display, active alias indicator, `codes` pick list, label, delete; add-entry form; all writes go directly to `assets/emoji_library_default.json`
- `assets/emoji_library_default.json` — 20-entry curated default library, tracked and versioned, shipped pre-populated with `codes` arrays; single working library
- `blindtag-widget` Calamum test definition added to `catalog/test_definitions.json`
- `tests/conftest.py` — session-scoped `qapp` fixture for PySide6 widget tests
- `tests/test_widget.py` — `TestEmojiLibrary` (headless, 9 tests), `TestGuidancePanel` (3), `TestEmojiFlyout` (3); 15/15 pass

### Planned

**Pass E** — COMPLETE (calamum `20260530T225738Z-blindtag-all`, `decision: go`):
- Added `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `X-Request-Id` (UUID4 per request) response headers via `@app.middleware("http")` in `blindtag/api.py`
- Added `TestSecurityHeaders` class to `tests/test_api.py` (7 tests: content-type-options on health + encode, frame-options on health + encode, request-id UUID4 format, request-id uniqueness per call, headers present on 422 error responses)

**Pass F** — COMPLETE (calamum `20260530T230757Z-blindtag-all`, `decision: go`):
- `test_tag_cancel_as_only_plane14_char_no_crash`: tightened assertion from `is None or == ""` to `is None` (dead branch removed; decode contract is deterministic)
- Removed `from typing import Optional` from `blindtag/core.py`; return type of `decode()` updated to `str | None`
- Added `__all__` export list to `blindtag/core.py` (8 public names: constants + codec functions)

**Pass G** — COMPLETE (commit `3f41967`, calamum `20260530T234925Z-blindtag-all`, `decision: go`):
- `BlindTagWindow.__init__`: added `?` title-bar button wired to `_GuidancePanel` toggle; added `☺` inline trigger on anchor row opening `_EmojiFlyout`; `_EmojiFlyout` callback registered as `_insert_alias` (superseded in Pass H)
- `_GuidancePanel` — left-side slide-out overlay, `_EmojiCard` collapsible cards, 5 entries matching `_CARD_CONTENT`
- `_EmojiFlyout` — floating glyph-grid with 20 cells, tooltip shows active alias, `Edit library ⚙` footer link
- `_LibraryEditorPanel` — fourth stack panel; per-entry rows with glyph, active alias, codes pick list, label, delete; add-entry form; writes to `assets/emoji_library_default.json`
- `tests/test_widget.py`: 15 tests passing (9 `TestEmojiLibrary` + 3 `TestGuidancePanel` + 3 `TestEmojiFlyout`)

**Pass H** — COMPLETE (commit `d2415ca`, calamum `20260531T020332Z-blindtag-all`, `decision: go`):
- `_resolve_anchor_tokens(text, library)` — new module-level pure function; resolves `U+XXXX` tokens to Unicode chars (with invalid codepoint / surrogate pass-through safety) and `:alias:` tokens to glyphs via library lookup; bare uppercase excluded to prevent natural-language collisions; headless-testable with no Qt dependency
- `_EmojiFlyout._pick`: passes raw emoji glyph to `on_select` callback (was alias string)
- `BlindTagWindow._insert_alias` renamed to `_insert_emoji(emoji: str)`: single-field insert — glyph into `_anchor_input` only; `_hidden_input` untouched
- `BlindTagWindow._do_encode`: now calls `strip_plane14(anchor)` before encoding (prevents silent double-encoding from pasted tagged strings) and `_resolve_anchor_tokens(anchor, self._library)` before `core.encode()`
- `_CARD_CONTENT[2]` ("Emoji aliases") body updated to reflect format-agnostic anchor input and resolution pipeline
- `tests/test_widget.py`: added `test_cell_count_matches_library`, `test_click_inserts_glyph` (replaces dual-field `test_click_appends_alias`), `TestEncodeResolution` class (7 headless tests)
- `catalog/test_definitions.json` `blindtag-widget` notes updated to reflect glyph-insert contract and `TestEncodeResolution` scope



## [1.0.0] — 2026-05-30

### Added
- Core Plane 14 steganographic codec engine (`blindtag.core`)
- FastAPI local transport layer with `/encode`, `/decode`, `/strip`, `/health` endpoints (`blindtag.api`)
- Desktop observer widget with live clipboard detection (`blindtag.widget`)
- Domain exception hierarchy (`blindtag.exceptions`)
- CLI launchers `blindtag-api` and `blindtag-widget`
- Full pytest suite — core round-trip, adversarial, normalization, and API integration tests
