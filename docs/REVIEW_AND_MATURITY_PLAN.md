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

### Pass I — System tray background service (`blindtag-tray`)

**Status:** Planned. Authorized for planning; implementation begins after Pass H calamum gate is confirmed.

**Scope:** Add a standalone `blindtag-tray` entry point that runs the Plane 14 clipboard watcher as a persistent system-tray background process — no visible window at launch, OS-native toast notifications on payload detection, right-click context menu, and optional auto-start on login. The full `BlindTagWindow` widget is available on demand from the tray menu and runs in the same process.

#### I.1 — Architecture

```
blindtag-tray  →  blindtag.tray:run_tray()
                      │
                      ├── QApplication (windowless at launch)
                      ├── QSystemTrayIcon
                      │     ├── icon: assets/images/blindtag_thumbnail_basic.png
                      │     ├── tooltip: "BlindTag — Clip Watcher"
                      │     └── context menu (see §I.3)
                      ├── clipboard hook: QApplication.clipboard().dataChanged
                      │     └── decode(text) → showMessage() on hit
                      └── BlindTagWindow (instantiated once; hidden until opened)
```

Single process. The tray and the widget share one `QApplication` instance. The `BlindTagWindow` is created at startup and hidden; opening it from the tray calls `show()` / `raise_()` / `activateWindow()`.

#### I.2 — New file: `blindtag/tray.py`

Approximate structure (~130 lines):

```python
# blindtag/tray.py
"""
blindtag.tray
=============
System-tray background watcher — no main window at launch.
"""
import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon
from .core import decode
from .exceptions import InvalidPayloadError

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "images"
_ICON_PATH   = _ASSETS_DIR / "blindtag_thumbnail_basic.png"
_log = logging.getLogger("blindtag.tray")

class BlindTagTray:
    def __init__(self, app: QApplication) -> None:
        # ... QSystemTrayIcon + context menu + clipboard hook
    def _start_watcher(self) -> None:
        app.clipboard().dataChanged.connect(self._on_clipboard_change)
    def _on_clipboard_change(self) -> None:
        # same decode() pattern as widget — all exceptions swallowed
    def _notify(self, message: str) -> None:
        # QSystemTrayIcon.showMessage() — OS-native toast
    def _open_widget(self) -> None:
        # lazy-import BlindTagWindow, show/raise
    def _toggle_autostart(self, enabled: bool) -> None:
        # Windows: winreg; macOS: launchd plist; Linux: ~/.config/autostart
    def stop(self) -> None:
        app.clipboard().dataChanged.disconnect(self._on_clipboard_change)

def run_tray() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    tray = BlindTagTray(app)
    tray.show()
    sys.exit(app.exec())
```

#### I.3 — Tray context menu

| Menu item | Action |
|---|---|
| `Open BlindTag` | `show()` / `raise_()` / `activateWindow()` on `BlindTagWindow` |
| `Pause Watcher` / `Resume Watcher` | toggle `dataChanged` connection; icon dims/brightens |
| `Auto-start on login` (checkable) | write/remove registry key (Windows), launchd plist (macOS), `.desktop` (Linux) |
| `Quit` | `_stop_watcher()`, `app.quit()` |

Double-clicking the tray icon opens the widget (same as `Open BlindTag`).

#### I.4 — Auto-start implementation

**Windows (primary target):**
```python
import winreg  # stdlib, Windows only
KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
def _set_autostart_windows(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, access=winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, "BlindTag", 0, winreg.REG_SZ, f'"{sys.executable}" -m blindtag.tray')
        else:
            try: winreg.DeleteValue(k, "BlindTag")
            except FileNotFoundError: pass
```
Wrapped in `if sys.platform == "win32"`. The registry value stores `sys.executable` (the actual interpreter path in the active venv) — this is correct for user-installed packages. Autostart state is persisted in the registry itself; no additional config file needed.

**macOS:** Write/remove `~/Library/LaunchAgents/com.polymath.blindtag.plist` — out of scope for this pass; menu item hidden on non-Windows platforms unless `sys.platform == "darwin"` is explicitly extended.

**Linux:** Write/remove `~/.config/autostart/blindtag.desktop` — same deferral policy.

Initial delivery targets Windows only. Menu item is hidden on unsupported platforms.

#### I.5 — Widget integration changes

`BlindTagWindow.closeEvent` requires a one-line guard: when tray mode is active, the close button should hide the window rather than destroy it (so it can be re-opened from the tray without re-instantiating).

```python
# BlindTagWindow.closeEvent — updated
def closeEvent(self, event) -> None:
    self._stop_watcher()
    if getattr(self, "_tray_mode", False):
        event.ignore()
        self.hide()
        return
    super().closeEvent(event)
```

`_tray_mode` is set by the tray at construction: `win._tray_mode = True`.

#### I.6 — Self-detection guard (known interaction)

When the widget's `Encode` button writes a tagged string to the clipboard, the tray watcher will immediately detect the Plane 14 payload and fire a toast — notifying the user about their own just-encoded output. This is cosmetically noisy but not harmful.

**Chosen resolution:** In `BlindTagTray._on_clipboard_change`, skip notification if `BlindTagWindow` is currently visible and frontmost (`self._widget_win.isActiveWindow()`). The assumption is: if the widget is open and focused, the user already sees the encode result and does not need a toast. If the widget is hidden/backgrounded, the toast is useful.

This guard is simple (one boolean check), eliminates the self-notification in the common encode workflow, and requires no timing heuristics or flags.

#### I.7 — Calamum test catalog: new `blindtag-tray` definition

Add to `catalog/test_definitions.json`:

```json
{
  "id": "blindtag-tray",
  "title": "BlindTag System Tray Background Service",
  "summary": "Headless construction and decode-path tests for BlindTagTray. Verifies QSystemTrayIcon instantiation, clipboard decode hook fires on payload-bearing text, notification suppressed when watcher paused, autostart registry toggle (Windows mocked).",
  "status": "active",
  "category": "integration",
  "selector_policy": "exact-name-only",
  "profiles": ["default", "release"],
  "tags": ["smoke", "tray"],
  "policy_flags": ["deterministic-output", "local-only", "release-gate"],
  "evidence_requirements": ["stdout_capture", "stderr_capture", "report_json"],
  "default_lanes": ["pytest"],
  "metadata": {
    "module": "blindtag.tray",
    "test_file": "tests/test_tray.py"
  },
  "lanes": {
    "pytest": [
      {
        "id": "tray-pytest",
        "title": "pytest tests/test_tray.py",
        "command": ["{python}", "-m", "pytest", "tests/test_tray.py", "-v", "--tb=short"],
        "expected_artifacts": ["stdout", "stderr"],
        "evidence_requirements": ["stdout_capture", "stderr_capture"],
        "notes": "BlindTagTray construction, decode-path signal mock, pause-watcher suppression, auto-start registry mock (win32 only via unittest.mock)."
      }
    ],
    "sandbox_test": [],
    "empirical_test": []
  }
}
```

`blindtag-all` rollup command in the existing catalog already targets `tests/` — no change required to the rollup definition; `test_tray.py` is picked up automatically.

#### I.8 — New test file: `tests/test_tray.py`

| Class | Tests |
|---|---|
| `TestTrayConstruction` | tray instantiates without error (headless QApp fixture); icon path resolves to existing file; `_ICON_PATH` exists |
| `TestTrayDecodeHook` | mock `QApplication.clipboard()` to return encoded text → `_on_clipboard_change()` calls `decode()` and `_notify()`; mock clipboard returning plain text → `_notify()` not called |
| `TestTrayPause` | after `stop()`, additional clipboard signals do not call `_notify()` |
| `TestAutoStartWindows` | mock `winreg` → `_set_autostart_windows(True)` writes correct key; `_set_autostart_windows(False)` deletes key; `FileNotFoundError` on delete is silent (skip if `sys.platform != "win32"`) |

All tests are headless. No `showMessage()` call escapes to the OS — mock `QSystemTrayIcon.showMessage` in the fixture.

#### I.9 — `pyproject.toml` change

```toml
[project.scripts]
blindtag        = "blindtag.cli:main"
blindtag-api    = "blindtag.cli:_api_shim"
blindtag-widget = "blindtag.cli:_widget_shim"
blindtag-tray   = "blindtag.tray:run_tray"     # ← new
```

#### I.10 — Polymath security alignment

| Invariant | Status in this pass |
|---|---|
| 1. No secrets in source control | PASS — no credentials; only registry key name (public) |
| 2. Environment is the keyring | N/A — no secrets at runtime |
| 3. Names-only documentation | PASS |
| 4. Agents do not read secret material | PASS |
| 5. Fail closed on trust ambiguity | PASS — if icon asset missing, `QIcon` falls back gracefully; tray still functional |
| 6. Protected stores require integrity controls | N/A |
| 7. Sensitive state changes require explicit authorization | PASS — auto-start requires user opt-in via menu checkbox; no silent registry writes |
| 8. Retained evidence must be verifiable | N/A — tray produces no retained evidence artifacts; calamum test run produces evidence |
| 9. Path containment enforced | PASS — only reads from `assets/images/`; registry writes scoped to `HKCU` only |
| 10. Security messaging useful and secret-safe | PASS — toast shows payload excerpt only (48 chars, same pattern as widget) |

No new SEAM blockers introduced.

#### I.11 — Polymath style alignment

Toast notification content follows the operator contract (what happened / payload excerpt / next action implied by bringing up the widget). `QSystemTrayIcon.showMessage()` signature:
```python
tray_icon.showMessage(
    "BlindTag",                        # title
    f"Payload detected: {preview!r}",  # message (48 char preview)
    QSystemTrayIcon.MessageIcon.Information,
    3000,                              # ms display time
)
```
OS controls rendering; Polymath style contract is met at the content level.

#### I.12 — Out of scope for this pass

- macOS launchd / Linux `.desktop` autostart (deferred — Windows only)
- Per-app clipboard access gating on macOS sandbox distribution
- IPC between a separately-running tray instance and a separately-running widget instance (not needed — same process)
- Tray logging/reporting endpoints (deferred to Pass J)

#### I.13 — Deliverables summary

| Artifact | Action | Notes |
|---|---|---|
| `blindtag/tray.py` | CREATE | ~130 lines |
| `tests/test_tray.py` | CREATE | ~60 lines, headless |
| `catalog/test_definitions.json` | MODIFY | Add `blindtag-tray` definition |
| `pyproject.toml` | MODIFY | Add `blindtag-tray` entry point |
| `blindtag/widget.py` | MODIFY | `closeEvent` tray-mode guard (~5 lines) |
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

## Section 10 — Planned: System Tray Background Service (`blindtag-tray`)

**Status:** Plan locked. Implementation authorized after Pass H gate.

**Purpose:** Expose the clipboard watcher as an always-on background process that survives without the widget being open. Adds zero new dependencies beyond what is already required by the widget (PySide6 ≥ 6.8). The full implementation plan is in **Pass I** above.

### Key design decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Tray icon | `assets/images/blindtag_thumbnail_basic.png` | Confirmed present; thumbnail variant is correct size for tray |
| Process model | Single process, not a daemon/service | Qt clipboard signal requires a user-session message loop; services have no clipboard access |
| Widget-in-tray | Same process, `BlindTagWindow` held live | Instant open, shared library state, zero IPC surface |
| Auto-start method | `winreg HKCU\...\Run` (Windows); deferred macOS/Linux | stdlib `winreg`, no installer needed, user-session only |
| Self-detection guard | Skip toast if widget is visible and frontmost | Simple boolean check; eliminates noise on encode without timing heuristics |
| Close behavior | Widget close hides (not destroys) when `_tray_mode = True` | Keeps window reusable from tray without re-instantiation |
| Platform scope | Windows primary; macOS/Linux deferred | Auto-start is platform-specific; Qt tray works cross-platform but autostart deferred |

### Security posture (summary)

No secrets. No network. File I/O limited to reading `assets/images/blindtag_thumbnail_basic.png` (read-only) and writing one `HKCU` registry value (user-authorized opt-in, Windows only). All Polymath security invariants pass. No new SEAM blockers. See Pass I §I.10 for full invariant table.

### Test scope summary

`tests/test_tray.py` — headless, ~60 lines, four test classes: construction, decode hook, pause behavior, autostart registry (mocked). `blindtag-all` rollup picks up `test_tray.py` automatically via `tests/` glob.

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
| Pass I plan | LOCKED — implementation authorized after Pass H gate |
| Pass J plan | PLACEHOLDER — scope definition after Pass H gate |

**Post-Pass-H next action:** Execute Pass I (system tray), then initiate Pass J scope definition session with joediggidyyy.
