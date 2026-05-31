# BlindTag — Polymath Maturity Review & Update Plan

**Date:** 2026-05-30  
**Reviewer:** ORACL  
**Status:** Pre-push baseline — no code changes applied this pass  
**Target:** Polymath-level maturity before public release

---

## TL;DR

The codec engine and API are well-written and the test suite is thorough for the happy-path and adversarial-input lanes. The primary gaps are: missing Calamum test configuration, no CI pipeline, an unresolved test ambiguity in the TAG_CANCEL-only case, absent widget tests, a deprecated build backend declaration, missing project metadata in `pyproject.toml`, no `.env.example`, no request tracing on the API, and no GitHub Actions workflow. All are plannable; none require architectural changes.

---

## Section 1 — Code Review Findings

### 1.1 `blindtag/core.py` — PASS with minor notes

| Finding | Severity | Notes |
|---------|----------|-------|
| Logic is sound; encode/decode/strip are unambiguous | — | Good |
| `PLANE14_MIN` / `PLANE14_MAX` constants declared but not used in public API surface | Low | Useful for external callers; keep but document intent |
| `Optional` imported from `typing` — should be `str \| None` (Python 3.11+) | Low | Cleanup item for code-change pass |
| No `__all__` export list | Low | Add to lock the public surface |

### 1.2 `blindtag/api.py` — PASS with security notes

| Finding | Severity | Notes |
|---------|----------|-------|
| Pydantic validation + InvalidPayloadError handler in place | — | Good |
| CORS restricted to localhost origins | — | Good |
| No request ID / trace header on responses | Medium | Polymath style: every API response should carry a `X-Request-Id` or equivalent for retained-evidence tracing |
| No rate limiting | Low | Localhost-only mitigates; note as accepted risk in SECURITY.md |
| No `X-Content-Type-Options: nosniff` or security headers | Low | Standard hardening for any HTTP surface |
| `run_server()` entry point in `api.py` — not visible in the portion read | Verify | Confirm this function exists; `pyproject.toml` script references it |
| No version header in health response beyond JSON body | Low | Consider `X-BlindTag-Version` header for client negotiation |

### 1.3 `blindtag/widget.py` — NOT REVIEWED (GUI, excluded from coverage)

| Finding | Severity | Notes |
|---------|----------|-------|
| Zero test coverage | Medium | At minimum: smoke tests for `encode`/`decode` plumbing through widget logic; full GUI not required |
| Clipboard watcher daemon thread — no documented stop condition beyond app close | Low | Document the shutdown contract explicitly |

### 1.4 `blindtag/exceptions.py` — PASS

Clean hierarchy. `DecodingError` is defined but verify it is raised in the decode path for out-of-range bytes (test coverage gap identified in Section 2).

---

## Section 2 — Test Suite Review

### 2.1 `tests/test_core.py` — STRONG, two gaps

| Finding | Severity | Action |
|---------|----------|--------|
| `TestDecodeNoPayload.test_only_tag_cancel_yields_none_or_empty` uses `assert result is None or result == ""` — ambiguous OR | Medium | **Resolve the contract:** TAG_CANCEL with no preceding payload chars should be `None` (no payload found). Update assertion to `assert result is None`. |
| `DecodingError` is never exercised in test suite | Medium | Add `TestCrashImmunity` case: feed a synthetic Plane 14 sequence outside ASCII range (e.g. U+E007F+1 if reachable) to verify `DecodingError` is raised rather than swallowed |
| No test for `encode()` called with empty hidden_message="" — currently raises `ValueError` | Low | Verify intent: should this raise `InvalidPayloadError` instead for consistency? |

### 2.2 `tests/test_api.py` — GOOD, three gaps

| Finding | Severity | Action |
|---------|----------|--------|
| No test for CORS headers (OPTIONS preflight, or `Origin` header response) | Low | Add `TestCORSPolicy` class |
| No test exercising the `InvalidPayloadError` handler path directly (the Pydantic validator catches first) | Low | Send a request where Pydantic passes but core raises — construct a raw request bypassing validator |
| No test for `GET /openapi.json` accessibility (important for tooling integrations) | Low | Add to `TestHealthEndpoint` |

### 2.3 Widget tests — ABSENT

No `tests/test_widget.py` exists. Minimum required:
- Import smoke test (widget module loads without GUI)
- Encode/decode plumbing tests via widget's internal logic (not the GUI layer)
- Clipboard watcher thread lifecycle (start/stop contract)

---

## Section 3 — Calamum Integration

### 3.1 Current state

No Calamum test configuration exists in the repository. Per CodeSentinel policy, all code changes require validation through `calamum test` — ad hoc `pytest` alone is not sufficient.

### 3.2 Required artifacts

| Artifact | Path | Notes |
|----------|------|-------|
| Calamum catalog JSON | `calamum_catalog.json` (root) | Defines the test suite lanes and run config |
| Test run evidence dir | `report_tmp/` (gitignored) | Per project precedent |

### 3.3 Minimum catalog definition (plan only)

The catalog should register at minimum two lanes:
1. **`core`** — `pytest tests/test_core.py` — codec engine tests
2. **`api`** — `pytest tests/test_api.py` — API integration tests

With a combined rollup lane `all` running both. Evidence from `calamum test run all` becomes the baseline pass receipt for the pre-push gate.

---

## Section 4 — Polymath Security Alignment

Reference: `docs/guides/POLYMATH_SECURITY_MEASURES_AND_EXPECTATIONS.md`

| Invariant | Status | Gap / Action |
|-----------|--------|-------------|
| 1. No secrets in source control | PASS | `.gitignore` covers `.env*` |
| 2. Environment is the keyring | N/A | No secrets required at runtime currently; document if API auth is added |
| 3. Names-only documentation | PASS | No values exposed anywhere |
| 4. Agents do not read secret material | PASS | No vault or secret reads |
| 5. Fail closed on trust ambiguity | DEFERRED | API has no auth layer. **Framing this as a permanent "localhost-only" design decision is premature** — a reporting layer is planned post-widget that will require revisiting API transport scope, auth, and exposure model. Do NOT lock localhost-only into SECURITY.md until the reporting layer scope is defined. |
| 6. Protected secret stores — integrity controls | N/A | No secret store |
| 7. Sensitive state changes require authorization | N/A | No state mutations; document for future API auth additions |
| 8. Retained evidence must be verifiable | GAP | API responses carry no checksums or request IDs; plan `X-Request-Id` header |
| 9. Path containment enforced | PASS | No file I/O in codec or API |
| 10. Security messaging useful and secret-safe | PASS | Error messages describe constraint without leaking values |

**Additional gap:** No `.env.example` file. Polymath standard requires one even when the current version has no secrets, to establish the pattern for future additions.

**Scope note:** The reporting layer planned in Section 9 will introduce new invariant touchpoints (auth, retained evidence, signed responses). Security invariants 2, 5, 7, and 8 must be re-evaluated against that layer's design before any final SECURITY.md settlement.

---

## Section 5 — Polymath Style & Formatting Alignment

Reference: `docs/guides/POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md`

| Surface | Status | Gap / Action |
|---------|--------|-------------|
| API error responses — structured JSON with reason + detail | PASS | `error_type` + `detail` fields present |
| API success responses — complete schema | PASS | All four questions answerable from response body |
| CLI launcher `run_api.py` — help text | Verify | Confirm `--help` output meets style contract |
| CLI launcher `run_widget.py` — help text | Verify | Same |
| Health endpoint — version in response | PASS | `version` field present |
| API response: "what happened / why / next action" contract | PARTIAL | Decode miss response has `detail` string but no `next_action` field guidance |

---

## Section 6 — Package Metadata & Build

### 6.1 `pyproject.toml` gaps

| Gap | Severity | Fix |
|-----|----------|-----|
| `setuptools.backends.legacy:build` is deprecated | Medium | Change to `setuptools.build_meta` |
| No `[project.authors]` field | Medium | Add `authors = [{name = "Polymath", email = "dev@polymath-global.com"}]` |
| No `[project.urls]` section | Medium | Add Homepage, Source, Issues URLs |
| No trove classifiers | Low | Add Python version, OS, topic classifiers |
| No `ruff` or `mypy` config section | Low | Add for lint/type-check consistency |

### 6.2 Missing files

| File | Action |
|------|--------|
| `.env.example` | Create — placeholder only, no values |
| `docs/` directory | Create — currently only `REVIEW_AND_MATURITY_PLAN.md` exists |
| `.github/workflows/ci.yml` | Create — run `pytest tests/` on push to main |
| `docs/CALAMUM_BASELINE.md` | Create after first `calamum test` run passes |

---

## Section 7 — CI Pipeline

No GitHub Actions workflow exists. Minimum required:

```
.github/
  workflows/
    ci.yml      → trigger on push + PR to main; matrix: python 3.11, 3.12
                  steps: checkout → pip install .[dev] → pytest tests/ -v --tb=short
```

---

## Section 8 — CHANGELOG

Current `CHANGELOG.md` has only the `[1.0.0]` release entry. Per Keep-a-Changelog convention, add an `[Unreleased]` section at the top to capture work in progress before the next tagged release.

---

## Prioritized Execution Plan

### Pass A — Document & config updates (no code changes, run this pass first)
1. Update `pyproject.toml`: fix build backend, add authors/URLs/classifiers
2. Create `.env.example` (empty placeholder with comment block)
3. Add `[Unreleased]` section to `CHANGELOG.md`
4. Create `.github/workflows/ci.yml`
5. Create `calamum_catalog.json` (minimal two-lane definition)
6. Update `SECURITY.md`: document localhost-only as explicit design decision; document accepted risk on rate limiting
7. Add `report_tmp/` to `.gitignore`

### Pass B — Test gap fills (code changes to test files only)
1. Resolve `test_only_tag_cancel_yields_none_or_empty` ambiguity → `assert result is None`
2. Add `TestDecodingError` class to `test_core.py`
3. Add `TestCORSPolicy` class to `test_api.py`
4. Add `tests/test_widget.py` — import smoke + plumbing tests (no GUI)
5. Verify `DecodingError` is raised (not swallowed) in decode path

### Pass C — Code hardening (code changes to source)
1. Add `X-Request-Id` response header to API
2. Add security headers (`X-Content-Type-Options`, `X-Frame-Options`)
3. Fix `Optional` → `str | None` annotation style
4. Add `__all__` to `blindtag/core.py` and `blindtag/__init__.py`
5. Fix build backend in `pyproject.toml`
6. **Add logging hook reservation**: wire `logging.getLogger("blindtag")` in `blindtag/cli.py` via `_configure_logging()`; add `logging.getLogger(__name__)` calls (no handler attachment) to `core.py` and `api.py`; see CLI_SCHEMA.md — Implementation notes — Logging architecture for the exact contract. This hook is required so Pass J can attach the structured handler without CLI code changes.

### Pass D — Calamum baseline
1. Install/configure Calamum in the blindtag venv
2. Run `calamum test run all`
3. Capture pass receipt as `docs/CALAMUM_BASELINE.md`
4. Commit evidence

### Pass E — Force push to GitHub (post baseline)
1. `git push --force origin main` (joediggidyyy sign-off required)
2. Verify GitHub Actions CI passes on arrival

### Pass I — Background monitoring posture & notification widget (widget enhancement)

**Status:** Plan locked. Implementation authorized; execute after Pass H gate confirmed.

**Scope:** Extend `BlindTagWindow` with a "background" posture — explicit hide, watcher stays alive, focus-stealing notification replaced by a custom ephemeral corner `NotificationWidget`. No new entry point, no `QSystemTrayIcon`, no new dependencies. All behavior lives inside the existing `blindtag-widget` entry point.

**Architecture driver:** `hide()` does not trigger `closeEvent`, so the `dataChanged` signal stays connected and the watcher runs. Two pieces were missing: (a) a non-intrusive notification surface for when the window is hidden, and (b) an explicit "Hide" transition distinct from minimize and close.

---

#### I.1 — Posture model

| Posture | Window state | Watcher | Notification |
|---|---|---|---|
| `"foreground"` | Visible, always-on-top | Active or idle | Inline blue `QLabel` banner (current `_notify_payload`) |
| `"background"` | Hidden, in taskbar | Active | `NotificationWidget.show_for(preview)` |

**Transitions:**
- **→ background:** Clip Watch checkbox checked + user clicks "Hide" button in title bar. `self.hide()`, `_posture = "background"`.
- **→ foreground:** User clicks `NotificationWidget` body. `main_win.show()` / `raise_()` / `activateWindow()`, `_posture = "foreground"`. Or: user clicks taskbar entry (Qt delivers normal show/restore event).
- **Close (X):** Always a real close — `_stop_watcher()`, `super().closeEvent(event)`. No interception. `closeEvent` is **unchanged**.

`BlindTagWindow` carries no `Qt.Tool` flag today (confirmed in source). Hidden windows without `Qt.Tool` remain in the Windows taskbar — this is the free "still running" indicator.

---

#### I.2 — New file: `blindtag/notification.py`

```python
# blindtag/notification.py
"""
blindtag.notification
=====================
Ephemeral bottom-right corner notification for background monitoring posture.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow

NOTIFY_MARGIN_PX: int = 16
CLOSE_BTN_TEXT: str = "×"


class NotificationWidget(QWidget):
    """Single-instance, single-use corner notification owned by BlindTagWindow."""

    def __init__(self, main_win: QMainWindow, duration_ms: int) -> None:
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self._main_win = main_win
        self._duration_ms = duration_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        self._label = QLabel("BlindTag — Payload detected")
        close_btn = QPushButton(CLOSE_BTN_TEXT)
        close_btn.setFixedSize(20, 20)
        close_btn.setFlat(True)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(self._label)
        layout.addWidget(close_btn)
        self.adjustSize()

    def show_for(self, preview: str) -> None:
        self._label.setText(f"⬡  BlindTag  ·  {preview}")
        self.adjustSize()
        self._reposition()
        self._timer.start(self._duration_ms)
        self.show()
        self.raise_()

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.right() - self.width() - NOTIFY_MARGIN_PX,
            geo.bottom() - self.height() - NOTIFY_MARGIN_PX,
        )

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.hide()
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._timer.start(self._duration_ms)
```

**Notes:**
- `QGuiApplication.primaryScreen()` is used for positioning (avoids the `QScreen.virtualSiblingAt` pattern which requires an existing window position).
- The `×` close button dismisses without opening the widget.
- The body click opens the widget.
- Timer is restarted on `leave`, not on `show_for` — hover always resets the full duration.

---

#### I.3 — `BlindTagWindow` changes (exact integration points)

**State to add in `__init__`:**
```python
self._posture: str = "foreground"
self._bg_notif: NotificationWidget = NotificationWidget(self, NOTIFY_DURATION_MS)
```
`NotificationWidget` is imported at top of `widget.py`: `from .notification import NotificationWidget`.

**`_notify_payload` — posture branch (lines ~1274–1301 today):**

Current code always raises the window. Add branch before `self.raise_()`:
```python
if self._posture == "background":
    preview = message[:48] + ("…" if len(message) > 48 else "")
    self._bg_notif.show_for(preview)
    return   # do not raise window; do not show inline banner
# existing foreground path follows unchanged
```

**"Hide" button — title bar:**

Shown only while Clip Watch is checked. Visibility is toggled inside `_toggle_watcher` (which already calls `_start_watcher` / `_stop_watcher`). The button is part of the existing frameless title bar widget. Label: `"Hide"`. Tooltip: `"Run in background — click notification to return"`.

Click handler:
```python
def _hide_to_background(self) -> None:
    self._posture = "background"
    self.hide()
```

When the user reopens the window (via notification click or taskbar), reset posture:
```python
def showEvent(self, event) -> None:  # override
    self._posture = "foreground"
    super().showEvent(event)
```

**`closeEvent` — no change required.** Existing code (`_stop_watcher()` + `super().closeEvent(event)`) is correct and sufficient.

---

#### I.4 — Self-detection guard

Guard already described in §I.6 (previous draft) — simplified here:

In `_on_clipboard_change`, add before calling `_notify_payload`:
```python
# Suppress self-detection: window is open and focused → user sees encode result directly
if self._posture == "foreground" and self.isActiveWindow():
    return
```

This is a one-line gate already available in current code structure (lines ~1260–1270).

---

#### I.5 — "Watcher alive" without tray icon

Confirmed: `BlindTagWindow` uses `Qt.FramelessWindowHint | Qt.Window` only — no `Qt.Tool`. Hidden windows without `Qt.Tool` remain in the Windows taskbar. Taskbar entry is the presence indicator and click-to-raise recovery path. No additional indicator needed.

---

#### I.6 — Calamum test contract

**No new catalog entry required.** `NotificationWidget` and background-posture behavior are tested under `blindtag-widget` (`tests/test_widget.py`). `blindtag-all` rollup covers it automatically.

**`catalog/test_definitions.json` — update `blindtag-widget` notes field only:**

Change `notes` in the `widget-pytest` lane from current value to:
```
EmojiLibrary schema, validation, add/remove, alias selection (headless).
GuidancePanel and EmojiFlyout smokes via QApplication fixture.
TestEncodeResolution: U+XXXX and :alias: resolve pipeline, passthrough for invalid/unknown tokens (headless).
TestNotificationWidget: construction, show_for label, timer auto-dismiss, body-click callback, hover pause, close-button dismiss-only (all headless with mocked main_win).
TestBackgroundPosture: _posture default, Hide button triggers hide+posture, _notify_payload routes to NotificationWidget in background posture, showEvent resets posture to foreground, closeEvent stops watcher in both postures.
```

**New test classes — `tests/test_widget.py`:**

```
TestNotificationWidget   (headless — mock main_win as MagicMock())
  test_construction_no_error
  test_show_for_sets_label_text
  test_timer_fires_hide           (QTest.qWait or direct timeout.emit())
  test_body_click_shows_main_win  (assert mock.show/raise_/activateWindow called)
  test_hover_pauses_timer         (enterEvent stops timer; leaveEvent restarts)
  test_close_button_hides_only    (× button: hide called, main_win.show NOT called)

TestBackgroundPosture    (requires qapp fixture; BlindTagWindow instantiated)
  test_posture_defaults_foreground
  test_hide_to_background_sets_posture_and_hides_window
  test_show_event_resets_posture_to_foreground
  test_notify_payload_routes_bg_notif_in_background_posture
  test_notify_payload_routes_inline_banner_in_foreground_posture
  test_close_event_stops_watcher_in_foreground_posture
  test_close_event_stops_watcher_in_background_posture
```

All `TestNotificationWidget` tests are headless — `NotificationWidget` is instantiated with a `MagicMock()` as `main_win`; no window is shown to screen. `TestBackgroundPosture` requires the session-scoped `qapp` fixture (already in `conftest.py`).

---

#### I.7 — Polymath security alignment

| Invariant | Assessment |
|---|---|
| 1. No secrets in source control | PASS — no new credentials, keys, or secrets introduced |
| 2. Environment is the keyring | N/A — no secrets at runtime in this pass |
| 3. Names-only documentation | PASS — plan documents class/method names only |
| 4. Agents do not read secret material | PASS |
| 5. Fail closed on trust ambiguity | PASS — no trust surface introduced; notification shows 48-char excerpt only; `decode()` called on clipboard text as before |
| 6. Protected stores require integrity controls | N/A |
| 7. Sensitive state changes require explicit authorization | PASS — posture change is explicit user button click; no silent background transitions |
| 8. Retained evidence must be verifiable | PASS — calamum gate produces verifiable `report.json` + stdout/stderr; no new evidence artifacts escape outside `calamum` control |
| 9. Path containment enforced | PASS — `notification.py` reads no files; writes no files; no new file I/O |
| 10. Security messaging useful and secret-safe | PASS — `NotificationWidget` shows `preview[:48]` only, same truncation rule as existing `_notify_payload` |

No new SEAM blockers.

---

#### I.8 — Polymath style alignment

`NotificationWidget` body follows the operator contract (what happened / excerpt / implied next action):

```
⬡  BlindTag  ·  "hello, world…"      [×]
```

- **What happened:** payload detected
- **Excerpt:** first 48 chars, truncated with `…`
- **Why / next action:** click body → widget opens to full decode view
- **Where is evidence:** widget Decode panel on open; calamum run log for test evidence

Contract met for all five questions.

---

#### I.9 — Out of scope for this pass

- `QSystemTrayIcon` / tray icon (deferred — see Section 10)
- Auto-start on login (requires tray process; deferred)
- macOS / Linux platform-specific notification APIs
- Simultaneous notification stacking (single-instance widget; last-write wins)
- Notification persistence / history log (deferred to Pass J)

---

#### I.10 — `pyproject.toml`

No change. No new entry point.

---

#### I.11 — Deliverables and sequence

| # | Artifact | Action | Dependency |
|---|---|---|---|
| 1 | `blindtag/notification.py` | CREATE | None |
| 2 | `blindtag/widget.py` | MODIFY | Requires (1) — import `NotificationWidget`; add `_posture`, `_bg_notif`; branch in `_notify_payload`; "Hide" button; `showEvent`; self-detection guard |
| 3 | `tests/test_widget.py` | MODIFY | Requires (1)(2) — add `TestNotificationWidget` + `TestBackgroundPosture` |
| 4 | `catalog/test_definitions.json` | MODIFY | Requires (3) — update `blindtag-widget` notes field |
| 5 | `CHANGELOG.md` | MODIFY | Requires gate pass |
| **Gate** | `calamum test run blindtag-all --project <path>` | RUN | After (1–4); `decision: go` required before (5) and commit |

Execute in order. No parallelism needed — each step is small.

---

### Pass J — Logging and reporting infrastructure (scope definition in this session; implementation follows Pass H)

Blindtag's primary use model is **imported and used via API by other applications**. This pass delivers dense, structured, tiered logging and reporting. Known inputs:
- Structured log handler attached to `logging.getLogger("blindtag")` at API/CLI startup
- Per-operation log entries: timestamp, operation type, anchor/payload lengths, resolved token count, outcome
- Tiered severity: `debug` through `critical` all meaningful; widget is always `warning`-silent
- CLI `--log-level` raises verbosity; retained log queryable via API reporting endpoints
- Storage layer and auth/transport scope TBD in scoping session
- Security invariants 2, 5, 7, 8 re-evaluated against final transport/auth model
- New calamum catalog lanes for the reporting surface

**Pass J begins only after Pass H calamum gate is confirmed.**

---

## Section 9 — Planned: Backend/API Reporting Layer

**Status:** Placeholder — scope not yet defined. Planning deferred until Pass H (widget) is complete and gated.

**Primary use model:** blindtag is designed to be **imported and used via API by other applications** — not as a standalone personal tool. The widget is a convenience surface; the API and importable core are the canonical consumption path. This changes the logging and reporting requirements significantly: callers need dense, structured, tiered operation evidence, not casual human-readable output.

**Logging and reporting requirements (known inputs, not final decisions):**

| Requirement | Detail |
|-------------|--------|
| Tiered logging | `debug`, `info`, `warning`, `error`, `critical` — all five levels used deliberately |
| Default level | `warning` for widget and library import; `info` for API server; `debug` available via CLI |
| CLI control | `blindtag --log-level debug` raises verbosity for any subcommand except widget |
| Library import safety | No handler attached at import time — library callers own their logging config |
| Structured output | Operation log entries carry: timestamp, operation type, anchor length, payload length, resolved token count, outcome, error type if any |
| Retained evidence | Every API encode/decode call produces a retained log entry queryable by callers |
| Severity filtering | Callers can request only `error`+ events or full `debug` traces |
| API reporting endpoints | `/log`, `/log/export`, or equivalent — exact shape TBD in scoping session |
| Storage layer | Not selected — append-only structured log file, SQLite, or equivalent |
| Auth/transport scope | Not settled — see invariant 5 DEFERRED status above |

The logging hook reservation (logger namespace, no handler at import, `_configure_logging` in CLI) is implemented in Pass C. The full structured handler, retention, and reporting endpoints are implemented in Pass J.

**Do not begin Pass J scope definition until joediggidyyy initiates the planning session after Pass H gate.**

---

## Section 10 — Deferred: System Tray Background Process (`blindtag-tray`)

**Status:** Deferred. Preserved for future development after Pass I (widget-based path) is complete.

**Why deferred:** The widget-based background posture (Pass I) satisfies the core monitoring use case without a separate entry point, `QSystemTrayIcon`, or new dependencies. The tray-hosted process adds auto-start-on-login and no-taskbar-presence; these are desirable but not required for the initial background monitoring delivery.

**Trigger for re-opening:** After Pass I is gated and shipped, initiate tray planning if any of the following are needed:
- Auto-start on login (requires a persistent entry point independent of the widget process)
- Full no-taskbar background presence (Qt.Tool + tray replaces taskbar row)
- Pause/resume watcher without opening the window
- Per-platform notification surface (macOS UserNotifications, Linux libnotify)

### Preserved design decisions (deferred, not discarded)

| Decision | Choice | Rationale |
|---|---|---|
| Tray icon | `assets/images/blindtag_thumbnail_basic.png` | Confirmed present; thumbnail variant is correct size for tray |
| Process model | Single process, not a daemon/service | Qt clipboard signal requires a user-session message loop; services have no clipboard access |
| Widget-in-tray | Same process, `BlindTagWindow` held live | Instant open, shared library state, zero IPC surface |
| Auto-start method | `winreg HKCU\...\Run` (Windows); deferred macOS/Linux | stdlib `winreg`, no installer needed, user-session only |
| Self-detection guard | Skip toast if widget is visible and frontmost | Simple boolean check; eliminates noise on encode without timing heuristics |
| Close behavior | Widget close hides (not destroys) when `_tray_mode = True` | Keeps window reusable from tray without re-instantiation |
| Entry point | `blindtag-tray = "blindtag.tray:run_tray"` in `pyproject.toml` | New script, no conflict with widget path |
| Platform scope | Windows primary; macOS/Linux deferred | Auto-start is platform-specific; Qt tray works cross-platform but autostart deferred |

### Preserved test scope (for when this pass is activated)

`tests/test_tray.py` — headless, ~60 lines: `TestTrayConstruction`, `TestTrayDecodeHook`, `TestTrayPause`, `TestAutoStartWindows` (mocked `winreg`). New calamum catalog entry `blindtag-tray` needed (definition previously drafted in this document's git history).

### Preserved security notes

No secrets. No network. `HKCU` registry write is user-authorized opt-in only. All Polymath invariants pass. See git history for the full invariant table from the original Pass I draft.

---

## Sign-off Readiness

| Gate | Status |
|------|--------|
| Code review | Done (this document) |
| Test suite review | Done — 5 gaps identified |
| Security alignment | Done — 2 gaps flagged |
| Calamum config | DONE — baseline established Pass D |
| CI pipeline | DONE — GitHub Actions wired Pass A |
| Force push authorization | Pending joediggidyyy |
| Pass I plan | LOCKED — widget-based path; implementation authorized after Pass H gate |
| Tray process (§10) | DEFERRED — preserved for future pass after Pass I ships |
| Pass J plan | PLACEHOLDER — scope definition after Pass H gate |

**Post-Pass-H next action:** Execute Pass I (widget background posture + `NotificationWidget`), then initiate Pass J scope definition session with joediggidyyy.
