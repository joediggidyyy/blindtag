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

**Status:** Plan revised. Architecture pivot from separate tray app to widget posture enhancement. Implementation authorized after Pass H gate.

**Scope:** Extend `BlindTagWindow` with a second operating posture — "background" — reached via an explicit "Hide to background" control. In background posture the clipboard watcher stays active, the focus-steal notification is replaced by a custom ephemeral corner `NotificationWidget`, and the widget raises on notification click. No new entry point, no `QSystemTrayIcon`, no extra dependencies. All behavior lives inside the existing `blindtag-widget` entry point.

**Architecture driver:** The existing Clip Watch mechanism already keeps the watcher alive as long as the window is not closed (`hide()` does not trigger `closeEvent`). The two missing pieces for safe background use were (a) non-intrusive notification and (b) an explicit "hide" transition distinct from minimize and close.

#### I.1 — Two operating postures

| Posture | Window state | Notification mode | Entry |
|---|---|---|---|
| **Foreground** | Visible, always-on-top | Inline blue QLabel banner (current) | Normal launch or notification click |
| **Background** | Hidden, in taskbar | Ephemeral corner `NotificationWidget` | "Hide to background" button |

- **Foreground → Background:** User clicks "Hide to background" title-bar button. `self.hide()` called. Watcher stays connected. `_posture = "background"`.
- **Background → Foreground:** User clicks `NotificationWidget` body on a hit, or clicks the widget in the Windows taskbar (widget stays in taskbar while hidden — no `Qt.Tool` flag set). `_posture = "foreground"`.
- **Close (X):** Always a real close — stops watcher, destroys window. No interception. Close means quit.

#### I.1a — Architecture

```
blindtag-widget (existing entry point, no change)
    └── BlindTagWindow
          ├── _posture: str  ("foreground" | "background")
          ├── Clip Watch active + foreground → inline QLabel banner (current _notify_payload)
          ├── Clip Watch active + background → NotificationWidget.show_for(preview)
          └── "Hide to background" button → self.hide() + _posture = "background"

NotificationWidget  (new class — blindtag/notification.py)
    ├── Frameless, always-on-top, bottom-right of QScreen.availableGeometry()
    ├── Content: icon (32px) + "BlindTag" title + 48-char payload preview + × button
    ├── Auto-dismiss: QTimer, NOTIFY_DURATION_MS (reuses existing constant, ~4500ms)
    ├── Hover: pause auto-dismiss timer while mouse is inside widget
    ├── Click body: hide self + main_win.show() + raise_() + activateWindow()
    └── Click ×: hide self only (does not open widget)
```

No `QSystemTrayIcon`. No new entry point. No extra dependencies. Zero IPC.

#### I.2 — New file: `blindtag/notification.py`

Approximate structure (~60 lines):

```python
# blindtag/notification.py
"""
blindtag.notification
=====================
Ephemeral corner notification widget for background monitoring posture.
"""
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QScreen

NOTIFY_MARGIN_PX = 16

class NotificationWidget(QWidget):
    def __init__(self, main_win, duration_ms: int) -> None:
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._main_win = main_win
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self.hide)
        self._duration_ms = duration_ms
        self._build_ui()

    def show_for(self, preview: str) -> None:
        self._label.setText(f"Payload detected: {preview!r}")
        self._reposition()
        self._timer.start(self._duration_ms)
        self.show()

    def _reposition(self) -> None:
        screen = QScreen.virtualSiblingAt(self.screen(), QPoint(0, 0)) or self.screen()
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - NOTIFY_MARGIN_PX,
                  geo.bottom() - self.height() - NOTIFY_MARGIN_PX)

    def mousePressEvent(self, event) -> None:
        self.hide()
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()

    def enterEvent(self, event) -> None:
        self._timer.stop()

    def leaveEvent(self, event) -> None:
        self._timer.start(self._duration_ms)
```

#### I.3 — "Hide to background" UX surface

| Option | Assessment |
|---|---|
| Dedicated title-bar button (visible when Clip Watch active) | **Chosen** — explicit, discoverable, distinct from minimize |
| Override system minimize button when Clip Watch active | Fragile — breaks expected OS behavior |
| Keyboard shortcut only | Not discoverable |
| Clip Watch checkbox auto-hides | Too implicit |

Chosen: a "Hide" button in the title bar area, shown only while Clip Watch is active. Tooltip: `"Run in background — tap notification to return"`. Clicking it calls `self.hide()` and sets `_posture = "background"`.

#### I.4 — "Watcher alive" indicator without tray icon

`BlindTagWindow` does **not** use `Qt.Tool` window flag. A window without `Qt.Tool` remains in the Windows taskbar even when hidden. This provides:
- A visible presence indicator ("BlindTag is running")
- A click-to-raise recovery path for missed notifications

No additional indicator needed. The tray icon is therefore optional, not required.

#### I.5 — Tray icon: deferred to optional future enhancement

`QSystemTrayIcon` is not required for this design. Deferred scenarios where it adds value:
- User wants no taskbar presence at all (full background daemon feel)
- "Pause watcher" quick action without opening the window
- Per-user preference

If added in a future pass, it fits over the same `NotificationWidget`-based posture model without changes. The tray icon decision is fully decoupled from background posture delivery.

`blindtag-tray` as a separate entry point is **dropped** from this pass.

#### I.6 — Self-detection guard

When Clip Watch is in background posture and the user encodes something, the watcher fires on its own clipboard write. Guard: if `_posture == "foreground"` and `self.isActiveWindow()`, suppress `NotificationWidget` — the inline banner already shows. No timing heuristics needed.

#### I.7 — Widget integration changes

`BlindTagWindow` changes:
1. Add `_posture: str` field (`"foreground"` / `"background"`)
2. `_notify_payload()`: branch on `_posture` — inline QLabel banner vs. `self._notif_widget.show_for(preview)`
3. Add "Hide" button to title bar (show/hide driven by `_on_clip_watch_toggled`)
4. "Hide" button `clicked` → `self.hide()` + `self._posture = "background"`
5. `closeEvent`: unchanged — X always closes. No `_tray_mode` flag needed.
6. `NotificationWidget` instantiated once at `__init__`, owned by `BlindTagWindow`

#### I.8 — Calamum test coverage

No new catalog entry. `NotificationWidget` and background-posture behavior belong in `tests/test_widget.py` under the existing `blindtag-widget` lane.

New test classes to add to `tests/test_widget.py`:

| Class | Tests |
|---|---|
| `TestNotificationWidget` | Construction without error; `show_for()` sets label text; auto-dismiss timer fires; click body calls `show()`/`raise_()` on main window (mocked); hover pauses timer; × button hides without calling main window |
| `TestBackgroundPosture` | `_posture` defaults `"foreground"`; "Hide" button triggers `hide()` + posture change; `_notify_payload` routes to `NotificationWidget.show_for()` in background posture; `_notify_payload` routes to inline banner in foreground posture; X close stops watcher in either posture |

`blindtag-all` rollup covers `tests/test_widget.py` automatically. No catalog changes needed.

#### I.9 — `pyproject.toml` change

No change. `blindtag-tray` entry point is dropped.

#### I.10 — Polymath security alignment

| Invariant | Status |
|---|---|
| 1. No secrets in source control | PASS |
| 2. Environment is the keyring | N/A — no secrets |
| 3. Names-only documentation | PASS |
| 4. Agents do not read secret material | PASS |
| 5. Fail closed on trust ambiguity | PASS — notification renders 48-char excerpt only; no full payload exposed |
| 6. Protected stores require integrity controls | N/A |
| 7. Sensitive state changes require explicit authorization | PASS — posture change requires explicit button click; no silent transitions |
| 8. Retained evidence must be verifiable | N/A |
| 9. Path containment enforced | PASS — no new file I/O; `notification.py` reads no files |
| 10. Security messaging useful and secret-safe | PASS — notification shows excerpt, never full payload |

No new SEAM blockers.

#### I.11 — Polymath style alignment

`NotificationWidget` body text follows the operator contract (what happened / excerpt / implied next action = click to open):

```
BlindTag
Payload detected: "hello, world..."
```

Click raises the widget where the user sees the full decode result. Contract met.

#### I.12 — Out of scope for this pass

- `QSystemTrayIcon` / tray icon (optional future enhancement — see §I.5)
- Auto-start on login (requires persistent daemon or tray; deferred)
- macOS / Linux platform-specific notification surfaces
- Multiple simultaneous notification stacking

#### I.13 — Deliverables summary

| Artifact | Action | Notes |
|---|---|---|
| `blindtag/notification.py` | CREATE | `NotificationWidget` class, ~60 lines |
| `blindtag/widget.py` | MODIFY | `_posture` field, `NotificationWidget` owner, "Hide" button, posture branch in `_notify_payload` |
| `tests/test_widget.py` | MODIFY | Add `TestNotificationWidget` + `TestBackgroundPosture` |
| `CHANGELOG.md` | MODIFY | Pass I entry |

Gate: `calamum test run blindtag-all --project <path>`, `decision: go` required before commit.

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
