# Changelog

All notable changes to BlindTag are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- **Pass R elevated provenance hardening** — `blindtag/reporting.py` now ships explicit `operational` / `security` / `forensic` modes, provenance-grade retained fields, deny-by-default executable scope enforcement, tamper-evident record chaining, segment seals, verifier-friendly Ed25519 high-trust export verification, and sandbox-simulated handoff assessment for elevated export bundles (calamum `20260531T233221Z-blindtag-forensic`, adjacent `20260531T233239Z-blindtag-reporting`, `20260531T233256Z-blindtag-api`, full-suite `20260531T233314Z-blindtag-all`)
- **Pass J reporting substrate** — `blindtag/reporting.py` introduces a bounded JSONL-first retained operation ledger under `.blindtag/generated/reporting/`, controlled JSON/Markdown export packets with manifest/checksum sidecars, and optional privileged export signing via explicit shared-key request verification (calamum `20260531T230143Z-blindtag-reporting`, adjacent `20260531T230200Z-blindtag-api`, `20260531T230620Z-blindtag-cli`, full-suite `20260531T230637Z-blindtag-all`)
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
- BlindTag API reporting surfaces now accept `policy_mode` / `action_phase` filtering so elevated provenance exports and sandbox verification are reachable through the public localhost transport layer
- Sandbox-simulated elevated provenance tests now validate output content and final handoff-completion posture instead of behaving like upgraded smoke tests
- BlindTag CLI global logging bootstrap now ships: root `--log-level` and `--verbose` flags configure runtime logging without import-time handler attachment, while the widget path remains pinned to warning-level logging
- BlindTag API request correlation now uses a single per-request `X-Request-Id` value for both the response header and retained event records, so `/v1/log` can filter by the exact request that produced an encode/decode event
- Hidden background-posture relaunch anchor now fires immediately when the widget is hidden with Clip Watch active, so the operator gets the promised click-to-return notification before any later hidden payload hit replaces it (calamum `20260531T220215Z-blindtag-widget`, full-suite confirmation `20260531T220238Z-blindtag-all`)
- CLI confirmation surfaces now emit friendly structured stderr blocks for human runs while preserving clean stdout for text and JSON result contracts; handled CLI errors now include a structured next-action block, and launcher commands (`blindtag api`, `blindtag widget`) report a clearer handoff/start summary (calamum `20260531T214710Z-blindtag-cli`, full-suite confirmation `20260531T214732Z-blindtag-all`)
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

**Pass K** — COMPLETE (commit `1108b8f`, calamum `20260531T040957Z-blindtag-all`, `decision: go`, 147/147):
- Full palette migration from warm charcoal to cool-navy ecosystem tokens: `C_BG`, `C_SECONDARY`, `C_SURFACE`, `C_ACCENT`, `C_ACCENT_H`, `C_TEXT`, `C_MUTED`, `C_SUCCESS`, `C_WARNING`, `C_ERROR` updated to match polymath palette
- New `C_LINE = "#263546"` token added; all 8 hardcoded `#303030` occurrences replaced
- `_btn_primary_style`: `border: none` → `border: 1px solid {C_ACCENT}`; text color set to dark navy for contrast on cyan background
- `_btn_secondary_style`, `_toggle_inactive_style`: hardcoded hover colors replaced with `C_LINE`-derived values
- New helpers `_clip_watch_active_style()` / `_clip_watch_inactive_style()`: 2px brand-cyan border glow when active; muted idle state
- `QCheckBox` ("Clip Watch") replaced by checkable `QPushButton` with `toggled` signal; `_watcher_btn` replaces `_watcher_chk` in all callsites
- `run_widget()`: `app.setWindowIcon()` added using `assets/images/blindtag_thumbnail_basic.png` for correct frameless-window taskbar presence
- `QCheckBox` removed from PySide6.QtWidgets import block
- Docstring Visual Identity section and Panel Layout diagram updated to reflect new tokens and button notation

**Pass K (palette correction)** — COMPLETE (commit `be23088`, 147/147):
- All button fills replaced with depth-based design: primary action uses deep steel-teal `#14384f` (border `#2a6b85`, text `#c9e8ef`), hover `#1a4d68`
- `_clip_watch_active_style`: transparent background, text `#7ab8c9`, cyan border — no fill
- `_clip_watch_inactive_style`: transparent, muted text, `C_LINE` border — no fill
- `_toggle_active_style`: `#1c2d3d` surface + full-brightness `C_TEXT` — no accent fill
- `_toggle_inactive_style`: transparent, `C_MUTED` text, transparent border

**Pass L** — COMPLETE (commit `7635a52`, calamum `20260531T053853Z-blindtag-all`, `decision: go`, 147/147):
- `run_widget()`: `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Polymath.BlindTag.Widget.1")` added; Windows groups the taskbar button under the app icon
- `_GuidancePanel.__init__`: `setObjectName("guidance_panel")` + scoped QSS selector `QWidget#guidance_panel { ... }` prevent style bleed into adjacent panels
- `BlindTagWindow._make_row()` lambda: fixed `NameError: emoji_str`; default-argument capture `em=entry["emoji"]` applied
- `blindtag-widget` moved from `[project.scripts]` to `[project.gui-scripts]` in `pyproject.toml`; eliminates terminal window on Windows launch; `blindtag.cli._widget_shim` is the backing entry

**Pass I** — COMPLETE (calamum `20260531T060157Z-blindtag-all`, `decision: go`, 160/160):
- `blindtag/notification.py` (NEW) — `NotificationWidget`: ephemeral bottom-right corner notification for background monitoring posture; auto-dismiss after `NOTIFY_DURATION_MS`; body click restores main window; `×` button dismisses silently; hover pauses timer; zero import dependency on `widget.py`
- `BlindTagWindow._posture` state (`"foreground"` / `"background"`) controls routing in `_notify_payload`
- `BlindTagWindow._bg_notif: NotificationWidget` — single instance owned by `BlindTagWindow`, receives `show_for(preview)` calls while hidden
- `_TitleBar._btn_hide` — "Hide" button added; visible only when Clip Watch is active; click calls `_hide_to_background()`; `_toggle_watcher()` drives visibility
- `BlindTagWindow._hide_to_background()` — sets posture to `"background"` and hides window; watcher stays alive
- `BlindTagWindow.showEvent()` — resets posture to `"foreground"` on every window-show event
- `_on_clipboard_change` — self-detection guard added: if posture is foreground and window is active, clipboard changes from own encode operation are silently ignored
- `_notify_payload` — posture branch at top: background posture routes to `_bg_notif.show_for(preview)` and returns early; foreground path raises window and shows inline banner (palette-aligned steel-teal fill instead of cyan)
- `tests/test_widget.py`: added `TestNotificationWidget` (6 headless tests) and `TestBackgroundPosture` (7 tests); 147 → 160 total
- `catalog/test_definitions.json`: `blindtag-widget` notes updated to document new test classes

**Pass M** — COMPLETE (calamum `20260531T075058Z-blindtag-all`, `decision: go`):
- Encode panel simplified to a single primary action: `Encode & Copy`; redundant standalone `Encode` button removed
- Decode panel simplified to a single primary action: `Decode`; redundant `Paste & Decode` button removed; `Ctrl+Return` now routes directly to decode-in-place on the decode panel
- Hidden-mode clip-watch notifications changed from ephemeral toast behavior to a persistent click-to-relaunch anchor until dismissed or replaced
- Hidden-mode payload detection now pre-populates the decode panel before relaunch so the decoded result is already available when the window is restored
- Emoji library editor rows converted to display-only multi-column rows showing glyph/code, alias, and label
- Bottom add row now uses three creation-time fields only: `glyph/code`, `alias`, `label`; glyph and Unicode forms derive from each other at creation time; alias input is no longer treated as a glyph/code source
- `tests/test_widget.py`: added helper coverage for glyph/code parsing and display, library-editor add-row behavior, single-action button contract, and persistent hidden notification anchor behavior
- `catalog/test_definitions.json`: `blindtag-widget` notes updated to reflect Pass M coverage

**Pass N** — COMPLETE (initial Calamum gate `20260531T085159Z-blindtag-all`, later hidden-notification closure confirmed by `20260531T220238Z-blindtag-all`; operator live pass recorded 2026-05-31):
- Root CLI widget launchpoint restored as a supported compatibility launcher; in installed environments it should hand off to the dedicated `blindtag-widget` GUI surface instead of staying attached to the calling terminal
- `blindtag.cli._widget_shim` no longer delegates through the root parser; it launches the widget directly and rejects unsupported arguments
- Hidden notification window flags and show path hardened for Windows visibility (`Qt.WindowDoesNotAcceptFocus`, direct top-level launch path, `showNormal()`)
- Background-notification lifecycle now recreates deleted notification instances safely and tolerates notification teardown during the window close path
- Encode / Decode top toggles compacted further to a stricter width contract after the earlier 92px attempt missed the approved visual target
- `tests/test_cli.py`: root CLI widget launchpoint, dedicated widget-shim direct-launch, and argument-rejection contract covered
- `tests/test_widget.py`: added coverage for deleted notification recreation / close-path tolerance and updated compact top-toggle geometry contract
- `README.md`, `docs/CLI_SCHEMA.md`, and `catalog/test_definitions.json` updated to reflect the dedicated terminal-free widget surface, the restored CLI compatibility launcher, and the new Pass N regression boundaries

**Pass O** — COMPLETE (calamum `20260531T202826Z-blindtag-all`, `decision: go`; installed live operator pass recorded 2026-05-31):
- `BlindTagWindow` now retains the exact encoded composite in `_last_encoded_payload` and clears stale encode output/source state before every new encode attempt
- `_encode_and_copy()` now copies from the in-memory source of truth instead of re-reading only from the output widget, preventing stale-output false copies after failed encode attempts
- Clipboard writes now use bounded verification before success is reported; failure to verify produces a calm warning directing the operator to retry or copy manually from Output
- `_btn_ghost_style()` and `_EmojiFlyout` glyph cells now include explicit `:pressed` states so clicks read as real activation instead of hover-only motion
- `tests/test_widget.py`: added focused `TestClipboardTruthfulness` and `TestPressedStateStyling` coverage for verified copy success, stale clipboard refusal, and pressed-state style presence
- `catalog/test_definitions.json`: widget notes updated to include Pass O clipboard-truthfulness and pressed-state coverage

**Pass O.12 follow-up UI closure** — COMPLETE (calamum `20260531T210626Z-blindtag-all`, `decision: go`; installed live operator pass recorded 2026-05-31):

**Pass O.13 hide-anchor closure** — COMPLETE (calamum `20260531T220215Z-blindtag-widget`, full-suite confirmation `20260531T220238Z-blindtag-all`; operator live pass recorded 2026-05-31):
- `_hide_to_background()` now emits the persistent relaunch anchor immediately when the widget is hidden with Clip Watch active
- The hide-time relaunch anchor remains replaceable by later hidden payload notifications so the freshest hidden event still wins
- Retained artifact checksum verification succeeded for both runs; signing-env remained names-only absent (`CALAMUM_ED25519_PUBLIC_KEY=missing`, `CALAMUM_POLICY_SIGNING_KEY=missing`)
- Emoji flyout trigger now behaves as a true toggle: click once to open, click again to close
- Emoji flyout dismissal now supports conventional click-away closing through a broader application-level mouse filter
- Help drawer now raises the widget to full opacity while open and adds a dim scrim across the rest of the widget body for legibility
- Help cards now render on more opaque elevated surfaces for stronger text/background separation
- Ghost/menu pressed states and emoji-cell pressed states strengthened with a darker filled state and visible accent border so activation reads more clearly in live use
- Emoji selection now leaves the pressed state visible for a short paint cycle before dismissing the flyout
- `tests/test_widget.py`: added focused coverage for help scrim/opacity behavior, trigger-toggle flyout close behavior, and click-away dismissal

**Pass J** — COMPLETE (calamum `20260531T230143Z-blindtag-reporting`, adjacent reruns `20260531T230200Z-blindtag-api`, `20260531T230620Z-blindtag-cli`, full-suite `20260531T230637Z-blindtag-all`, all `decision: go`):
- `blindtag/reporting.py` (NEW) — append-only JSONL retained event store, read-only filter/query helpers, controlled JSON/Markdown export artifact families, checksum sidecars, and optional privileged shared-key export verification
- `blindtag/api.py` — `X-Request-Id` continuity now survives into retained event records; API-owned encode/decode/query/export events are persisted locally; new `GET /v1/log` and `POST /v1/log/export` surfaces added
- `blindtag/cli.py` — global `--log-level` and `--verbose` bootstrap shipped; widget route remains pinned to warning-level logging regardless of root flag
- `blindtag/core.py` — quiet module logger reservation added with no import-time handler attachment
- `tests/test_reporting.py` (NEW) — focused retained store / export / signing coverage
- `tests/test_api.py` — new reporting endpoint coverage and fail-closed export trust gate coverage
- `tests/test_cli.py` — root logging flag coverage added, including widget warning-level override behavior
- `.gitignore` — `.blindtag/` retained reporting outputs kept local-only
- `catalog/test_definitions.json` — `blindtag-reporting` Calamum definition added

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
