# BlindTag — Polymath Maturity Review & Update Plan

**Date:** 2026-05-30  
**Reviewer:** ORACL  
**Status:** Pre-push baseline — no code changes applied this pass  
**Target:** Polymath-level maturity before public release

---

## Handoff Gate — Standing Rule (non-negotiable)

> **A pass is not complete until ORACL has personally launched the application from the normal user path, observed it running, and confirmed the expected changes are visible.**

- **User launch path** = `blindtag-widget.exe` (the installed console-script / gui-script shim in `.venv-core\Scripts\`)
- **Requirement:** widget launch must be terminal-free. This is not just a handoff-test preference; it is a product requirement.
- After any `pyproject.toml` entry-point change, `pip install -e .` must be run before the live test to regenerate shims
- The gate clears only when: shim type is verified → widget launches with no terminal → new UI/behavior is visually confirmed
- Calamum `decision: go` is a necessary condition but not sufficient — it covers automated tests only, not the live launch path
- This rule applies to every pass that modifies `widget.py`, entry points, or install configuration

### 2026-05-31 follow-up evidence addendum

**Evidence reviewed this pass:**
- Operator screenshot showing launch from `blindtag widget` inside an activated terminal
- Operator screenshot showing top toggle buttons still visually wider than the requested mock target
- Operator screenshot showing no corner notification and a close-path traceback at `blindtag/widget.py:1468`
- Current installed entry points from `.venv-core\Scripts\`: `blindtag.exe` and `blindtag-widget.exe` both present
- Current package config: `pyproject.toml` defines `blindtag` under `[project.scripts]` and `blindtag-widget` under `[project.gui-scripts]`

**Verified interpretation:**
- `blindtag widget` is the root CLI launchpoint routed through `blindtag.exe`; it should remain available unless explicitly retired by operator mandate.
- `blindtag-widget.exe` remains the GUI-script handoff surface and the normal compliant terminal-free widget launch path.
- The requirement itself is broader than the handoff lane: widget launch is expected to be terminal-free. The CLI route therefore needs truthful adaptation to the same handoff behavior, not implied removal.

**Current follow-up verdict:**
- Terminal-open behavior in the screenshot was explained by the launch surface used, not by a failed GUI-script registration.
- That did **not** make the terminal-attached widget route acceptable; the required correction is to adapt the CLI launchpoint so it hands off cleanly instead of staying attached.
- The 92px toggle-width adjustment landed in code but did **not** satisfy the visual target; treat that edit as insufficient, not absent.
- Hidden-notification delivery remains unproven in live use. The last fix improved screen targeting and non-activating popup behavior, but the operator still did not observe the notification. This remains an open implementation gap.
- The close-path traceback at `blindtag/widget.py:1468` indicates an additional runtime issue in the window close lane that was not covered by the last automated tests.

---

## TL;DR

The codec engine and API are well-written and the test suite is thorough for the happy-path and adversarial-input lanes. The primary gaps are: missing Calamum test configuration, no CI pipeline, an unresolved test ambiguity in the TAG_CANCEL-only case, absent widget tests, a deprecated build backend declaration, missing project metadata in `pyproject.toml`, no `.env.example`, no request tracing on the API, and no GitHub Actions workflow. All are plannable; none require architectural changes.

---

## Section 1 — Code Review Findings

### 1.1 `blindtag/core.py` — PASS with minor notes

| Finding                                                                             | Severity | Notes                                                 |
| ----------------------------------------------------------------------------------- | -------- | ----------------------------------------------------- |
| Logic is sound; encode/decode/strip are unambiguous                                 | —        | Good                                                  |
| `PLANE14_MIN` / `PLANE14_MAX` constants declared but not used in public API surface | Low      | Useful for external callers; keep but document intent |
| `Optional` imported from `typing` — should be `str \| None` (Python 3.11+)          | Low      | Cleanup item for code-change pass                     |
| No `__all__` export list                                                            | Low      | Add to lock the public surface                        |

### 1.2 `blindtag/api.py` — PASS with security notes

| Finding                                                                  | Severity | Notes                                                                                                        |
| ------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------ |
| Pydantic validation + InvalidPayloadError handler in place               | —        | Good                                                                                                         |
| CORS restricted to localhost origins                                     | —        | Good                                                                                                         |
| No request ID / trace header on responses                                | Medium   | Polymath style: every API response should carry a `X-Request-Id` or equivalent for retained-evidence tracing |
| No rate limiting                                                         | Low      | Localhost-only mitigates; note as accepted risk in SECURITY.md                                               |
| No `X-Content-Type-Options: nosniff` or security headers                 | Low      | Standard hardening for any HTTP surface                                                                      |
| `run_server()` entry point in `api.py` — not visible in the portion read | Verify   | Confirm this function exists; `pyproject.toml` script references it                                          |
| No version header in health response beyond JSON body                    | Low      | Consider `X-BlindTag-Version` header for client negotiation                                                  |

### 1.3 `blindtag/widget.py` — NOT REVIEWED (GUI, excluded from coverage)

| Finding                                                                         | Severity | Notes                                                                                              |
| ------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| Zero test coverage                                                              | Medium   | At minimum: smoke tests for `encode`/`decode` plumbing through widget logic; full GUI not required |
| Clipboard watcher daemon thread — no documented stop condition beyond app close | Low      | Document the shutdown contract explicitly                                                          |

### 1.4 `blindtag/exceptions.py` — PASS

Clean hierarchy. `DecodingError` is defined but verify it is raised in the decode path for out-of-range bytes (test coverage gap identified in Section 2).

---

## Section 2 — Test Suite Review

### 2.1 `tests/test_core.py` — STRONG, two gaps

| Finding                                                                                                                     | Severity | Action                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TestDecodeNoPayload.test_only_tag_cancel_yields_none_or_empty` uses `assert result is None or result == ""` — ambiguous OR | Medium   | **Resolve the contract:** TAG_CANCEL with no preceding payload chars should be `None` (no payload found). Update assertion to `assert result is None`.                       |
| `DecodingError` is never exercised in test suite                                                                            | Medium   | Add `TestCrashImmunity` case: feed a synthetic Plane 14 sequence outside ASCII range (e.g. U+E007F+1 if reachable) to verify `DecodingError` is raised rather than swallowed |
| No test for `encode()` called with empty hidden_message="" — currently raises `ValueError`                                  | Low      | Verify intent: should this raise `InvalidPayloadError` instead for consistency?                                                                                              |

### 2.2 `tests/test_api.py` — GOOD, three gaps

| Finding                                                                                                   | Severity | Action                                                                                             |
| --------------------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| No test for CORS headers (OPTIONS preflight, or `Origin` header response)                                 | Low      | Add `TestCORSPolicy` class                                                                         |
| No test exercising the `InvalidPayloadError` handler path directly (the Pydantic validator catches first) | Low      | Send a request where Pydantic passes but core raises — construct a raw request bypassing validator |
| No test for `GET /openapi.json` accessibility (important for tooling integrations)                        | Low      | Add to `TestHealthEndpoint`                                                                        |

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

| Artifact              | Path                          | Notes                                       |
| --------------------- | ----------------------------- | ------------------------------------------- |
| Calamum catalog JSON  | `calamum_catalog.json` (root) | Defines the test suite lanes and run config |
| Test run evidence dir | `report_tmp/` (gitignored)    | Per project precedent                       |

### 3.3 Minimum catalog definition (plan only)

The catalog should register at minimum two lanes:
1. **`core`** — `pytest tests/test_core.py` — codec engine tests
2. **`api`** — `pytest tests/test_api.py` — API integration tests

With a combined rollup lane `all` running both. Evidence from `calamum test run all` becomes the baseline pass receipt for the pre-push gate.

---

## Section 4 — Polymath Security Alignment

Reference: `docs/guides/POLYMATH_SECURITY_MEASURES_AND_EXPECTATIONS.md`

| Invariant                                        | Status   | Gap / Action                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. No secrets in source control                  | PASS     | `.gitignore` covers `.env*`                                                                                                                                                                                                                                                                                         |
| 2. Environment is the keyring                    | N/A      | No secrets required at runtime currently; document if API auth is added                                                                                                                                                                                                                                             |
| 3. Names-only documentation                      | PASS     | No values exposed anywhere                                                                                                                                                                                                                                                                                          |
| 4. Agents do not read secret material            | PASS     | No vault or secret reads                                                                                                                                                                                                                                                                                            |
| 5. Fail closed on trust ambiguity                | DEFERRED | API has no auth layer. **Framing this as a permanent "localhost-only" design decision is premature** — a reporting layer is planned post-widget that will require revisiting API transport scope, auth, and exposure model. Do NOT lock localhost-only into SECURITY.md until the reporting layer scope is defined. |
| 6. Protected secret stores — integrity controls  | N/A      | No secret store                                                                                                                                                                                                                                                                                                     |
| 7. Sensitive state changes require authorization | N/A      | No state mutations; document for future API auth additions                                                                                                                                                                                                                                                          |
| 8. Retained evidence must be verifiable          | GAP      | API responses carry no checksums or request IDs; plan `X-Request-Id` header                                                                                                                                                                                                                                         |
| 9. Path containment enforced                     | PASS     | No file I/O in codec or API                                                                                                                                                                                                                                                                                         |
| 10. Security messaging useful and secret-safe    | PASS     | Error messages describe constraint without leaking values                                                                                                                                                                                                                                                           |

**Additional gap:** No `.env.example` file. Polymath standard requires one even when the current version has no secrets, to establish the pattern for future additions.

**Scope note:** The reporting layer planned in Section 9 will introduce new invariant touchpoints (auth, retained evidence, signed responses). Security invariants 2, 5, 7, and 8 must be re-evaluated against that layer's design before any final SECURITY.md settlement.

---

## Section 5 — Polymath Style & Formatting Alignment

Reference: `docs/guides/POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md`

| Surface                                                    | Status  | Gap / Action                                                                 |
| ---------------------------------------------------------- | ------- | ---------------------------------------------------------------------------- |
| API error responses — structured JSON with reason + detail | PASS    | `error_type` + `detail` fields present                                       |
| API success responses — complete schema                    | PASS    | All four questions answerable from response body                             |
| CLI launcher `run_api.py` — help text                      | Verify  | Confirm `--help` output meets style contract                                 |
| CLI launcher `run_widget.py` — help text                   | Verify  | Same                                                                         |
| Health endpoint — version in response                      | PASS    | `version` field present                                                      |
| API response: "what happened / why / next action" contract | PARTIAL | Decode miss response has `detail` string but no `next_action` field guidance |

---

## Section 6 — Package Metadata & Build

### 6.1 `pyproject.toml` gaps

| Gap                                              | Severity | Fix                                                                      |
| ------------------------------------------------ | -------- | ------------------------------------------------------------------------ |
| `setuptools.backends.legacy:build` is deprecated | Medium   | Change to `setuptools.build_meta`                                        |
| No `[project.authors]` field                     | Medium   | Add `authors = [{name = "Polymath", email = "dev@polymath-global.com"}]` |
| No `[project.urls]` section                      | Medium   | Add Homepage, Source, Issues URLs                                        |
| No trove classifiers                             | Low      | Add Python version, OS, topic classifiers                                |
| No `ruff` or `mypy` config section               | Low      | Add for lint/type-check consistency                                      |

### 6.2 Missing files

| File                       | Action                                                       |
| -------------------------- | ------------------------------------------------------------ |
| `.env.example`             | Create — placeholder only, no values                         |
| `docs/` directory          | Create — currently only `REVIEW_AND_MATURITY_PLAN.md` exists |
| `.github/workflows/ci.yml` | Create — run `pytest tests/` on push to main                 |
| `docs/CALAMUM_BASELINE.md` | Create after first `calamum test` run passes                 |

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

### Pass K — Polymath aesthetic alignment & UI hygiene (execute BEFORE Pass I)

**See full Pass K section below for detailed spec.**

Summary: palette migration to cool-navy ecosystem, Clip Watch checkbox → glow button, taskbar icon fix, border/line token introduction, button style refresh. All changes are widget-only — no API, no tests, no CLI.

### Pass I — Background monitoring posture & notification widget (widget enhancement)

**Dependency:** Pass K must be executed and gated first so Pass I uses the updated color tokens throughout.

**Scope:** Extend `BlindTagWindow` with a "background" posture — explicit hide, watcher stays alive, focus-stealing notification replaced by a custom ephemeral corner `NotificationWidget`. No new entry point, no `QSystemTrayIcon`, no new dependencies. All behavior lives inside the existing `blindtag-widget` entry point.

**Architecture driver:** `hide()` does not trigger `closeEvent`, so the `dataChanged` signal stays connected and the watcher runs. Two pieces were missing: (a) a non-intrusive notification surface for when the window is hidden, and (b) an explicit "Hide" transition distinct from minimize and close.

---

#### I.1 — Posture model

| Posture        | Window state           | Watcher        | Notification                                            |
| -------------- | ---------------------- | -------------- | ------------------------------------------------------- |
| `"foreground"` | Visible, always-on-top | Active or idle | Inline blue `QLabel` banner (current `_notify_payload`) |
| `"background"` | Hidden, in taskbar     | Active         | `NotificationWidget.show_for(preview)`                  |

**Transitions:**
- **→ background:** Clip Watch button active (checked) + user clicks "Hide" button in title bar. `self.hide()`, `_posture = "background"`.
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

Shown only while Clip Watch is active. Visibility is toggled inside `_toggle_watcher` (called via `_watcher_btn.toggled` after Pass K). The button is part of the existing frameless title bar widget. Label: `"Hide"`. Tooltip: `"Run in background — click notification to return"`.

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

| Invariant                                                 | Assessment                                                                                                                        |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 1. No secrets in source control                           | PASS — no new credentials, keys, or secrets introduced                                                                            |
| 2. Environment is the keyring                             | N/A — no secrets at runtime in this pass                                                                                          |
| 3. Names-only documentation                               | PASS — plan documents class/method names only                                                                                     |
| 4. Agents do not read secret material                     | PASS                                                                                                                              |
| 5. Fail closed on trust ambiguity                         | PASS — no trust surface introduced; notification shows 48-char excerpt only; `decode()` called on clipboard text as before        |
| 6. Protected stores require integrity controls            | N/A                                                                                                                               |
| 7. Sensitive state changes require explicit authorization | PASS — posture change is explicit user button click; no silent background transitions                                             |
| 8. Retained evidence must be verifiable                   | PASS — calamum gate produces verifiable `report.json` + stdout/stderr; no new evidence artifacts escape outside `calamum` control |
| 9. Path containment enforced                              | PASS — `notification.py` reads no files; writes no files; no new file I/O                                                         |
| 10. Security messaging useful and secret-safe             | PASS — `NotificationWidget` shows `preview[:48]` only, same truncation rule as existing `_notify_payload`                         |

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

| #        | Artifact                                         | Action                                                                                                             | Dependency                                                                                                                                                   |
| -------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1        | `blindtag/notification.py`                       | CREATE                                                                                                             | None                                                                                                                                                         |
| 2        | `blindtag/widget.py`                             | MODIFY                                                                                                             | Requires (1) — import `NotificationWidget`; add `_posture`, `_bg_notif`; branch in `_notify_payload`; "Hide" button; `showEvent`; self-detection guard       |
| 3        | `tests/test_widget.py`                           | MODIFY                                                                                                             | Requires (1)(2) — add `TestNotificationWidget` + `TestBackgroundPosture`                                                                                     |
| 4        | `catalog/test_definitions.json`                  | MODIFY                                                                                                             | Requires (3) — update `blindtag-widget` notes field                                                                                                          |
| 5        | `CHANGELOG.md`                                   | MODIFY                                                                                                             | Requires gate pass                                                                                                                                           |
| **Gate** | `calamum test run blindtag-all --project <path>` | RUN                                                                                                                | After (1–4); `decision: go` required before (5) and commit                                                                                                   |
| 6        | **Package reinstall**                            | `pip install -e .` in `.venv-core`                                                                                 | Required after Pass L `pyproject.toml` change moved `blindtag-widget` to `[project.gui-scripts]`; regenerates `blindtag-widget.exe` shim as `pythonw`-backed |
| 7        | **Live visual test**                             | Launch `blindtag-widget`, observe: no terminal, Hide button present, background posture + corner notification fire | After (6); must be run and observed before lane closeout                                                                                                     |

**Status (revised 2026-05-31):** Steps 1–5 + Gate complete. The installed GUI shim lane (`blindtag-widget.exe`) remains the normal no-terminal handoff surface. Follow-up operator evidence showed that the then-current `blindtag widget` implementation still kept a terminal open, so the correction lane is to restore that CLI launchpoint and adapt it to the same handoff behavior rather than retire it. Hidden-notification live behavior remains unresolved, and the close-path traceback at `widget.py:1468` requires a dedicated remediation pass before claiming the hidden-notification lane is fully stable.

**Live test command (exact, copy-paste-ready):**
```powershell
Set-Location "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"
& "c:\Users\joedi\Documents\CodeSentinel-1\.venv-core\Scripts\pip.exe" install -e .
& "c:\Users\joedi\Documents\CodeSentinel-1\.venv-core\Scripts\blindtag-widget.exe"
```

Execute in order. Reinstall must precede widget launch to flush the stale shim.

**Supported compatibility launcher (must hand off cleanly):**
```powershell
blindtag widget
```

This route remains part of the public CLI surface. The requirement is not retirement by implication; it is truthful terminal-free handoff behavior.

---

### Pass K — Polymath aesthetic alignment & UI hygiene

**Status:** Plan locked. Execute before Pass I. No new features; no new files.

**Scope:** Migrate `widget.py` visual tokens to the cool-navy Polymath ecosystem palette, replace the Clip Watch checkbox with a glow-button, fix the taskbar icon, introduce a named border/line color token, and freshen button styles to match the Polyventure control-deck language. All changes are confined to `widget.py` and the widget's color-constant block.

**Reference sources (evidence gathered):**
- `projects/calamum-vulcan/calamum_vulcan/app/style.py` — `COLOR_TOKENS` dict (canonical ecosystem palette)
- `docs/external/polymath-global-website/index.html` — CSS `:root` tokens (`--bg-color`, `--secondary-accent`, `--accent-color`)
- Polyventure Control Deck screenshot — selected-button glow pattern, section header treatment, status-pill shapes
- `blindtag/widget.py` — current palette constants and UI construction methods (lines 1–130)

---

#### K.1 — Palette migration

Full token mapping. Every constant in `widget.py` must be updated; no old value retained.

| Constant      | Old value | New value | Rationale                                                    |
| ------------- | --------- | --------- | ------------------------------------------------------------ |
| `C_BG`        | `#121212` | `#0a0d12` | Warm charcoal → cool deep navy (matches Vulcan `background`) |
| `C_SECONDARY` | `#1E1E1E` | `#10161f` | → Vulcan `surface` — navy-tinted                             |
| `C_SURFACE`   | `#252525` | `#16212d` | → Vulcan `surface_card` — navy card                          |
| `C_ACCENT`    | `#4A90D9` | `#3dd5f3` | Office blue → brand cyan (Vulcan `brand`)                    |
| `C_ACCENT_H`  | `#5BA3F0` | `#62daf7` | Hover lightened brand cyan                                   |
| `C_TEXT`      | `#E8E8E8` | `#edf2f7` | Warm white → cool near-white (Vulcan `text`)                 |
| `C_MUTED`     | `#888888` | `#9aa9bc` | Warm gray → cool blue-gray (Vulcan `muted`)                  |
| `C_SUCCESS`   | `#4CAF6E` | `#4fc08d` | Match Vulcan `success`                                       |
| `C_WARNING`   | `#E8A838` | `#f3a948` | Match Vulcan `warning`                                       |
| `C_ERROR`     | `#E85555` | `#e25757` | Match Vulcan `danger`                                        |

**New constant — add after `C_ACCENT_H`:**
```python
C_LINE      = "#263546"   # Navy-tinted border/divider — replaces all hardcoded #303030
```

**Hardcoded `#303030` audit:** Every occurrence of `"#303030"` in `widget.py` must be replaced with `C_LINE`. This covers: `_textbox_style()`, `_EmojiFlyout` frame border, `_GuidancePanel` border-right, `_LibraryEditorPanel` dividers, emoji grid button hover.

---

#### K.2 — Clip Watch: checkbox → glow button

**Rationale:** Checkboxes are not in the Polymath design language. The Polyventure control-deck uses bordered buttons with a teal/cyan glow for selected states (e.g. "OPERATOR CONTROLS" with active border vs "EVIDENCE" with dim border).

**Implementation spec:**

Remove `QCheckBox` entirely. Replace with `QPushButton(setCheckable=True)` named `_watcher_btn`.

Add two style helpers to the stylesheet-helpers block:

```python
def _clip_watch_active_style() -> str:
    """Clip Watch button — active/checked state: cyan border glow."""
    return (
        f"QPushButton {{"
        f"background-color: {C_SECONDARY}; color: {C_ACCENT}; "
        f"border: 2px solid {C_ACCENT}; border-radius: 5px; "
        f"font-size: 9pt; font-weight: bold; padding: 4px 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {C_SURFACE}; }}"
    )

def _clip_watch_inactive_style() -> str:
    """Clip Watch button — idle state: subtle border, muted text."""
    return (
        f"QPushButton {{"
        f"background-color: transparent; color: {C_MUTED}; "
        f"border: 1px solid {C_LINE}; border-radius: 5px; "
        f"font-size: 9pt; padding: 5px 12px;"
        f"}}"
        f"QPushButton:hover {{ border-color: {C_ACCENT}; color: {C_TEXT}; }}"
    )
```

In `_build_toggle_strip()`:
- Remove `self._watcher_chk = QCheckBox(...)` and `stateChanged` connection
- Add:
  ```python
  self._watcher_btn = QPushButton(" Clip Watch")
  self._watcher_btn.setCheckable(True)
  self._watcher_btn.setStyleSheet(_clip_watch_inactive_style())
  self._watcher_btn.toggled.connect(self._toggle_watcher)
  layout.addWidget(self._watcher_btn)
  ```

In `_toggle_watcher(self, checked: bool)`:
```python
def _toggle_watcher(self, checked: bool) -> None:
    if checked:
        self._watcher_btn.setStyleSheet(_clip_watch_active_style())
        self._start_watcher()
    else:
        self._watcher_btn.setStyleSheet(_clip_watch_inactive_style())
        self._stop_watcher()
```

Also update `_toggle_watcher_hotkey` to use `self._watcher_btn.setChecked(not self._watcher_btn.isChecked())`.

**Pass I impact:** Pass I's `_start_watcher()` / `_stop_watcher()` checks watcher state via `_watcher_btn.isChecked()` instead of the old `_watcher_chk.isChecked()`. Update Pass I §I.3 accordingly — the "Hide" button visibility toggle is driven by `_watcher_btn.toggled` signal, not a checkbox signal.

**QCheckBox import:** After this change, `QCheckBox` is no longer used in `widget.py`. Remove from the `from PySide6.QtWidgets import (...)` block.

---

#### K.3 — Taskbar icon fix

**Gap:** `run_widget()` calls `QApplication.instance() or QApplication(sys.argv)` but never sets an app-level icon. For frameless windows (`Qt.FramelessWindowHint`), the per-window `setWindowIcon()` does not populate the Windows taskbar entry — the app-level icon is used instead.

**Fix — in `run_widget()`, after `app =` and before `app.setStyleSheet(...)`:**
```python
_app_icon_path = Path(__file__).resolve().parent.parent / "assets" / "images" / "blindtag_thumbnail_basic.png"
if _app_icon_path.exists():
    app.setWindowIcon(QIcon(str(_app_icon_path)))
```

**Note:** `blindtag_thumbnail_basic.png` is confirmed present at `assets/images/`. `blindtag_logo.png` is also present and is used in the title bar; the thumbnail variant is the correct choice for the taskbar (square crop, no wordmark).

---

#### K.4 — Button style refresh

All three existing button helpers (`_btn_primary_style`, `_btn_secondary_style`, `_btn_ghost_style`) and the two toggle helpers (`_toggle_active_style`, `_toggle_inactive_style`) will pick up the new palette automatically via the updated constants. No structural change needed.

One enhancement: `_btn_primary_style` should add a matching 1px brand border for a subtle polymath-era definition:
```python
f"border: 1px solid {C_ACCENT}; "   # add after "border: none;" removal
```
This matches the Polyventure pattern where primary actions carry a visible brand border (not just a filled background), giving the filled button a crisper frame without adding glow.

---

#### K.5 — Section header label update

`_section_label` outputs uppercase section labels. Currently style is `C_MUTED` color. After palette update, `C_MUTED = "#9aa9bc"` is a cool blue-gray — this is slightly lighter and cooler than the old warm gray and will naturally look more consistent with the Polyventure header treatment. No code change needed; the constant update achieves it.

---

#### K.6 — Swept-in items from previous pass plans

The following items were specified in earlier pass plans but not yet executed. They are formally swept into Pass K as the canonical implementation home:

| Item                               | Source                                  | Action                        |
| ---------------------------------- | --------------------------------------- | ----------------------------- |
| Taskbar icon (app-level)           | Section 10 "Preserved design decisions" | §K.3 above                    |
| `C_LINE` border token              | Section 1.3 (`#303030` hardcoded)       | §K.1 — new constant + sweep   |
| Clip Watch as non-checkbox control | Section 1.3 widget finding              | §K.2 above                    |
| `QCheckBox` import removal         | Code hygiene                            | Remove from imports after K.2 |
| `_APP_STYLESHEET` palette accuracy | All passes                              | Resolved by §K.1 token update |

---

#### K.7 — Calamum test contract

No new test classes needed. The aesthetic changes are stylistic only — no logic changes. Existing `blindtag-widget` test suite must still pass at `decision: go` through `blindtag-all`.

Gate command (same as Pass H/I):
```powershell
$cal = Join-Path "c:\Users\joedi\Documents\CodeSentinel-1\.venv-core\Scripts" "calamum.exe"
$proj = "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"
& $cal "test" "run" "blindtag-all" "--project" $proj | Tee-Object -FilePath "report_tmp\pass_k_gate.txt"
```

---

#### K.8 — Deliverables and sequence

| #        | Artifact                        | Action | Notes                                                                                                                                                                                                                                                                          |
| -------- | ------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1        | `blindtag/widget.py`            | MODIFY | Update color constants (§K.1); add `C_LINE`; replace `#303030` occurrences; add glow-button style helpers (§K.2); replace `QCheckBox` with `QPushButton` (§K.2); fix `run_widget()` taskbar icon (§K.3); freshen `_btn_primary_style` border (§K.4); remove `QCheckBox` import |
| 2        | `CHANGELOG.md`                  | MODIFY | Pass K entry after gate pass                                                                                                                                                                                                                                                   |
| **Gate** | `calamum test run blindtag-all` | RUN    | `decision: go` required before commit and before Pass I begins                                                                                                                                                                                                                 |

---

#### K.9 — Visual reference summary

The target aesthetic (verified across sources):

| Property         | Target value                                     | Source                                |
| ---------------- | ------------------------------------------------ | ------------------------------------- |
| Background       | Deep cool navy, not warm charcoal                | Vulcan `#0a0d12`, website `#0a0a0a`   |
| Brand/accent     | Cyan `#3dd5f3`                                   | Vulcan `brand` token                  |
| Muted text       | Cool blue-gray `#9aa9bc`                         | Vulcan `muted`                        |
| Borders          | Navy-tinted `#263546`                            | Vulcan `line`                         |
| Selected button  | Brand-color border (2px) + transparent/tinted bg | Polyventure OPERATOR CONTROLS pattern |
| Idle button      | 1px muted border, no fill, dim text              | Polyventure EVIDENCE pattern          |
| Hover transition | Border lightens to brand; text brightens         | Polyventure hover behavior            |
| Primary CTA      | Filled brand color + 1px border frame            | Polyventure primary action style      |

---

### Pass M — Emoji library multi-column editor & action button cleanup

**Status:** LOCKED — bounded implementation plan ready.  
**Dependency:** Pass I complete and gated. No dependency on Pass J.  
**Scope:** Two widget-only changes — (1) library editor rows gain multi-column display with a structured add row at the bottom, (2) extra action buttons are removed so each panel has one action button. No API changes. No new files.

---

#### M.1 — Redundant action button removal

**Locked design:** One primary CTA per panel. Both secondary buttons are removed. No behavior changes to the remaining buttons.

**Current → target:**
- Encode panel: `[ Encode ]` + `[ ⬡ Obfuscate & Copy ]` → **`[ Encode & Copy ]` only**
- Decode panel: `[ Decode ]` + `[ ⬇ Paste & Decode ]` → **`[ Decode ]` only**

**Rationale (operator-confirmed):** Clip Watch mode handles automatic decode on clipboard change. When Clip Watch is off, the user pastes into the raw input field and clicks `Decode`. The extra `Paste & Decode` button is not wanted. Same for the encode panel — the single action should be the complete path, with clearer text. Clutter is antithetical to the design culture.

**Post-change layout per panel:**
```
Encode:  [ Encode & Copy ]   [ Clear All ]
Decode:  [ Decode ]   [ Clear All ]
```

`Ctrl+Return` already routes to the correct primary CTA per active panel. No hotkey changes needed.

**Test impact:** Remove any test asserting the presence of the removed `[ Encode ]` and `[ ⬇ Paste & Decode ]` buttons. Add/retain coverage confirming the encode panel exposes a single `Encode & Copy` action and the decode panel exposes a single `Decode` action button.

---

#### M.2 — Emoji library multi-column editor

**Locked design contract (from mockup):** Existing rows are display rows. The only editable controls on this page live in the single add-entry row at the bottom.

| Column       | Content                                       | Example         |
| ------------ | --------------------------------------------- | --------------- |
| Glyph / Code | Glyph plus its derived Unicode representation | `👎` / `U+1F44E` |
| Alias        | Active alias string                           | `:thumbsdown:`  |
| Label        | Human-readable name                           | `thumbs down`   |

The glyph icon remains at the far left. The `×` remove button remains at the far right.

**Current row structure (`_make_row`):**  
`[glyph 14pt QLabel] [label QLabel] [× QPushButton]`

**Target row structure:**  
`[glyph 14pt QLabel + derived code label] [alias QLabel] [label QLabel] [× QPushButton]`

**Schema:** No change required. `entry["emoji"]` remains the stored glyph, `entry["alias"]` remains the creation-time alias, and `entry["label"]` remains the human-readable label. The code value is derived from `entry["emoji"]` for display.

**Add form:** The add row has exactly three fields: `glyph/code`, `alias`, `label`.

- `glyph/code` accepts either a literal glyph or a Unicode form such as `U+1F44E`
- `alias` is entered directly at creation time and becomes the local key for the record
- `label` is the human-readable description

If the user enters a glyph, the Unicode code is derived for display in the record row. If the user enters a Unicode code, the glyph is derived for storage/display in the record row. The add row must not accept `:alias:` as a substitute for glyph/code because a new record cannot be created from an alias that does not yet exist.

---

#### M.3 — Hidden-mode relaunch behavior (settled)

| #   | Gap                                                     | Options                                                                                         | Impact                                                                                                                                                                                                                                   |
| --- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Hidden-mode relaunch path when the widget is hidden** | Persistent notification window acts as the click-to-relaunch anchor until dismissed or replaced | This is settled. `NotificationWidget` becomes the explicit relaunch surface in hidden posture. Replacement rule: newest hidden notification replaces the previous one. Taskbar presence remains incidental, not the primary UX contract. |

---

#### M.4 — Calamum test contract

Existing `blindtag-widget` test suite must pass at `decision: go`. New test coverage needed in `tests/test_widget.py`:

```
TestLibraryEditorColumns
    test_row_shows_glyph_code_alias_label_columns
    test_codepoint_display_derived_from_emoji_char
    test_add_row_accepts_glyph_input_and_derives_code
    test_add_row_accepts_unicode_input_and_derives_glyph
    test_add_row_rejects_alias_as_glyph_code_source

TestActionButtonCleanup
    test_encode_panel_has_only_encode_and_copy_action
    test_decode_panel_has_only_decode_action

TestHiddenNotificationAnchor
    test_hidden_notification_persists_until_dismissed_or_replaced
    test_hidden_notification_body_restores_main_window
    test_hidden_notification_close_only_dismisses_anchor
    test_new_hidden_notification_replaces_previous_anchor
```

**Calamum evidence contract:** Pass M is not considered validated on `pytest` output alone. The gate must produce Calamum artifact families consistent with runner contract precedent:

- `report_json`
- `report_md`
- `manifest_json`
- `checksums_json`
- checksum sidecars where emitted

Where signing is configured for the environment, retained JSON artifacts should also remain verifiable under the Calamum signing surface (`sign_json_artifact` / `verify_json_artifact`). Pass M does not introduce new signed-call surfaces, but it must not weaken the existing evidence-verification lane.

---

#### M.5 — Polymath + Calamum alignment guardrails

**Polymath user-facing alignment:**
- Single primary action per panel satisfies the calm, low-noise, no-surprise surface rule from `docs/guides/POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md`.
- `Encode & Copy` is explicit about what ran and what happened.
- `Decode` remains explicit and truthful; no implied clipboard mutation is baked into the label.
- Hidden-mode relaunch via persistent notification answers the operator-facing question: *what should happen next?* — click the notification to reopen.

**Polymath security alignment:**
- No new secrets, credentials, or trust material.
- No new network surface.
- No new publishable artifact families.
- Retained evidence remains verifiable through existing Calamum manifest/checksum/signature expectations.
- Hidden notification preview remains truncated/secret-safe and must not expand beyond the current guarded excerpt behavior.

**Project-precedent alignment:**
- Preserve the current single-window widget architecture; no tray split in this pass.
- Preserve the handoff gate: live launch from `blindtag-widget.exe` remains mandatory before closeout.
- Preserve the Calamum-first validation lane: `decision: go` plus retained artifacts, then live visual confirmation.

---

#### M.6 — Deliverables and sequence

| #                   | Artifact                                         | Action | Notes                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1                   | `blindtag/widget.py`                             | MODIFY | Rename the remaining encode CTA to `Encode & Copy`; remove secondary `Encode`; remove `Paste & Decode` so `Decode` is the single action; keep hidden notifications persistent while hidden until dismissed or replaced; rewrite `_make_row()` in `_LibraryEditorPanel` to 3-column display layout; update add row to `glyph/code`, `alias`, `label`; derive glyph/code pair at creation time |
| 2                   | `tests/test_widget.py`                           | MODIFY | Add `TestLibraryEditorColumns`, `TestActionButtonCleanup`, and `TestHiddenNotificationAnchor`                                                                                                                                                                                                                                                                                                |
| 3                   | `catalog/test_definitions.json`                  | MODIFY | Update `blindtag-widget` notes field                                                                                                                                                                                                                                                                                                                                                         |
| 4                   | `CHANGELOG.md`                                   | MODIFY | After gate pass                                                                                                                                                                                                                                                                                                                                                                              |
| **Gate**            | `calamum test run blindtag-all --project <path>` | RUN    | `decision: go` required before commit; retain `report_json`, `report_md`, `manifest_json`, `checksums_json` evidence set                                                                                                                                                                                                                                                                     |
| **Evidence verify** | Verify Calamum artifacts                         | RUN    | Confirm manifest/checksum set exists; where signing is configured, verify signed artifact path remains valid                                                                                                                                                                                                                                                                                 |
| **Live handoff**    | Launch installed widget                          | RUN    | `pip install -e .` → `blindtag-widget.exe` → visually confirm persistent hidden notification anchor, single CTA per panel, and display-only library rows                                                                                                                                                                                                                                     |

**Handoff gate applies.** After any `widget.py` change: `pip install -e .` → launch `blindtag-widget.exe` → confirm library editor rows show 3 columns and action rows show single primary CTA each.

#### M.7 — 2026-05-31 evidence review: keep / adapt / remove classification

| Edit from 2026-05-31 passes                                                                           | Evidence                                                                                 | Classification | Notes                                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pyproject.toml` GUI-script entry for `blindtag-widget`                                               | Present in current package config; `blindtag-widget.exe` exists in `.venv-core\Scripts\` | **KEEP**       | This remains the correct no-terminal handoff surface.                                                                                                   |
| Pass M single-action cleanup (`Encode & Copy`, `Decode`, display-only library rows, add-row contract) | Reflected in current widget code and user screenshot                                     | **KEEP**       | These changes match the locked design lane.                                                                                                             |
| Persistent hidden-notification anchor concept                                                         | Still the locked UX contract                                                             | **KEEP**       | The concept remains correct even though delivery is not yet reliable.                                                                                   |
| Notification hardening via `WA_ShowWithoutActivating`, `NoFocus`, `_target_screen()`                  | Landed in `notification.py`, but operator still observed no notification                 | **ADAPT**      | Keep as partial groundwork; do not treat as sufficient fix. Next pass must investigate why the popup never becomes visible in the real hidden workflow. |
| Toggle-width reduction to `setFixedWidth(92)` and reduced padding                                     | Landed in `widget.py`, but user still judged the tabs too wide                           | **ADAPT**      | The edit stuck in code; it simply missed the visual target.                                                                                             |
| Prior claim that the hidden-notification lane was complete/validated                                  | Contradicted by current operator evidence                                                | **REMOVE**     | Replace with narrower wording: automated tests passed, but live notification delivery remains unresolved.                                               |
| Any wording that normalizes terminal-attached widget launch as acceptable                             | Conflicts with operator requirement that widget launch be terminal-free                  | **REMOVE**     | Replace with stricter wording: terminal-attached widget routes are currently noncompliant and must be adapted or retired.                               |

---

### Pass N — Widget launch compliance, hidden-notification closure, and top-toggle visual parity

**Status:** IMPLEMENTED — code changes and Calamum gate complete (`20260531T085159Z-blindtag-all`, `decision: go`); live operator re-verification of notification visibility and final visual parity still required.  
**Dependency:** Pass M codebase is the baseline. This pass is corrective and must land before Pass J scope or any additional widget feature growth.  
**Scope:** Close the remaining operator-observed gaps in the widget lane without broadening architecture: (1) enforce terminal-free widget launch as the only compliant widget surface, (2) make hidden notification delivery live-visible and close-stable, and (3) bring the top Encode / Decode toggle geometry into actual visual parity with the approved mock. No tray split. No new network surface. No new publishable artifact family.

---

#### N.1 — Evidence snapshot (2026-05-31)

| Open item                                        | Evidence                                                                                                                                         | Verified state                                                                                                                                |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Terminal-free widget launch is non-negotiable    | Operator clarification on 2026-05-31; handoff gate at top of this document                                                                       | Requirement is locked: widget launch must be terminal-free.                                                                                   |
| Current widget CLI duplication creates ambiguity | `pyproject.toml` has `blindtag-widget` under `[project.gui-scripts]`; `blindtag/cli.py` exposes `blindtag widget`                     | Current correction direction is to keep the CLI launchpoint and adapt it to hand off to `blindtag-widget.exe` truthfully instead of removing it. |
| Top toggle buttons remain visually too wide      | Operator screenshot after the 92px width change; current `widget.py` shows `setFixedWidth(92)` for both toggles                                  | The last geometry tweak landed in code but did not reach the approved design target.                                                          |
| Hidden notification still not observed live      | Operator screenshot and follow-up report; current `notification.py` contains `_target_screen()`, `WA_ShowWithoutActivating`, and persistent mode | The concept and partial hardening exist, but live visibility remains unresolved.                                                              |
| Close lane has an unclosed runtime defect        | Operator screenshot includes traceback pointing at `blindtag/widget.py:1468` (`closeEvent`)                                                      | The close path is not yet proven stable in the live hidden-notification workflow.                                                             |

---

#### N.2 — Locked decisions

1. **Terminal-free requirement stays product-level, not just handoff-level.** Any terminal-attached widget route is noncompliant until adapted or removed.
2. **One canonical widget surface.** The compliant steady-state widget surface remains `blindtag-widget.exe`. The duplicate CLI-routed widget path must be treated as a remediation target, not as an accepted alternate UX.
3. **No tray or OS-native notification expansion in this pass.** The custom `NotificationWidget` remains the chosen relaunch pattern; this pass is about making that pattern actually work and closing its teardown defects.
4. **No blind numeric UI nudges.** Toggle geometry changes in this pass must be driven by approved visual target matching, not by arbitrary width reduction alone.
5. **No evidence downgrade.** This pass must retain the current Calamum artifact family (`report_json`, `report_md`, `manifest_json`, `checksums_json`, checksum sidecars) and verify signatures/checksums where the environment is configured for signing.

**Execution outcome (2026-05-31):**
- Lane N-A was initially executed via surface consolidation, but that retirement decision exceeded the authorized scope and is being corrected by restoring the CLI launchpoint and adapting it instead.
- Lane N-B implemented via notification-window flag/show-path hardening plus safe recreation/teardown handling for the background notification object.
- Lane N-C implemented via a stricter compact-width toggle contract.
- Focused regressions passed (`85 passed` across `tests/test_cli.py` + `tests/test_widget.py`).
- Full Calamum gate passed: `20260531T085159Z-blindtag-all`, `decision: go`.
- Signing env check was names-only `missing` for `CALAMUM_POLICY_SIGNING_KEY`, so checksum/manifest verification was the active integrity lane for this run.
- Live reinstall + terminal-free widget launch executed; running `blindtag-widget.exe` process confirmed after reinstall.

**Rejected alternatives for this pass:**
- Adding tray infrastructure or platform-native notifications — out of scope and unnecessary before the current single-window route is corrected.
- Treating `blindtag widget` as acceptable terminal-attached product behavior — rejected by operator requirement.
- Implicitly retiring `blindtag widget` without explicit operator mandate — rejected by operator correction.
- Declaring the hidden-notification lane complete based only on focused pytest — rejected by live evidence.

---

#### N.3 — Bounded implementation scope

This pass is limited to three corrective lanes:

##### Lane N-A — Widget launch compliance
- Remove ambiguity between the compliant GUI surface and the terminal-attached widget route.
- The authorized current direction is to **adapt** the `blindtag widget` route so it no longer leaves the widget attached to a terminal and truthfully satisfies the same terminal-free contract.
- `blindtag-widget` remains the dedicated GUI surface; `blindtag widget` remains the public CLI compatibility launchpoint.

##### Lane N-B — Hidden-notification live closure
- Investigate why `NotificationWidget.show_for(..., persistent=True)` remains invisible in live hidden posture despite current tests.
- Investigate the interaction between `_apply_decoded_payload(...)`, `_notify_payload(...)`, `showEvent(...)`, and `closeEvent(...)` under hidden posture.
- Treat `closeEvent` stability as part of the same defect family because the live screenshot shows the close-path traceback adjacent to notification retest activity.
- Preserve the current secret-safe preview rule: notification preview remains truncated and names-only.

##### Lane N-C — Top-toggle parity
- Rework the Encode / Decode toggle sizing and/or padding so the result visually matches the approved mock rather than merely being narrower than before.
- Acceptance is visual, not just numeric: the active toggle should read as compact and centered within the strip without the oversized-pill look still visible in the 2026-05-31 screenshot.

---

#### N.4 — Calamum, security, and Polymath alignment contract

##### Calamum test contract

This pass must validate in three tiers:

1. **Targeted widget regression first** — focused `tests/test_widget.py` coverage for:
    - launch-surface behavior affected by the chosen Lane N-A decision,
    - hidden-notification visibility / persistence / close-path stability,
    - top-toggle geometry contract where testable without pixel overreach.
2. **Full project gate** — `calamum test run blindtag-all --project <path>` must return `decision: go`.
3. **Retained-artifact verification** — confirm emitted:
    - `report.json`
    - `report.md`
    - `manifest.json`
    - `checksums.json`
    - checksum sidecars where emitted

##### Calamum security / integrity contract

Grounding evidence:
- `projects/calamum/tests/test_runner.py` confirms retained-artifact families are written and bounded even under failure conditions.
- `projects/calamum/tests/test_signing.py` confirms `sign_json_artifact(...)` / `verify_json_artifact(...)` round-trip behavior where signing is configured.

Pass N must therefore follow this rule:

- If the validation environment is configured for signing, JSON evidence verification is **required** and must fail closed on missing or invalid signatures/checksums.
- If the environment is not configured for signing, the plan must still verify manifest/checksum integrity and record the reason in names-only form.
- No new signed-call surface is introduced by Pass N, so signed-call scope remains unchanged; however, this pass must not weaken any existing evidence-verification lane.

##### Polymath user-facing alignment

Per `docs/guides/POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md`, the corrected widget lane must remain:
- calm,
- explicit about what happened,
- low-noise,
- evidence-first,
- and clear about what the operator should do next.

Applied here:
- Terminal-free widget launch removes launch ambiguity.
- Hidden notification must truthfully answer “what happened?” and “what should happen next?” in one glance.
- The top-toggle correction is not cosmetic fluff; it is part of the calm, low-noise, visually truthful control surface.

##### Polymath security alignment

Per `docs/guides/POLYMATH_SECURITY_MEASURES_AND_EXPECTATIONS.md`, Pass N must preserve:
- names-only documentation,
- fail-closed validation wording,
- no secret-bearing previews,
- retained evidence verification,
- and path containment within the project + Calamum generated roots.

---

#### N.5 — Deliverables and execution sequence

| #          | Artifact                                         | Action | Notes                                                                                                                                                     |
| ---------- | ------------------------------------------------ | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1          | `blindtag/cli.py` and/or `pyproject.toml`        | MODIFY | Adapt the noncompliant `blindtag widget` route so it hands off to the same truthful widget launch contract without removing the public CLI launchpoint.    |
| 2          | `blindtag/widget.py`                             | MODIFY | Notification-path remediation, close-path stabilization, and top-toggle visual parity correction.                                                         |
| 3          | `blindtag/notification.py`                       | MODIFY | Only if required by the hidden-notification visibility/root-cause findings.                                                                               |
| 4          | `tests/test_widget.py`                           | MODIFY | Add focused regression coverage for the specific N-A / N-B / N-C acceptance boundaries.                                                                   |
| 5          | `catalog/test_definitions.json`                  | MODIFY | Update widget notes only if new focused coverage materially changes the lane contract.                                                                    |
| 6          | `CHANGELOG.md`                                   | MODIFY | Record Pass N only after gate pass.                                                                                                                       |
| **Gate A** | Focused widget pytest                            | RUN    | Clean targeted regressions required before full Calamum gate.                                                                                             |
| **Gate B** | `calamum test run blindtag-all --project <path>` | RUN    | `decision: go` required before commit.                                                                                                                    |
| **Gate C** | Evidence verification                            | RUN    | Verify manifest/checksum family and signature verification where configured.                                                                              |
| **Gate D** | Live handoff                                     | RUN    | `pip install -e .` → launch compliant terminal-free widget surface → visually confirm notification visibility, compact toggles, and clean close behavior. |

---

#### N.6 — Acceptance criteria

Pass N is complete only when all of the following are true:

1. Widget launch is terminal-free on the supported steady-state surface, with no contradictory alternate widget route left documented as acceptable.
2. The operator observes the hidden notification live in the actual hidden workflow, not just in tests.
3. Closing the widget after hidden-notification activity does not emit the `closeEvent` traceback seen on 2026-05-31.
4. The top Encode / Decode toggles visually match the approved compact target rather than the still-too-wide 92px result.
5. Focused widget tests pass.
6. Calamum full-project gate returns `decision: go`.
7. Retained evidence is present and verified via checksums, and via signatures where configured.

---

### Pass J — Logging and reporting infrastructure (scope definition after widget closure)

Blindtag's primary use model is **imported and used via API by other applications**. This pass delivers dense, structured, tiered logging and reporting. Known inputs:
- Structured log handler attached to `logging.getLogger("blindtag")` at API/CLI startup
- Per-operation log entries: timestamp, operation type, anchor/payload lengths, resolved token count, outcome
- Tiered severity: `debug` through `critical` all meaningful; widget is always `warning`-silent
- CLI `--log-level` raises verbosity; retained log queryable via API reporting endpoints
- Storage layer and auth/transport scope TBD in scoping session
- Security invariants 2, 5, 7, 8 re-evaluated against final transport/auth model
- New calamum catalog lanes for the reporting surface

**Pass J begins only after Pass N closes and its Calamum gate is confirmed.**

---

## Section 9 — Planned: Backend/API Reporting Layer

**Status:** Placeholder — scope not yet defined. Planning deferred until Pass N (widget closure) is complete and gated.

**Primary use model:** blindtag is designed to be **imported and used via API by other applications** — not as a standalone personal tool. The widget is a convenience surface; the API and importable core are the canonical consumption path. This changes the logging and reporting requirements significantly: callers need dense, structured, tiered operation evidence, not casual human-readable output.

**Logging and reporting requirements (known inputs, not final decisions):**

| Requirement             | Detail                                                                                                                                  |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Tiered logging          | `debug`, `info`, `warning`, `error`, `critical` — all five levels used deliberately                                                     |
| Default level           | `warning` for widget and library import; `info` for API server; `debug` available via CLI                                               |
| CLI control             | `blindtag --log-level debug` raises verbosity for any subcommand except widget                                                          |
| Library import safety   | No handler attached at import time — library callers own their logging config                                                           |
| Structured output       | Operation log entries carry: timestamp, operation type, anchor length, payload length, resolved token count, outcome, error type if any |
| Retained evidence       | Every API encode/decode call produces a retained log entry queryable by callers                                                         |
| Severity filtering      | Callers can request only `error`+ events or full `debug` traces                                                                         |
| API reporting endpoints | `/log`, `/log/export`, or equivalent — exact shape TBD in scoping session                                                               |
| Storage layer           | Not selected — append-only structured log file, SQLite, or equivalent                                                                   |
| Auth/transport scope    | Not settled — see invariant 5 DEFERRED status above                                                                                     |

The logging hook reservation (logger namespace, no handler at import, `_configure_logging` in CLI) is implemented in Pass C. The full structured handler, retention, and reporting endpoints are implemented in Pass J.

**Do not begin Pass J scope definition until joediggidyyy initiates the planning session after Pass N gate.**

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

| Decision             | Choice                                                         | Rationale                                                                                   |
| -------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Tray icon            | `assets/images/blindtag_thumbnail_basic.png`                   | Confirmed present; thumbnail variant is correct size for tray                               |
| Process model        | Single process, not a daemon/service                           | Qt clipboard signal requires a user-session message loop; services have no clipboard access |
| Widget-in-tray       | Same process, `BlindTagWindow` held live                       | Instant open, shared library state, zero IPC surface                                        |
| Auto-start method    | `winreg HKCU\...\Run` (Windows); deferred macOS/Linux          | stdlib `winreg`, no installer needed, user-session only                                     |
| Self-detection guard | Skip toast if widget is visible and frontmost                  | Simple boolean check; eliminates noise on encode without timing heuristics                  |
| Close behavior       | Widget close hides (not destroys) when `_tray_mode = True`     | Keeps window reusable from tray without re-instantiation                                    |
| Entry point          | `blindtag-tray = "blindtag.tray:run_tray"` in `pyproject.toml` | New script, no conflict with widget path                                                    |
| Platform scope       | Windows primary; macOS/Linux deferred                          | Auto-start is platform-specific; Qt tray works cross-platform but autostart deferred        |

### Preserved test scope (for when this pass is activated)

`tests/test_tray.py` — headless, ~60 lines: `TestTrayConstruction`, `TestTrayDecodeHook`, `TestTrayPause`, `TestAutoStartWindows` (mocked `winreg`). New calamum catalog entry `blindtag-tray` needed (definition previously drafted in this document's git history).

### Preserved security notes

No secrets. No network. `HKCU` registry write is user-authorized opt-in only. All Polymath invariants pass. See git history for the full invariant table from the original Pass I draft.

---

## Sign-off Readiness

| Gate                     | Status                                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Code review              | Done (this document)                                                                                         |
| Test suite review        | Done — 5 gaps identified                                                                                     |
| Security alignment       | Done — 2 gaps flagged                                                                                        |
| Calamum config           | DONE — baseline established Pass D                                                                           |
| CI pipeline              | DONE — GitHub Actions wired Pass A                                                                           |
| Force push authorization | Pending joediggidyyy                                                                                         |
| Pass K plan              | LOCKED — aesthetic alignment, glow button, taskbar icon; execute before Pass I                               |
| Pass I plan              | LOCKED — widget-based background posture; execute after Pass K gate                                          |
| Tray process (§10)       | DEFERRED — preserved for future pass after Pass I ships                                                      |
| Pass M plan              | LOCKED — bounded implementation plan aligned to Polymath + Calamum contracts                                 |
| Pass N plan              | LOCKED — corrective widget closure pass for terminal-free launch, hidden notification, and top-toggle parity |
| Pass J plan              | PLACEHOLDER — scope definition after Pass N gate                                                             |

**Execution sequence:** Pass K (aesthetic) → Pass I (background posture) → Pass M (library editor + button cleanup) → Pass N (widget closure corrections) → Pass J (logging).

Pass M is implementation-ready and bounded by the contracts in M.4–M.6.
