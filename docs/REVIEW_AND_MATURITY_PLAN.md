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

### 2026-05-31 live widget verification addendum (operator screenshots)

**Evidence reviewed this pass:**
- Encode-panel screenshot showing status `Encoded payload copied to clipboard.` after encoding `U+2705` with hidden payload `hello, world!`
- Decode-panel screenshot immediately after pasting the just-encoded glyph, showing only the visible checkmark in raw input and `No Plane 14 payload detected in this text`
- Emoji-flyout screenshot showing icon clicks with minimal pressed-state feedback
- Library-editor screenshot showing the current multi-column row presentation in the live surface

**Verified interpretation:**
- A live **encode -> clipboard -> decode** round-trip regressed. The operator-facing status message claims copy success, but the subsequent decode result shows the hidden payload did not survive the handoff to the next step.
- Based on the current implementation shape in `blindtag/widget.py`, the most likely fault family is **widget-surface transport**, not the core codec contract: the encoded composite is generated, but the invisible Plane 14 payload appears to be dropped somewhere between output-field storage, clipboard write, paste into the decode field, or a QTextEdit/plain-text round-trip.
- The current screenshots do **not** prove whether the loss occurs on encode output storage or on decode input capture; they do prove that the live widget round-trip is presently untrustworthy.
- Emoji/flyout click targets look visually inert during activation. Even if the click is registering, the surface currently under-signals interaction and should gain a conventional pressed-state shading transition so the user can see the action happen.

**Current release implication:**
- **PyPI publication is blocked by live evidence.** Automated tests remain valuable, but a package intended for near-term downstream consumption should not ship while the widget's flagship encode/decode clipboard path is visibly regressed.
- The right next lane is a narrow remediation pass focused on: (1) preserving the encoded payload across widget output/clipboard/input transport, (2) restoring visual press feedback on flyout/menu-like click surfaces, and (3) repeating the same live encode/decode proof with the installed `blindtag-widget.exe` path before packaging/publish.

**Recommended root-cause checkpoints for the next code pass:**
1. Audit whether the encoded composite is stored only in `QTextEdit` state before clipboard copy; if so, retain the exact encoded string in a dedicated runtime variable and copy from that source of truth instead of re-reading from a text widget.
2. Verify whether Qt text widgets preserve Plane 14 tag characters through `setPlainText(...)`, `toPlainText()`, clipboard copy, and paste. Test each hop independently.
3. Add a focused widget regression test that proves: encode a glyph anchor -> copy exact encoded string -> paste/read back -> decode returns the original hidden payload.
4. Add `:pressed` / active-shade styles to emoji-flyout cells and any menu-like action surfaces whose current ghost styling makes clicks appear unresponsive.

### 2026-05-31 diagnostic audit addendum (ORACL evidence pass)

**Audit objective:** determine whether the live glyph-round-trip failure is a deterministic BlindTag encode/decode regression or an intermittent transport failure in the widget / clipboard lane.

**Audit artifacts created this pass:**
- Diagnostic probe script: `projects/blindtag/semantics_staging/widget_transport_audit.py`
- Diagnostic probe script: `projects/blindtag/semantics_staging/widget_clipboard_win32_probe.py`
- Evidence JSON: `projects/blindtag/report_tmp/widget_transport_audit.json`
- Evidence JSON: `projects/blindtag/report_tmp/widget_clipboard_win32_probe.json`

**Verified findings:**
1. **Core codec is healthy in the audited scenario.**
    - The glyph case (`U+2705` + payload `hello, world!`) encoded and decoded correctly in every direct core check.
2. **`QTextEdit` is not the stripping point in the audited scenario.**
    - The transport probe showed exact preservation of Plane 14 characters through `QTextEdit.setPlainText(...) -> toPlainText()`.
3. **Widget output storage is not the stripping point in the audited scenario.**
    - `BlindTagWindow._do_encode()` produced an output string whose Plane 14 payload decoded correctly after a widget-field round-trip.
4. **The system clipboard can preserve the full encoded payload exactly.**
    - The Win32-backed probe recorded `exact-encoded` on all 8/8 direct Qt clipboard writes and all 8/8 widget `_encode_and_copy()` writes for the glyph scenario.
5. **The clipboard lane is still suspicious because it is intermittently unstable in this environment.**
    - The earlier transport probe emitted repeated Qt clipboard errors: `OleSetClipboard ... OpenClipboard Failed`, and that same run produced empty clipboard readbacks despite the widget success message.
    - Taken together with the later 8/8 exact-encoded pass, the evidence points to **intermittent clipboard acquisition/write instability**, not a deterministic Plane 14 stripping bug in the codec or text widgets.
6. **The widget currently overclaims success.**
    - `BlindTagWindow._encode_and_copy()` sets clipboard text and immediately reports `Encoded payload copied to clipboard.` with no retry, no verification, and no stale/sentinel detection.
    - If Windows rejects the clipboard open or the write races another owner, the UI can still claim success even when the actual clipboard content was not updated.
7. **Pressed-state click feedback is genuinely missing on the relevant surfaces.**
    - Source audit of `blindtag/widget.py` found hover styles but **no `:pressed` selectors**.
    - `_btn_ghost_style()` and `_EmojiFlyout` cell styles currently signal hover only, which explains the operator report that menu/flyout clicks look unresponsive.

**Diagnosis verdict:**
- The audited evidence does **not** support a blanket claim that BlindTag currently strips Plane 14 payloads during normal widget encode/decode.
- The stronger diagnosis is: **the widget's clipboard handoff is intermittently unreliable on Windows, and the current UI reports success without verifying that the system clipboard actually contains the encoded composite**.
- The click-feedback issue is independent and confirmed: the flyout / ghost-button surfaces under-signal activation because they lack a conventional pressed-state visual.

**Fully developed update plan for the next code pass:**
1. **Clipboard success hardening**
    - Keep the exact encoded composite in a dedicated runtime variable at encode time.
    - On copy, write from that in-memory source of truth rather than re-reading only from the UI field.
    - Add bounded retry/backoff around clipboard set on Windows.
    - Verify clipboard content after write (or at minimum verify non-stale update) before showing a success message.
    - If verification fails, surface a truthful warning/error state instead of `copied to clipboard`.
2. **Focused regression coverage**
    - Add a widget test for `glyph anchor -> encode -> copy -> read back -> decode` success.
    - Add a failure-path test that simulates clipboard write refusal / stale clipboard and asserts the widget does **not** report success.
    - Keep the current direct-core and widget-field checks as the non-regression baseline.
3. **Pressed-state visual feedback**
    - Add conventional background-shade / border-emphasis `:pressed` states to `_btn_ghost_style()`.
    - Add the same pressed-state treatment to `_EmojiFlyout` cell buttons and other menu-like click targets whose current ghost treatment reads as inert.
4. **Release gate after remediation**
    - Re-run focused widget regression tests.
    - Re-run full `blindtag-all` validation.
    - Repeat the installed-surface live proof on `blindtag-widget.exe` using the same glyph scenario that failed in operator testing.
    - Re-verification completed on 2026-05-31; this widget lane no longer blocks PyPI packaging/publish.

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

**Status:** COMPLETE — initial code changes gated at `20260531T085159Z-blindtag-all` (`decision: go`), with final hidden-notification closure later confirmed by `20260531T220238Z-blindtag-all` and operator live pass recorded on 2026-05-31.  
**Dependency:** Pass M codebase is the baseline. This pass is corrective and must land before Pass J scope or any additional widget feature growth.  
**Scope:** Close the remaining operator-observed gaps in the widget lane without broadening architecture: (1) enforce terminal-free widget launch as the only compliant widget surface, (2) make hidden notification delivery live-visible and close-stable, and (3) bring the top Encode / Decode toggle geometry into actual visual parity with the approved mock. No tray split. No new network surface. No new publishable artifact family.

---

#### N.1 — Evidence snapshot (2026-05-31)

| Open item                                        | Evidence                                                                                                                                         | Verified state                                                                                                                                   |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Terminal-free widget launch is non-negotiable    | Operator clarification on 2026-05-31; handoff gate at top of this document                                                                       | Requirement is locked: widget launch must be terminal-free.                                                                                      |
| Current widget CLI duplication creates ambiguity | `pyproject.toml` has `blindtag-widget` under `[project.gui-scripts]`; `blindtag/cli.py` exposes `blindtag widget`                                | Current correction direction is to keep the CLI launchpoint and adapt it to hand off to `blindtag-widget.exe` truthfully instead of removing it. |
| Top toggle buttons remain visually too wide      | Operator screenshot after the 92px width change; current `widget.py` shows `setFixedWidth(92)` for both toggles                                  | The last geometry tweak landed in code but did not reach the approved design target.                                                             |
| Hidden notification still not observed live      | Operator screenshot and follow-up report; current `notification.py` contains `_target_screen()`, `WA_ShowWithoutActivating`, and persistent mode | The concept and partial hardening exist, but live visibility remains unresolved.                                                                 |
| Close lane has an unclosed runtime defect        | Operator screenshot includes traceback pointing at `blindtag/widget.py:1468` (`closeEvent`)                                                      | The close path is not yet proven stable in the live hidden-notification workflow.                                                                |

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
| 1          | `blindtag/cli.py` and/or `pyproject.toml`        | MODIFY | Adapt the noncompliant `blindtag widget` route so it hands off to the same truthful widget launch contract without removing the public CLI launchpoint.   |
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

### Pass J — Logging and reporting infrastructure

**Status:** LOCKED — bounded execution plan defined on 2026-05-31; implementation remains separate.  
**Dependency:** Widget closure is complete and evidenced (`20260531T220215Z-blindtag-widget`, `20260531T220238Z-blindtag-all`), so the logging/reporting lane may proceed without reopening widget remediation.  
**See also:** Section 9 below for the detailed execution contract, evidence basis, security alignment, and validation sequence.

---

### Pass O — Clipboard reliability and pressed-state truthfulness closure

**Status:** LOCKED — bounded remediation plan derived from live operator evidence plus ORACL diagnostic audit.  
**Dependency:** Current BlindTag widget code as audited on 2026-05-31; this pass is the immediate publish blocker and must close before PyPI packaging/publication.  
**Scope:** Fix the Windows widget copy-trust lane and the inert-feeling click surfaces without broadening architecture. This pass is limited to the encode/copy/decode widget path, visual press feedback on menu/flyout ghost surfaces, focused regression coverage, Calamum validation/evidence integrity, and live installed-surface re-verification.

#### O.1 — Evidence basis for this pass

This pass is grounded in these verified surfaces:

- Operator screenshots from 2026-05-31 showing:
    - encode status claiming clipboard success,
    - immediate decode miss on the just-encoded glyph,
    - flyout/menu click surfaces with little visible activation feedback.
- `projects/blindtag/report_tmp/widget_transport_audit.json`
    - proved core codec health,
    - proved `QTextEdit` and widget output field preserve Plane 14 in the audited scenario,
    - captured intermittent clipboard-open/write failure symptoms in the same environment.
- `projects/blindtag/report_tmp/widget_clipboard_win32_probe.json`
    - proved the glyph scenario can succeed end-to-end on the system clipboard,
    - recorded 8/8 exact-encoded Win32 readbacks for both direct Qt writes and widget `_encode_and_copy()` writes in the audited rerun.
- `projects/blindtag/blindtag/widget.py`
    - confirms `_encode_and_copy()` currently reports success immediately after `QApplication.clipboard().setText(...)` with no verification or stale-content detection.
- `projects/blindtag/blindtag/widget.py` style audit
    - confirms hover states exist but no `:pressed` states exist on `_btn_ghost_style()` or `_EmojiFlyout` cells.

#### O.2 — Locked diagnosis carried into implementation

1. The audited evidence does **not** support a deterministic Plane 14 codec or text-widget stripping defect.
2. The strongest current diagnosis is **intermittent Windows clipboard handoff failure plus overconfident success messaging** in the widget.
3. The click-feedback issue is independent and confirmed: current flyout/ghost-button surfaces under-signal activation because they have no conventional pressed-state shading.
4. This pass must therefore improve **truthfulness and reliability**, not redesign BlindTag’s product architecture.

#### O.3 — Bounded implementation lanes

##### Lane O-A — Clipboard success hardening

Required behavior:

- Preserve the exact encoded composite in a dedicated in-memory source of truth at encode time.
- Copy from that source of truth rather than relying only on a UI-field readback.
- Add bounded retry/backoff around clipboard write on Windows.
- Verify that the clipboard now contains the intended encoded composite, or at minimum verify that the clipboard changed from known stale/sentinel state to the intended payload, before claiming success.
- If clipboard verification fails, the widget must **not** say `Encoded payload copied to clipboard.`
- Failure messaging must be calm, explicit, and next-action oriented.

Out of scope for Lane O-A:

- redesigning the core codec,
- adding a new transport layer,
- adding background services, tray surfaces, or alternate clipboard providers,
- adding runtime dependencies without explicit operator authorization.

##### Lane O-B — Pressed-state visual feedback

Required behavior:

- Add a conventional `:pressed` visual state to `_btn_ghost_style()`.
- Add the same pressed-state treatment to `_EmojiFlyout` glyph cells.
- Preserve the current calm Polymath palette language; pressed state should read as real activation, not as a new feature surface.
- The visual result must make click registration obvious even on low-noise ghost/menu surfaces.

Out of scope for Lane O-B:

- redesigning the full widget theme,
- introducing animation systems,
- changing the locked multi-column editor/action-button architecture beyond the requested feedback improvement.

##### Lane O-C — Evidence-backed regression coverage

Required behavior:

- Add focused widget regression coverage for:
    - glyph anchor -> encode -> copy -> read back -> decode success,
    - clipboard refusal / stale-content failure path,
    - truthful success/failure status signaling,
    - presence of pressed-state styles on affected surfaces where testable.
- Keep tests bounded to the audited fault family; do not sprawl into unrelated widget rewrites.

#### O.4 — Calamum test contract for this pass

This pass must validate through Calamum-owned evidence, not by ad hoc confidence alone.

**Tier 1 — Focused regression gate**

Run the narrowest affected widget test slice first. Minimum required families:

- clipboard copy/readback success path,
- clipboard failure-path truthfulness,
- pressed-state styling / click-surface regression coverage,
- any adjacent widget tests directly touched by the remediation.

**Tier 2 — Full project gate**

Run:

`calamum test run blindtag-all --project <blindtag-root>`

Required result:

- `decision: go`
- no unresolved failures in the retained report packet

**Tier 3 — Live installed-surface proof**

After package reinstall, ORACL must personally re-run the installed widget lane:

- `pip install -e .`
- `blindtag-widget.exe`

Required live proof:

1. encode glyph-anchor payload,
2. clipboard receives the encoded composite,
3. paste into decode lane,
4. decode returns the original hidden payload,
5. flyout/menu click surfaces show visible pressed-state feedback.

#### O.5 — Calamum security / integrity contract for this pass

This pass must align with Calamum’s retained-evidence and verification posture even though BlindTag itself is not introducing a new signed-call API surface.

Required retained artifacts after the full gate:

- `report_json`
- `report_md`
- `manifest_json`
- `checksums_json`
- checksum sidecars where emitted by the active Calamum lane

Required integrity behavior:

1. **Checksum verification is mandatory.**
     - Manifest/checksum artifacts must be present and consistent with the generated run artifacts.
2. **Signature verification is required when signing is configured.**
     - If the environment provides signing material (for example `CALAMUM_ED25519_*` or other active Calamum signing env expected by the runner), verify signed JSON artifacts after write.
3. **Names-only reporting when signing is absent.**
     - If signing is not configured, record that fact in names-only form and keep checksum/manifest verification as the active integrity lane.
4. **Fail closed on verification ambiguity.**
     - Do not treat a missing, invalid, or unverifiable integrity envelope as a soft warning for publish readiness.

No new privileged or signed-call surface is introduced by Pass O. Therefore:

- BlindTag does **not** need a new signed request flow in this pass,
- but the remediation pass must not weaken the existing Calamum evidence/signature/checksum lane used to validate and clear the release blocker.

#### O.6 — Polymath alignment contract for this pass

##### Polymath security alignment

Reference: `docs/guides/POLYMATH_SECURITY_MEASURES_AND_EXPECTATIONS.md`

Pass O must preserve:

- names-only evidence and no secret values in docs/output,
- fail-closed treatment of unverifiable publish-gate evidence,
- path containment to the BlindTag project and Calamum-generated evidence roots,
- no surprise machine mutation beyond the explicitly run validation/install commands.

Specific judgment for this pass:

- clipboard verification is a truthfulness improvement, not a new trust-boundary expansion;
- no new secrets, credentials, or host-specific configuration are introduced;
- generated audit scripts and evidence remain local review surfaces, not publishable artifacts.

##### Polymath user-facing alignment

Reference: `docs/guides/POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md`

Pass O must make the widget more truthful against the operator contract:

1. **What ran?** encode/copy action
2. **What happened?** clipboard copy succeeded or failed
3. **Why did it happen?** clipboard updated, stale, or unavailable
4. **What should happen next?** retry, copy manually, or proceed to decode
5. **Where is the evidence?** automated Calamum run artifacts + live installed-surface proof

The pressed-state update is also a Polymath requirement in practice: the UI should stay calm and low-noise, but it must not hide the fact that an action is being taken.

#### O.7 — BlindTag / project precedent alignment

This pass must preserve the local project rules and already-locked design precedents:

- keep widget launch terminal-free via `blindtag-widget.exe` as the normal handoff lane;
- keep the current single-window widget architecture;
- keep runtime dependency set unchanged unless joediggidyyy explicitly authorizes otherwise;
- keep the public API and codec contract unchanged;
- keep Calamum-first validation and retained evidence discipline;
- keep docs truthful about shipped behavior and block publication until live proof clears.

#### O.8 — Deliverables and sequence

| #      | Artifact                                         | Action | Notes                                                                                          |
| ------ | ------------------------------------------------ | ------ | ---------------------------------------------------------------------------------------------- |
| 1      | `blindtag/widget.py`                             | MODIFY | Clipboard truthfulness hardening + pressed-state feedback only within the bounded Pass O lanes |
| 2      | `tests/test_widget.py`                           | MODIFY | Focused clipboard reliability and click-feedback regression coverage                           |
| 3      | `catalog/test_definitions.json`                  | MODIFY | Update widget notes only if the focused coverage contract materially changes                   |
| 4      | `CHANGELOG.md`                                   | MODIFY | Record Pass O only after validation gate passes                                                |
| Gate A | focused widget regression                        | RUN    | Required before full Calamum gate                                                              |
| Gate B | `calamum test run blindtag-all --project <path>` | RUN    | Must return `decision: go`                                                                     |
| Gate C | evidence integrity verification                  | RUN    | Verify manifest/checksum set; verify signatures when configured                                |
| Gate D | installed live handoff proof                     | RUN    | `pip install -e .` then `blindtag-widget.exe` and repeat the glyph scenario                    |

#### O.9 — Acceptance criteria

Pass O is complete only when all of the following are true:

1. The widget no longer claims clipboard success when the clipboard update was not verified.
2. The audited glyph scenario succeeds through encode -> clipboard -> decode in the installed widget lane.
3. Focused widget regressions pass.
4. `blindtag-all` passes via Calamum with `decision: go`.
5. Manifest/checksum evidence is verified, and signed artifact verification is also completed when signing is configured.
6. Flyout/menu click surfaces show a visible pressed-state activation consistent with the calm Polymath design language.
7. PyPI publish readiness can be reclassified only after the live installed-surface proof is recorded.

#### O.10 — Precision implementation checklist (mandatory execution control)

Use this checklist as the execution control surface for Pass O. It is intentionally stricter than the lane summary above.

**Enforcement rule:** a checklist item is not complete just because the code landed or tests passed. Each item must also survive the final installed live-launch observation on `blindtag-widget.exe` before final ORACL signoff.

| #    | Precision item                          | Enforcement rule                                                                                                                                                                                                                 | Minimum automated proof                                                                                                                                           | Mandatory observed live-launch signoff                                                                                                                                                             |
| ---- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| O-1  | Scope remains inside Pass O             | No implementation may widen beyond clipboard truthfulness, pressed-state feedback, focused tests, Calamum validation, and evidence verification. No architecture drift, no new runtime dependency, no API/codec contract change. | Diff review against `widget.py`, `tests/test_widget.py`, `catalog/test_definitions.json`, and `CHANGELOG.md` only unless explicitly justified by the locked lane. | ORACL confirms the installed widget behavior changed only in the expected clipboard/click-feedback surfaces; no unrelated UI, API, or launch-path drift is visible.                                |
| O-2  | Encoded source-of-truth retained        | Encode path must retain the exact encoded composite in runtime memory before any clipboard handoff.                                                                                                                              | Focused widget test proves encode result is preserved and reused by the copy lane.                                                                                | ORACL launches the installed widget, encodes the glyph scenario, and confirms the copied/decode-ready result behaves as one coherent encode/copy action rather than a stale UI readback accident.  |
| O-3  | Clipboard write is bounded and verified | Copy logic must use bounded retry/backoff and must not claim success until the clipboard update is verified or positively distinguished from stale prior content.                                                                | Focused widget tests cover success path plus refusal/stale-content failure path.                                                                                  | ORACL observes the installed widget either: (a) truthfully reports verified copy success and the pasted decode succeeds, or (b) truthfully reports failure without a false success claim.          |
| O-4  | Success/failure messaging is truthful   | The widget must never emit `Encoded payload copied to clipboard.` when the update was not verified. Failure text must be calm, explicit, and next-action oriented.                                                               | Focused widget assertions on exact success/failure status text or equivalent message-state contract.                                                              | ORACL observes the installed widget messaging during the live glyph scenario and confirms the message matches what actually happened on the clipboard/decode path.                                 |
| O-5  | Ghost/menu pressed states land          | `_btn_ghost_style()` must include a visible `:pressed` state and preserve the calm Polymath palette.                                                                                                                             | Style regression check in `tests/test_widget.py` where practical.                                                                                                 | ORACL clicks the installed surface and visually confirms ghost/menu-like controls no longer look inert during activation.                                                                          |
| O-6  | Emoji flyout pressed states land        | `_EmojiFlyout` cell styling must include a visible `:pressed` state aligned to the same design language.                                                                                                                         | Focused widget/style regression coverage where practical.                                                                                                         | ORACL opens the installed emoji flyout and visually confirms click registration is obvious during cell activation.                                                                                 |
| O-7  | Focused regression gate passes          | Only the narrow Pass O fault family should be exercised first; no skip-by-hope path to the full gate.                                                                                                                            | Clean focused widget regression run for clipboard truthfulness and pressed-state coverage.                                                                        | ORACL repeats the same user-facing behavior live after the focused gate so the pass is not closed on headless proof alone.                                                                         |
| O-8  | Full Calamum gate passes                | `calamum test run blindtag-all --project <blindtag-root>` must return `decision: go` with no unresolved retained-report failures.                                                                                                | Retained Calamum run packet and console evidence.                                                                                                                 | ORACL performs the installed live launch after the passing Calamum run and confirms the exact audited glyph scenario succeeds on the shipped surface, not just in automation.                      |
| O-9  | Evidence integrity is verified          | Required retained artifacts (`report_json`, `report_md`, `manifest_json`, `checksums_json`, sidecars where emitted) must exist and verify; signed JSON artifacts must also verify when signing is configured.                    | Checksum/manifest verification; signature verification when configured; names-only record when signing is absent.                                                 | ORACL signs off only after the live launch being used for final approval is tied back to the verified retained evidence packet for the same pass.                                                  |
| O-10 | Final installed handoff proof clears    | `pip install -e .` must precede the last signoff run, and `blindtag-widget.exe` is the mandatory final approval surface.                                                                                                         | Reinstall completed after the last relevant code/edit pass.                                                                                                       | ORACL personally launches `blindtag-widget.exe`, runs the glyph encode -> clipboard -> decode scenario, confirms pressed-state feedback, and records this observed run as the final signoff event. |

**Hard stop rule:** if any item above lacks its corresponding live-launch observation, Pass O remains open even if pytest and Calamum are green. Green bars are helpful; they are not a hall pass.

#### O.11 — Final implementation readiness and governance alignment assessment

**Assessment date:** 2026-05-31  
**Assessment scope:** readiness to execute Pass O exactly as locked in this document; not a claim that Pass O is already implemented or release-cleared.

##### Verdict summary

- **Implementation readiness:** **YES** — Pass O is sufficiently bounded, evidenced, and sequenced to execute without further planning expansion.
- **Governance alignment:** **YES** — The pass aligns with BlindTag local instructions, Polymath security/style expectations, and Calamum validation/integrity discipline.
- **Release / publish readiness:** **NO** — publication remains correctly blocked until the Pass O checklist, evidence verification, and final observed live-launch signoff all clear.

##### Why the implementation lane is ready

1. **Root-cause direction is specific enough.**
    - Current evidence narrows the problem to clipboard reliability/truthfulness plus missing pressed-state feedback, not a vague full-widget rewrite.
2. **Scope boundary is mature.**
    - The plan explicitly forbids architecture drift, dependency growth, API changes, and codec-contract churn.
3. **Validation sequence is complete.**
    - Focused regression -> full `blindtag-all` -> integrity verification -> installed live launch is a complete and correctly ordered execution ladder.
4. **The final handoff rule is explicit.**
    - Final signoff already requires ORACL-observed launch on `blindtag-widget.exe`, and the precision checklist now applies that requirement to every completion item.

##### Governance alignment assessment

| Governance surface                                               | Verdict | Evidence basis                                                                                                                                    |
| ---------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `projects/blindtag/AGENT_INSTRUCTIONS.md` scope/minimalism rules | ALIGNED | Pass O remains widget/test/catalog/changelog bounded, preserves dependency policy, and keeps API/codec/public-surface stability intact.           |
| BlindTag handoff gate at top of this plan                        | ALIGNED | Pass O requires installed `blindtag-widget.exe` live observation before final signoff.                                                            |
| Polymath security expectations                                   | ALIGNED | Names-only evidence, fail-closed publish gate, no new secret surface, and required retained-evidence verification are all explicitly preserved.   |
| Polymath user-facing style expectations                          | ALIGNED | The lane centers truthful operator messaging, visible interaction feedback, and evidence-backed next-step clarity.                                |
| Calamum validation discipline                                    | ALIGNED | The pass requires focused regression evidence plus full `blindtag-all` and retained artifact verification rather than ad hoc pytest-only closure. |
| Publish governance                                               | ALIGNED | PyPI remains blocked until live installed-surface proof and verified retained evidence clear the exact audited failure scenario.                  |

##### Remaining blockers to final signoff

Pass O is ready to execute, but the following remain intentional blockers to closure until the work is actually performed:

1. Clipboard truthfulness hardening is not yet implemented.
2. Pressed-state feedback is not yet implemented on the affected surfaces.
3. Focused widget regressions for the new truthfulness path are not yet recorded.
4. The final `blindtag-all` retained evidence packet for the completed Pass O code does not yet exist.
5. The mandatory ORACL-observed installed launch proof for the corrected widget does not yet exist.

##### Final judgment

Pass O is **execution-ready and governance-aligned**.

Pass O is **not** signoff-ready, release-ready, or publish-ready until every item in the precision checklist above is complete and the final observed `blindtag-widget.exe` launch proves the exact clipboard and pressed-state fixes on the installed surface.

#### O.12 — 2026-05-31 post-implementation live UI follow-up (operator screenshots)

**Evidence reviewed this follow-up:**

- Live screenshot of the emoji flyout open over the Encode panel
- Live screenshot of the help drawer open over the main widget surface

**Verified follow-up findings:**

1. **Emoji flyout close behavior is still below the expected conventional contract.**
     - Current live behavior does not provide a dependable close path when the drawer is opened and the operator decides not to select anything.
     - The expected contract is conventional: **click the trigger again or click away to dismiss**.
     - This is a real usability gap, not a cosmetic preference.

2. **Help drawer legibility is still inadequate in live use.**
     - The current main-window translucency and the visual competition from the underlying surface continue to interfere with reading the help content.
     - The issue is not the existence of the drawer; it is the readability of the text once opened.

3. **The flyout click-response improvement was not sufficient on the live surface.**
     - The current update should be treated as **insufficient**, not necessarily absent.
     - The operator still does not perceive clear press/activation feedback on the menu-like flyout surface.
     - The most likely reason is that the landed `:pressed` styling is either too subtle to register in the live palette or is visually lost because selection closes the surface too quickly for the pressed state to read.

**Recommended follow-up handling (no code changes in this pass):**

##### A. Emoji flyout dismissal contract

Recommended priority: **high**

Preferred correction:

- make the emoji trigger a true toggle:
    - first click opens,
    - second click closes,
    - click-away also closes.

Implementation recommendation:

- keep the trigger-click toggle as the primary close contract,
- add broader click-away dismissal using an application-level or wider-surface mouse filter rather than relying only on narrow parent-local event routing.

##### B. Help drawer legibility

Recommended priority: **high**

Preferred correction:

- temporarily increase the widget body opacity to a fully opaque state while the help drawer is open.

Preferred companion treatment:

- add a subtle dim/scrim effect across the non-help portion of the widget while the drawer is open so the operator's eye is pulled toward the help content.

Alternative acceptable solutions:

1. make the drawer/card backgrounds more opaque and slightly more elevated,
2. widen the drawer modestly and increase body-text line spacing,
3. keep overall window opacity unchanged but darken only the main content plane behind the drawer.

Current recommendation ranking:

- **best:** full-opacity window + subtle body scrim while help is open,
- **good:** opaque drawer + darker main-content plane,
- **acceptable fallback:** larger text / spacing / width only.

##### C. Flyout click-response visibility

Recommended priority: **medium-high**

Preferred correction:

- strengthen the pressed-state delta so it is unmistakable at a glance:
    - darker filled pressed background,
    - brighter text/glyph or subtle accent border,
    - optional 1px inset/downshift feel.

Likely required companion correction:

- allow the pressed state to remain visible for at least one paint cycle before the flyout dismisses on selection.

Interpretation note:

- this follow-up should be recorded as **"pressed-state patch landed but did not clear live perceptibility"**, not as **"feature omitted"**.

**Signoff impact:**

- These live findings mean the widget still does **not** meet final human-facing signoff quality even though the automated Pass O coverage and retained-evidence lane are green.
- Clipboard-truthfulness remediation remains valuable and real, but final release confidence still requires a follow-up UI polish/closure pass covering:
    - flyout dismissal contract,
    - help-panel readability,
    - and stronger perceptible press feedback on the flyout/menu surface.

#### 2026-05-31 CLI confirmation-surface audit addendum (no-code review)

**Audit trigger:** joediggidyyy requested that all BlindTag CLI actions provide human-consumable confirmation or handled error text, using the pasted external launcher screenshot only as a rough formatting expectation rather than a content template.

**Evidence reviewed this pass:**

- `projects/blindtag/docs/CLI_IMPLEMENTATION_CHECKLIST.md`
- `projects/blindtag/docs/CLI_SCHEMA.md`
- `projects/blindtag/blindtag/cli.py`
- `projects/blindtag/tests/test_cli.py`
- live sampled output from:
    - `python -m blindtag --help`
    - `python -m blindtag encode "anchor" "café"`
    - `python -m blindtag decode "plain text"`
    - `python -m blindtag strip "plain text"`

**Verified current state:**

1. **Basic handled-error routing exists, but it is not yet a full human-facing confirmation surface.**
    - `encode`, `decode`, `api`, and `widget` do route some failures to stderr with a BlindTag-prefixed line.
    - Example observed this pass: `blindtag encode: Payload character at index 3 is invalid ...`
    - This satisfies the minimum "not a traceback" bar in several cases, but it does **not** consistently answer the operator-facing questions "what happened?" and "what should I do next?"

2. **Successful codec actions are still shell-lean, not human-confirming.**
    - `strip` on a clean string currently prints only the raw result.
    - `decode` on a clean miss prints nothing and exits 0.
    - `encode` default text mode prints only the encoded composite.
    - This is script-friendly, but it does **not** meet joediggidyyy's stated requirement that CLI actions provide a friendly, structured confirmation of action.

3. **Launcher actions do not currently emit a BlindTag-owned success confirmation block.**
    - `blindtag widget` returns the handoff code from `_launch_widget_process()`, but `cli.py` emits no human-readable success packet when launch succeeds.
    - `blindtag api` delegates into `run_server(...)` with no BlindTag-owned startup summary before control passes to the server runtime.
    - Compared with the pasted launcher example, these are the most visibly incomplete confirmation surfaces.

4. **The current implementation does not fully satisfy the already-written Pass C style/security checklist.**
    - `CLI_IMPLEMENTATION_CHECKLIST.md` requires CLI output to answer: **what ran, what happened, why, what next**.
    - The same checklist also requires error output to include **reason + next action**.
    - `cli.py` and `tests/test_cli.py` do not currently lock or verify that richer confirmation contract.

5. **There are additional plan-vs-implementation variances inside the CLI lane beyond confirmation text.**
    - `CLI_SCHEMA.md` planned global `--log-level` / `--verbose`; current `cli.py` does not implement them.
    - The logging-hook reservation (`_configure_logging()`) planned in the checklist/schema is not present in `cli.py`.
    - The locked top-level import-budget note was narrower than the current implementation shape; `cli.py` imports `os`, `shutil`, `subprocess`, `blindtag.core`, and `blindtag.exceptions` at module load.
    - `tests/test_cli.py` validates exit codes and basic routing, but not the richer human-facing confirmation grammar joediggidyyy is now asking for.

**Unresolved items for the CLI lane (verified against current code):**

- **CLI-1 — Human-facing success confirmations are unresolved.**
  No consistent friendly confirmation block exists for successful `encode`, `decode`, `strip`, `api`, or `widget` actions.

- **CLI-2 — Next-action guidance in error paths is unresolved.**
  Current stderr lines give a reason, but generally not a concrete next step.

- **CLI-3 — Launcher-summary contract is unresolved for `api` and `widget`.**
  These surfaces are the best fit for a structured launcher-style summary packet, and neither currently provides one.

- **CLI-4 — Script-safe vs human-friendly output policy is unresolved.**
  The code currently preserves raw stdout for codec commands, but the project docs also ask for human-consumable confirmation. The channel policy (stdout vs stderr vs TTY-sensitive behavior) is not yet reconciled.

- **CLI-5 — Pass C logging-hook work remains unresolved.**
  The planned `_configure_logging()` / global log-level surface is still absent.

- **CLI-6 — Test coverage for confirmation text is unresolved.**
  Current CLI tests do not lock success-summary text, next-action wording, or launcher confirmation structure.

**Recommended bounded next lane (no code executed in this pass):**

1. **Keep machine-safe result channels intact.**
    - Preserve raw stdout for `encode`, `decode`, and `strip` results.
    - Preserve clean JSON on stdout for `--out json`.
    - Do **not** pollute those result channels with decorative prose.

2. **Add human-readable confirmation on the operator channel.**
    - Preferred rule: emit the friendly confirmation block on **stderr** for codec commands when running in human-facing mode, so stdout stays script-safe.
    - For launcher commands (`api`, `widget`), emit a short BlindTag-owned summary block immediately before/after handoff.

3. **Use one stable confirmation grammar across commands.**
    - Recommended structure:
        - `BlindTag :: <command>`
        - `decision: <verb phrase>`
        - `Summary` block with 2–4 compact fields
        - `Next action` line
    - This matches joediggidyyy's pasted expectation at the structure level without copying that launcher's specific content.

4. **Treat decode-clean-miss as a handled outcome, not silent ambiguity, in human mode.**
    - Keep stdout empty for scripting if required,
    - but add stderr confirmation such as "no payload found" plus the next step when a human is running the command interactively.

5. **Lock the behavior in tests before implementation closes.**
    - Add explicit CLI tests for:
        - success confirmation on `widget` handoff,
        - startup summary on `api`,
        - reason + next action on handled codec errors,
        - human-mode decode clean-miss confirmation,
        - suppression/cleanliness of stdout in machine-readable paths.

**Recommendation summary:**

- The CLI lane is **functionally implemented** but **not yet human-confirmation complete**.
- The highest-value unresolved items are `widget` and `api` launcher confirmations, followed by a consistent reason/next-step pattern for handled errors.
- Before any code pass for this lane, BlindTag should explicitly choose the output-channel rule: **raw result on stdout, friendly confirmation on stderr/interactive channel** is the cleanest fit to both the existing scriptability contract and joediggidyyy's requested operator experience.

**Implementation receipt (2026-05-31 later pass):**

- The bounded CLI confirmation update has now been implemented in `blindtag/cli.py` and covered in `tests/test_cli.py`.
- Calamum CLI-lane validation passed at `20260531T214710Z-blindtag-cli` (`decision: go`).
- Full-suite confirmation passed at `20260531T214732Z-blindtag-all` (`decision: go`).
- Retained artifact checksum verification succeeded for both runs; signing-env remained names-only absent (`CALAMUM_ED25519_PUBLIC_KEY=missing`, `CALAMUM_POLICY_SIGNING_KEY=missing`).
- The remaining intentionally open CLI-adjacent items are the broader Pass C drift items not required for this bounded confirmation pass (notably global log-level / logging-hook reservation), not the human-confirmation surface itself.

#### 2026-05-31 hide-to-background relaunch anchor remediation receipt

**Verified problem statement:**

- Live operator report narrowed the remaining notification issue: hidden payload-hit notifications were appearing, but the promised relaunch anchor was still not firing at the moment the widget was hidden.

**Implemented correction:**

- `BlindTagWindow._hide_to_background()` now emits the persistent background relaunch notification immediately when Clip Watch is active.
- The hide-time relaunch anchor uses a stable non-secret preview (`Clip Watch active - click to return`) and remains replaceable by later hidden payload notifications.
- The hide path stays no-op for the notification surface when the watcher is inactive.

**Automated evidence:**

- Widget-lane Calamum validation passed at `20260531T220215Z-blindtag-widget` (`decision: go`).
- Full-suite confirmation passed at `20260531T220238Z-blindtag-all` (`decision: go`).
- Retained artifact checksum verification succeeded for both runs; signing-env remained names-only absent (`CALAMUM_ED25519_PUBLIC_KEY=missing`, `CALAMUM_POLICY_SIGNING_KEY=missing`).

**Closeout status:**

- The hide-trigger path is covered by focused widget regression coverage and full-suite Calamum evidence.
- Operator live testing passed on 2026-05-31, closing the real desktop relaunch-anchor lane for this remediation pass.
- This widget-remediation lane is now closed and no longer blocks the next logging/reporting planning lane.

---

## Section 9 — Planned: Backend/API Reporting Layer

**Status:** LOCKED — bounded Pass J execution plan ratified on 2026-05-31.

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

The logging hook reservation described in `CLI_SCHEMA.md` is **not** fully implemented in the shipped code as of the 2026-05-31 review pass. `blindtag/cli.py` does not expose the planned global `--log-level` / `--verbose` flags and does not define `_configure_logging()`, while `blindtag/core.py` and `blindtag/api.py` currently operate without the planned `logging.getLogger(__name__)` reservation hooks. Pass J must therefore either absorb that bootstrap work or split it into a narrow prerequisite pass before structured retention/reporting lands.

### 2026-05-31 logging/reporting implementation gap review (no-code audit)

**Audit scope:** compare the current logging/reporting plan against the shipped BlindTag implementation after widget closure, with emphasis on API-first use, retained evidence, and implementation-ready next steps.

**Sources reviewed:**

- Planning surfaces: `docs/REVIEW_AND_MATURITY_PLAN.md`, `docs/CLI_SCHEMA.md`
- Runtime surfaces: `blindtag/cli.py`, `blindtag/api.py`, `blindtag/core.py`, `run_api.py`
- Validation/governance surfaces: `tests/test_cli.py`, `tests/test_api.py`, `catalog/test_definitions.json`

#### Current implementation snapshot

1. **Correlation header is present at the API boundary.**
    - `blindtag/api.py` adds `X-Request-Id` via middleware and `tests/test_api.py` verifies format, uniqueness, and presence on error responses.
2. **Human-facing CLI confirmations are implemented, but logging control is not.**
    - `blindtag/cli.py` emits structured stderr confirmation blocks for human runs, yet the planned global logging controls and bootstrap hook are absent.
3. **API launcher verbosity exists only as Uvicorn process verbosity.**
    - `run_api.py` and `blindtag api --log-level ...` pass a log level into `uvicorn.run(...)`, but this is not a BlindTag-owned structured event layer.
4. **No retained operation log exists yet.**
    - No append-only log store, no SQLite/file-backed event ledger, and no structured export surface exist in the shipped code.
5. **No reporting/query API exists yet.**
    - There is no `/log`, `/log/export`, or equivalent endpoint in `blindtag/api.py`.
6. **No test/catalog contract exists for reporting.**
    - `catalog/test_definitions.json` includes no reporting-specific definition, and the current test suite contains no assertions for retained-operation logging, severity filtering, or export/query behavior.

#### Gap matrix

| Area                       | Planned contract                                                                 | Current state                                                                        | Gap verdict | Recommendation                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------- | ---------------------------------------------------------------------------------------------------------------------- |
| Logger bootstrap           | Global CLI logging control plus `_configure_logging()` hook reservation          | Absent in `blindtag/cli.py`; no global `--log-level` / `--verbose`                   | **High**    | Land the bootstrap hook first so later reporting work does not have to reopen CLI routing                              |
| Library logger reservation | `logging.getLogger(__name__)` in API/core without import-time handler attachment | No module logger reservation present                                                 | **Medium**  | Add named loggers in `core.py` and `api.py` without attaching handlers at import time                                  |
| Structured event schema    | Timestamped operation records with outcome/error metadata                        | No BlindTag-owned structured event emission                                          | **High**    | Lock an event schema before choosing storage so tests and exports share one contract                                   |
| Retained storage           | Queryable retained event history                                                 | No storage layer selected or implemented                                             | **High**    | Prefer one append-only authority first; defer multi-backend ambition until after the schema and query needs are proven |
| Reporting endpoints        | `/log`, `/log/export`, or equivalent caller-facing reporting surface             | No reporting endpoints exist                                                         | **High**    | Scope read-only query/export endpoints only for the first pass; avoid write/mutation/report management surfaces        |
| Severity filtering         | Caller-selectable thresholds (`error+`, `debug`, etc.)                           | No event filtering surface exists; only Uvicorn verbosity for the server process     | **Medium**  | Make filtering a query concern on top of stored structured levels, not a separate bespoke reporting grammar            |
| Correlation continuity     | Request ID linked to retained evidence and exported reports                      | `X-Request-Id` exists, but is not persisted into a BlindTag-owned event/report layer | **Medium**  | Reuse `X-Request-Id` as the primary per-request join key rather than inventing a second correlation token              |
| Validation/governance      | Reporting lanes and tests in Calamum + pytest                                    | No reporting catalog/test coverage exists                                            | **High**    | Add reporting-specific catalog entries and tests in the same pass as the first shipped reporting surface               |

#### Recommendations

1. **Split Pass J into two layers mentally, even if it ships under one label.**
    - Layer 1: logger bootstrap + event schema + retained storage authority.
    - Layer 2: read-only API reporting/query/export surface built on top of that stored event stream.
2. **Use the existing `X-Request-Id` as the canonical correlation key.**
    - It already exists in `blindtag/api.py`; the missing step is persistence, not reinvention.
3. **Do not start with multiple storage backends.**
    - Pick one authoritative retained surface first (append-only JSONL or SQLite are the obvious candidates) and lock the schema around it.
4. **Keep import-time library behavior quiet.**
    - The planning intent is still correct here: library consumers should not get forced handlers or surprise stderr chatter just by importing BlindTag.
5. **Treat reporting as an API contract, not a console prettification exercise.**
    - CLI confirmation is already handled. The remaining work is machine-consumable retained evidence for downstream callers.
6. **Bind tests to the first reporting shape immediately.**
    - The first shipped `/log` / export contract should land with pytest coverage and matching Calamum catalog lanes so the reporting layer is governed from day one.

#### Concise verdict

- BlindTag has **partial foundations** for Pass J: request correlation exists and CLI confirmation is already operator-friendly.
- BlindTag does **not yet have** the actual reporting substrate: no logger bootstrap, no structured retained event stream, no reporting endpoints, and no governance/tests for that surface.
- The cleanest next move is a bounded design pass that locks: **event schema -> single retained store -> read-only query/export endpoints -> matching Calamum lanes**.

### Pass J — locked execution plan

**Plan posture:** This section converts the reviewed evidence into a bounded implementation lane. It is intentionally narrower than a full observability platform and is designed to land with no new runtime dependency and no product-surface sprawl.

#### J.1 — Locked decisions

1. **Single retained-store authority in the first pass:** use an append-only JSONL store as the canonical retained event ledger for Pass J.
    - Preferred root: `.blindtag/generated/reporting/`
    - Preferred primary ledger: `.blindtag/generated/reporting/operations.jsonl`
    - Preferred export root: `.blindtag/generated/reporting/exports/`
    - Rationale: JSONL matches Calamum precedent (`run_index.jsonl`, `report_index.jsonl`), is append-friendly, stdlib-safe, and avoids premature multi-backend complexity.
2. **No new runtime dependency in Pass J.**
    - Use only stdlib/logging/FastAPI surfaces already present in BlindTag.
    - SQLite may be revisited only in a future scale pass if JSONL proves insufficient.
3. **Logger bootstrap lands in the same pass as retained reporting.**
    - Pass J absorbs the currently-missing `_configure_logging()` / global CLI log-level work rather than treating it as an unowned future drift item.
4. **Read-only query, controlled export.**
    - Query surface is read-only.
    - Export surface is explicit and controlled; it may write artifacts only under the server-owned reporting export root.
5. **Correlation key is not reinvented.**
    - `X-Request-Id` is the canonical per-request join key and must be persisted into retained operation records and export packets.
6. **No import-time handler attachment.**
    - Library use stays quiet by default; CLI/API startup owns handler attachment.
7. **Widget stays warning-silent.**
    - Pass J does not expand the widget into a new reporting console or verbose desktop telemetry surface.
8. **Export mutation follows Calamum-style trust discipline.**
    - Simple read-only log queries do not require a privileged signed request.
    - Export requests must fail closed on invalid/missing trust material when signing is configured.

#### J.2 — Scope boundary

Pass J is limited to:

- logger bootstrap and log-level control;
- module logger reservation in `core.py` / `api.py`;
- append-only retained event writing;
- read-only API query surface for retained events;
- controlled export surface for retained log evidence;
- pytest + Calamum governance coverage for the reporting lane;
- doc/catalog updates required to describe and validate the new reporting surface.

Pass J explicitly excludes:

- GUI reporting panels, tray dashboards, or widget history browsers;
- remote/multi-tenant auth redesign beyond the bounded export trust gate;
- alternate storage backends in the same pass;
- background agents, services, or external telemetry sinks;
- any release, publish, or packaging broadening not directly required by the reporting lane.

#### J.3 — Evidence basis carried into implementation

This plan is grounded in these already-verified facts:

- `blindtag/api.py` already emits `X-Request-Id`, and `tests/test_api.py` verifies presence, uniqueness, and error-path continuity.
- `blindtag/cli.py` already separates human stderr confirmations from machine-safe stdout, proving BlindTag can preserve human-vs-machine channel discipline.
- `blindtag/cli.py` still lacks global `--log-level` / `--verbose` and `_configure_logging()`.
- `blindtag/core.py` and `blindtag/api.py` still lack the planned `logging.getLogger(__name__)` reservation hooks.
- `catalog/test_definitions.json` already treats Calamum evidence (`stdout_capture`, `stderr_capture`, `report_json`) as the validation baseline for BlindTag surfaces.
- Calamum retained evidence already produces `report_json`, `report_md`, `manifest_json`, `checksums_json`, checksum sidecars, and names-only signing-state reporting when signing is absent.
- Polymath security guidance requires names-only evidence, fail-closed trust ambiguity, verifiable retained evidence, and explicit authorization for sensitive state changes.

#### J.4 — Bounded implementation lanes

##### Lane J-A — Logger bootstrap and quiet-import reservation

Required behavior:

- Add global CLI controls: `--log-level LEVEL` and `--verbose`.
- Add `_configure_logging()` in `blindtag/cli.py`.
- Add `logging.getLogger(__name__)` reservation hooks to `blindtag/core.py` and `blindtag/api.py` with **no** import-time handler attachment.
- Keep widget launch pinned to warning-level logging regardless of global CLI verbosity.

Acceptance intent:

- BlindTag library imports remain quiet.
- CLI/API startup owns runtime handler attachment.
- The logging substrate exists before any retained reporting/export logic tries to attach to it.

##### Lane J-B — Retained event schema and append-only authority

Required behavior:

- Introduce one stable retained event schema for BlindTag operations.
- Persist retained records append-only into `.blindtag/generated/reporting/operations.jsonl`.
- Enforce path containment so retained logs and derived exports never escape the declared reporting root unless explicitly authorized in a future pass.
- Persist `request_id` on API-owned records and preserve enough operation detail to make downstream filtering/export useful.

Minimum stable event fields for Pass J:

- `recorded_at`
- `event_id`
- `request_id` (nullable only for non-request surfaces)
- `surface` (`api`, `cli`, `library`)
- `operation` (`encode`, `decode`, `strip`, `log_query`, `log_export`, etc.)
- `severity`
- `decision` / `outcome`
- `anchor_length`
- `payload_length`
- `resolved_token_count` (when applicable)
- `error_type` (nullable)
- `detail` / `reason`

Bounded first-pass rule:

- API encode/decode operations are mandatory retained events.
- CLI operations may emit retained events once bootstrap exists, but Pass J must not delay the API-first reporting contract waiting on a broader CLI telemetry ambition.

##### Lane J-C — Read-only query surface and controlled export surface

Required behavior:

- Add a read-only query endpoint for retained events.
- Add a controlled export endpoint for reporting artifacts.
- Keep the first pass narrow: no mutation of retained events, no purge/reset API, no admin console.

Preferred first-pass shape:

- `GET /v1/log`
  - filters: `request_id`, `operation`, `level`, `limit`
  - response is machine-readable and query-safe
- `POST /v1/log/export`
  - export formats: `json`, `markdown` only in Pass J
  - server chooses the output filename and writes only under `.blindtag/generated/reporting/exports/`
  - response includes decision, artifact family, verification status, and next review path

##### Lane J-D — Export artifact integrity and signed-call behavior

Required behavior:

- Every export operation emits a verifiable artifact family, not just a bare payload file.
- Export artifact family for Pass J:
  - exported payload (`.json` or `.md`)
  - `manifest.json`
  - `checksums.json`
  - checksum sidecars where emitted by the implementation lane
- If signing is configured, JSON export artifacts and privileged export requests must be signature-verified and fail closed on ambiguity.
- If signing is absent, the lane must record that in names-only form and continue with checksum/manifest verification only.

Trust split for Pass J:

- `GET /v1/log` remains a local read-only query surface and does not require a privileged signed request.
- `POST /v1/log/export` is the trust-bearing surface; when signing is configured it must require a privileged request packet plus detached signature in a Calamum-style names-only contract (`requester_id`, freshness window, scope, format, signature verification result).

#### J.5 — Calamum validation contract

Pass J must validate through Calamum-owned evidence, not informal local confidence.

Required catalog evolution:

- add a dedicated `blindtag-reporting` definition to `catalog/test_definitions.json`
- keep `evidence_requirements: ["stdout_capture", "stderr_capture", "report_json"]`
- preserve `blindtag-all` as the release-gate rollup

Required validation sequence:

1. **Focused reporting gate**
    - targeted pytest file for reporting/bootstrap/export behavior
2. **Adjacent API gate**
    - rerun API tests covering request id continuity plus new `/v1/log` / export endpoints
3. **Adjacent CLI gate**
    - rerun CLI tests for global logging bootstrap/flag behavior if CLI surfaces changed
4. **Full project gate**
    - `calamum test run blindtag-all --project <blindtag-root>` must return `decision: go`
5. **Evidence verification gate**
    - verify `report_json`, `report_md`, `manifest_json`, `checksums_json`, checksum sidecars, and signed JSON artifacts where configured

#### J.6 — Calamum security and Polymath alignment contract

##### Calamum security alignment

Pass J must preserve and extend the existing BlindTag/Calamum evidence posture:

- manifest/checksum verification is mandatory for retained validation artifacts;
- signed JSON verification is mandatory when signing is configured;
- names-only reporting is mandatory when signing is absent;
- export calls fail closed on invalid, expired, or unverifiable privileged request material;
- no trust-bearing export is treated as successful until its artifact family verifies after write.

##### Polymath security alignment

Reference: `docs/guides/POLYMATH_SECURITY_MEASURES_AND_EXPECTATIONS.md`

Pass J must preserve:

- names-only evidence;
- fail-closed trust ambiguity;
- no import-time secret or handler surprises;
- explicit operator authority for sensitive export behavior;
- verifiable retained evidence;
- path containment to BlindTag-local generated roots.

##### Polymath user-facing alignment

Reference: `docs/guides/POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md`

Pass J human-facing/API-facing surfaces must answer:

1. what query/export ran,
2. what happened,
3. why it happened,
4. what should happen next,
5. where the evidence lives.

Human-readable summaries may exist on stderr or report surfaces, but machine-readable outputs must remain stable and parseable.

#### J.7 — Deliverables and execution sequence

| #      | Artifact                                   | Action | Notes                                                                                 |
| ------ | ------------------------------------------ | ------ | ------------------------------------------------------------------------------------- |
| 1      | `blindtag/cli.py`                          | MODIFY | Add global logging controls and `_configure_logging()` bootstrap                      |
| 2      | `blindtag/api.py`                          | MODIFY | Persist retained API events; add query/export endpoints                               |
| 3      | `blindtag/core.py`                         | MODIFY | Add quiet module logger reservation only                                              |
| 4      | `blindtag/reporting.py`                    | ADD    | Centralize event schema, JSONL append/read, export helpers, and verification plumbing |
| 5      | `.gitignore`                               | MODIFY | Keep `.blindtag/generated/` local-only                                                |
| 6      | `tests/test_reporting.py`                  | ADD    | Reporting schema/store/query/export coverage                                          |
| 7      | `tests/test_api.py`                        | MODIFY | Add `/v1/log` and export endpoint coverage                                            |
| 8      | `tests/test_cli.py`                        | MODIFY | Add global log-level / bootstrap flag coverage as needed                              |
| 9      | `catalog/test_definitions.json`            | MODIFY | Add `blindtag-reporting` lane and update notes                                        |
| 10     | `README.md` / `CHANGELOG.md`               | MODIFY | Document shipped reporting surface only after validation passes                       |
| Gate A | `blindtag-reporting` targeted Calamum lane | RUN    | Must pass before adjacent/full reruns                                                 |
| Gate B | adjacent API / CLI reruns                  | RUN    | Required if those surfaces changed                                                    |
| Gate C | `blindtag-all`                             | RUN    | Must return `decision: go`                                                            |
| Gate D | evidence integrity verification            | RUN    | Verify checksums/manifest family and signatures where configured                      |

#### J.8 — Acceptance criteria

Pass J is complete only when all of the following are true:

1. `blindtag` exposes the planned global logging bootstrap controls without attaching handlers at import time.
2. API encode/decode operations produce retained structured events in the declared local reporting root.
3. `GET /v1/log` returns stable machine-readable filtered results.
4. `POST /v1/log/export` writes only under the controlled export root and returns a verifiable artifact family.
5. Export requests fail closed on invalid/missing privileged trust material when signing is configured.
6. Reporting/export pytest coverage exists and is represented in the Calamum catalog.
7. `blindtag-all` passes with retained evidence verified via checksums, and via signatures where configured.
8. Docs describe the shipped surface truthfully without overstating remote auth, storage scale, or signed-state guarantees.

#### J.9 — Final judgment for this planning pass

Pass J is now **planning-complete, bounded, and execution-ready**.

The locked shape is:

- **bootstrap first** (`_configure_logging`, named loggers, quiet imports),
- **JSONL retained authority second**,
- **read-only query + controlled export third**,
- **Calamum evidence/security verification throughout**.

This plan is intentionally mature but narrow: it gives BlindTag the first real reporting substrate without turning the project into a broader observability platform in the same pass.

#### J.10 — Final implementation readiness and governance alignment assessment

**Assessment date:** 2026-05-31  
**Assessment scope:** readiness to execute Pass J exactly as locked above; not a claim that Pass J is already implemented or validation-cleared.

##### Verdict summary

- **Implementation readiness:** **YES** — Pass J is sufficiently bounded, sequenced, and evidenced to execute without additional planning expansion.
- **Governance alignment:** **YES** — the locked plan aligns with BlindTag local instructions, Calamum evidence/security expectations, and the parent Polymath security/style guides.
- **Closeout readiness:** **NO** — Pass J remains open until the retained-event substrate, query/export surface, tests, Calamum receipts, and evidence verification all exist in shipped code.

##### Why the implementation lane is ready

1. **The implementation order is now deterministic.**
    - Bootstrap -> JSONL retained authority -> read-only query/export -> validation/evidence verification is a complete execution ladder with no unresolved architecture branch point left inside the pass.
2. **The storage decision is bounded.**
    - The plan chose a single append-only JSONL authority for the first pass, removing the biggest scope-drift risk from the reporting lane.
3. **Trust handling is specific instead of vague.**
    - Read-only query remains local and non-privileged; controlled export is the only trust-bearing surface and must fail closed when signing is configured.
4. **Validation is already shaped around existing project precedent.**
    - The lane uses the same Calamum-first model already established elsewhere in BlindTag: focused lane -> adjacent reruns -> `blindtag-all` -> manifest/checksum/signature verification where configured.
5. **The doc now answers the main execution questions up front.**
    - what will be changed,
    - in what order,
    - under what evidence contract,
    - and what counts as completion.

##### Governance alignment assessment

| Governance surface                                               | Verdict | Evidence basis                                                                                                                                                 |
| ---------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `projects/blindtag/AGENT_INSTRUCTIONS.md` scope/minimalism rules | ALIGNED | Pass J stays inside API/CLI/core/tests/catalog/docs with no dependency expansion and no unrelated product-surface growth.                                      |
| BlindTag dependency policy                                       | ALIGNED | The locked plan explicitly forbids a new runtime dependency and defers SQLite/alternate backends.                                                              |
| BlindTag API stability rule                                      | ALIGNED | New reporting endpoints are deliberately scoped and documented as the explicit subject of Pass J rather than accidental surface drift.                         |
| Calamum validation precedent                                     | ALIGNED | The plan requires dedicated lane coverage, `blindtag-all`, and retained artifact verification instead of ad hoc trust.                                         |
| Calamum security / evidence posture                              | ALIGNED | Checksums/manifest verification remain mandatory; signatures are mandatory when configured; names-only reporting remains required when signing is absent.      |
| Polymath security expectations                                   | ALIGNED | The plan preserves fail-closed trust decisions, names-only evidence, path containment, and verifiable retained artifacts.                                      |
| Polymath user-facing expectations                                | ALIGNED | Query/export outputs are required to answer what ran, what happened, why, what next, and where the evidence lives while preserving machine-readable stability. |

##### Remaining blockers to final signoff

Pass J is ready to execute, but these are still intentional blockers to closure until implementation actually lands:

1. Global logging bootstrap controls are not yet present in shipped `blindtag/cli.py`.
2. `blindtag/core.py` and `blindtag/api.py` do not yet reserve module loggers.
3. No retained event ledger exists under `.blindtag/generated/reporting/`.
4. No `/v1/log` or `/v1/log/export` surface exists in shipped code.
5. No reporting-specific pytest file or `blindtag-reporting` Calamum definition exists yet.
6. No Pass J retained evidence packet exists yet for checksum/signature verification.

##### Final judgment

Pass J is **execution-ready and governance-aligned**.

Pass J is **not** implementation-complete, validation-complete, or closeout-ready until the bounded reporting surface lands in code, the reporting lane passes under Calamum, and the retained evidence family verifies under the same fail-closed rules already established elsewhere in BlindTag.

#### J.11 — Implementation receipt and validation closeout

**Execution date:** 2026-05-31

Pass J is now **implemented and validation-complete**.

Delivered surfaces:

1. `blindtag/reporting.py` added as the JSONL-first retained reporting authority.
2. `blindtag/api.py` now persists retained API operation records and exposes `GET /v1/log` plus `POST /v1/log/export`.
3. `blindtag/cli.py` now ships the planned global `--log-level` / `--verbose` bootstrap hook.
4. `blindtag/core.py` now reserves a quiet module logger without import-time handler attachment.
5. `tests/test_reporting.py` added focused retained-store / export / signing coverage.
6. `tests/test_api.py` and `tests/test_cli.py` extended for the reporting lane and logging bootstrap.
7. `catalog/test_definitions.json` now includes `blindtag-reporting`.

Validation evidence:

- Focused reporting gate: `20260531T230143Z-blindtag-reporting` — `decision: go`
- Adjacent API gate: `20260531T230200Z-blindtag-api` — `decision: go`
- Adjacent CLI gate: `20260531T230620Z-blindtag-cli` — `decision: go`
- Full project gate: `20260531T230637Z-blindtag-all` — `decision: go`

Integrity posture observed in retained evidence:

- Calamum emitted the expected report / manifest / checksums artifact family for each gate.
- The first focused reporting attempt (`20260531T230059Z-blindtag-reporting`) failed on post-write signature verification drift; the implementation was corrected so signature sidecars are written only after manifest/checksum content reaches final form.
- The corrected reporting rerun verified cleanly under the same checksum-first retained evidence posture.

Final implementation judgment for Pass J:

- **Implementation status:** COMPLETE
- **Validation status:** COMPLETE
- **Governance status:** ALIGNED
- **Closeout status:** READY

### Pass R — Proposed: Logging/reporting security hardening and forensic mode

**Proposal posture:** Pass J delivered a bounded operational reporting substrate. It is sufficient for local retained evidence, controlled export, and first-pass integrity verification. It is **not yet sufficient** as the security/reporting backbone for a downstream project that will transport and unpack executable payloads, where malappropriation, replay, tampering, and provenance disputes become first-class risks.

This proposal defines the next bounded hardening lane needed before BlindTag's reporting substrate should be treated as top-tier security or forensic authority for executable-payload workflows.

#### R.1 — Security gap analysis after Pass J

Pass J left these deliberate gaps open:

1. **Operational integrity exists, but tamper-evident ledger authority does not.**
    - `operations.jsonl` is append-only by contract, but a later local edit can still rewrite history without a built-in record-chain proof.
2. **Shared-key export auth is acceptable for local trust gates, but weak for independent forensic verification.**
    - HMAC-based request and artifact verification is not the same as independently verifiable public-key signing with revocation and verifier separation.
3. **Provenance depth is still thin.**
    - Current records capture request correlation and operation outcome, but not a full chain-of-custody model for payload source, classification, unpack target, policy mode, or derived executable lineage.
4. **No deny-by-default executable workflow policy exists yet.**
    - Pass J does not define how reporting/security should behave when the protected subject is an executable payload or an unpacked executable artifact.
5. **No forensic/export mode split exists yet.**
    - Current `/v1/log` and `/v1/log/export` are bounded operational surfaces, not a top-tier incident-review or forensic review surface.
6. **No quarantine / blocked-action evidence lane exists yet.**
    - A high-risk workflow needs authoritative recording not only of successful actions, but also denied, quarantined, replayed, or policy-blocked actions.

#### R.2 — Proposal judgment

**Recommendation:** BlindTag should not rely on Pass J alone for downstream executable-payload transport/unpack projects.

Before that next project uses BlindTag as a transport + unpack substrate, BlindTag should land a follow-on hardening lane with:

- explicit policy modes,
- richer provenance capture,
- tamper-evident retained records,
- deny-by-default executable handling,
- stronger signature posture for shared verification,
- and a dedicated Calamum adversarial validation contract.

#### R.3 — Locked proposal recommendations

1. **Introduce explicit top-level reporting/security modes.**
    - Recommended family:
      - `operational` — current Pass J-style local reporting posture.
      - `security` — stricter signed-call, classification, and deny-by-default posture for sensitive payload workflows.
      - `forensic` — security mode plus tamper-evident record chaining, deeper provenance, and incident-review export bundles.
    - These modes should be explicit in requests/configuration and persisted into retained records. No ambient hidden fallback should silently escalate or de-escalate policy posture.
2. **Treat executable transport/unpack as a deny-by-default policy class.**
    - If a future project wants BlindTag-backed transport or unpack of executable payloads, that action class should require explicit signed authority and a scope that names the action family.
    - Absent that authority, the action should be blocked, recorded, and exported as a names-only denied-action event.
3. **Make provenance a first-class schema layer, not an optional note field.**
    - Minimum proposed provenance fields for high-risk modes:
      - `policy_mode`
      - `subject_kind` (`text_payload`, `binary_payload`, `archive_payload`, `executable_payload`, `unpacked_executable`)
      - `source_artifact_sha256`
      - `derived_artifact_sha256` (nullable)
      - `parent_event_id`
      - `request_id`
      - `requester_id`
      - `key_id`
      - `scope`
      - `action_phase` (`received`, `verified`, `exported`, `blocked`, `quarantined`, `unpacked`, `released`)
      - `tool_version`
      - `session_id` / `host_context` (names-only)
4. **Add tamper-evident retained ledger chaining.**
    - Each retained record in `security` / `forensic` mode should carry a hash-chain link to the previous retained record in that ledger family.
    - Segment sealing should produce a signed summary for bounded ledger slices so later export can prove continuity and omission resistance.
5. **Prefer public-key artifact verification for shared forensic workflows.**
    - Shared-key HMAC may remain a local-dev fallback.
    - For top-tier security / forensic mode, the preferred posture should align with Calamum-style detached signature verification and names-only key reporting.
    - Any new crypto dependency required for that posture remains an explicit approval gate under BlindTag dependency policy.
6. **Split operational query from high-trust forensic export.**
    - `GET /v1/log` should remain the low-friction operational read surface.
    - High-trust forensic export should become a stricter surface with signed authority, richer bundle contents, and no ambiguity about review context.
7. **Record blocked, replayed, expired, and tamper-detected attempts as first-class evidence.**
    - For a security-grade reporting layer, denials are not noise; they are part of the authoritative incident narrative.

#### R.4 — Recommended forensic mode semantics

| Mode          | Intended use                                                   | Trust posture                                                     | Evidence depth                                                | Default executable policy                                |
| ------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------- |
| `operational` | Local troubleshooting and ordinary API review                  | Current Pass J baseline                                           | bounded event rows + export family                            | not an authority lane                                    |
| `security`    | Sensitive payload handling and controlled downstream transport | signed authority for privileged actions, fail closed on ambiguity | richer provenance + denied-action evidence                    | deny by default unless explicitly authorized             |
| `forensic`    | Incident review, disputed actions, chain-of-custody exports    | strongest available signing + verifier-friendly artifact family   | hash chain + provenance packet + segment seal + signed bundle | deny by default and preserve denied attempts as evidence |

#### R.5 — Proposed implementation lanes

##### Lane R-A — Policy mode and authority envelope

Required planning direction:

- define one stable `policy_mode` field for every trust-bearing event/export;
- define scope families for sensitive actions such as transport, unpack, release, and forensic export;
- define allowlist / key-id / freshness / expiry rules for those actions;
- define the names-only operator-facing denial packet for unsupported or unauthorized executable workflows.

##### Lane R-B — Provenance schema uplift

Required planning direction:

- add first-class provenance fields for source artifact digest, derived digest, parent lineage, requester identity, signing key id, scope, phase, and subject classification;
- require these fields for `security` / `forensic` records even when some are null-by-contract;
- distinguish the original BlindTag transport artifact from later unpacked/extracted executable artifacts.

##### Lane R-C — Tamper-evident ledger and segment sealing

Required planning direction:

- chain high-trust records with `previous_record_hash` and `record_hash` fields;
- introduce bounded sealed segments or checkpoints so later exports can prove continuity without requiring the entire ledger;
- fail closed when continuity proofs or seal verification fail.

##### Lane R-D — Forensic bundle export and quarantine evidence

Required planning direction:

- add a forensic bundle family that includes:
  - filtered record payload,
  - manifest,
  - checksums,
  - signature sidecars,
  - provenance summary,
  - chain/seal verification summary,
  - denied/quarantined action summary where applicable;
- keep bundle outputs path-contained and local-only by default;
- define a quarantine-root contract for blocked or suspicious executable-related events.

##### Lane R-E — Adversarial validation and Calamum security lane

Required planning direction:

- add a focused hardening lane (for example `blindtag-reporting-security` or `blindtag-forensic`) to the Calamum catalog;
- add a sandbox-simulated elevated-provenance validation lane for `security` / `forensic` mode behavior;
- require those sandbox tests to evaluate and validate generated program output content, not just command success or process survival;
- require those sandbox tests to verify handoff-completion posture explicitly (complete, blocked, quarantined, incomplete) so the high-trust provenance path cannot clear on upgraded smoke tests alone;
- validate representative adversarial cases:
  - modified ledger row,
  - broken hash chain,
  - missing segment seal,
  - expired signed request,
  - unknown key id,
  - replayed privileged request,
  - unsupported executable action scope,
  - unauthorized unpack attempt,
  - path escape attempt,
  - checksum/signature mismatch after export.

#### R.6 — Calamum and Polymath alignment contract

##### Calamum test alignment

The hardening pass should preserve the existing BlindTag validation shape:

1. focused hardening/security lane;
2. adjacent API rerun for mode negotiation + deny behavior + provenance contracts;
3. adjacent CLI rerun if operator-facing mode/export surfaces change;
4. full `blindtag-all` gate;
5. retained evidence verification gate for checksums, signatures, and forensic chain proof artifacts;
6. sandbox-simulated elevated-provenance lane that validates output content and handoff-completion posture rather than merely proving that the process ran.

##### Calamum security alignment

The hardening pass should explicitly inherit these Calamum-style expectations:

- names-only reporting of signing configuration and verification state;
- fail-closed behavior on invalid, expired, replayed, revoked, or unverifiable trust material;
- manifest/checksum/signature verification after write;
- local-only generated evidence roots unless explicitly exported.

##### Polymath alignment

The hardening pass should preserve:

- names-only evidence,
- environment-based secret injection,
- explicit authorization for sensitive state changes,
- path containment,
- calm human-facing security messages that explain what failed, why, what next, and where evidence lives.

#### R.7 — Gaps that should be closed before executable-payload use

Before BlindTag is reused by the next project for transport + unpack of executable payloads, ORACL recommends closing these gaps:

1. **Move beyond operational-only event schema.**
2. **Replace or supplement shared-key-only trust with verifier-friendly public-key signing for high-trust bundles.**
3. **Add deny/quarantine evidence for executable actions.**
4. **Add chain-of-custody provenance fields for derived artifacts.**
5. **Add tamper-evident record chaining and segment sealing.**
6. **Add adversarial Calamum coverage specifically for security / forensic paths.**

#### R.8 — Acceptance criteria for the future hardening pass

The hardening pass should not be considered complete until all of the following are true:

1. `policy_mode` is explicit, persisted, and tested.
2. Executable transport/unpack actions are deny-by-default unless explicitly authorized by signed scope.
3. `security` / `forensic` records carry the required provenance fields.
4. Tampering with retained records, chain links, seals, or exported artifacts is detected and fails closed.
5. Forensic bundle exports are independently verifiable through manifest/checksum/signature materials.
6. Human-facing security output stays names-only, calm, and actionable.
7. Focused Calamum hardening lanes and `blindtag-all` both return `decision: go`.
8. Sandbox-simulated `security` / `forensic` tests verify exported output content and the final handoff-completion posture, and they fail closed on mismatched or incomplete simulated handoff state.

#### R.9 — Final proposal judgment

This proposal is **aligned** with BlindTag local rules, Calamum evidence/security posture, and Polymath security expectations.

It is also ORACL's recommendation that **Pass R (or an equivalent hardening lane) be treated as a prerequisite before BlindTag becomes the logging/reporting substrate for any downstream executable-payload transport/unpack project.**

#### R.10 — Final implementation readiness and governance alignment assessment

**Assessment date:** 2026-05-31  
**Assessment scope:** readiness to execute Pass R exactly as bounded above; not a claim that the security / forensic hardening substrate is already implemented or validation-cleared.

##### Verdict summary

- **Implementation readiness:** **YES** — Pass R is sufficiently bounded, threat-anchored, and sequenced to execute without another broad planning pass.
- **Governance alignment:** **YES** — the locked hardening direction aligns with BlindTag local instructions, Calamum evidence/security expectations, and the parent Polymath security/style guides.
- **Closeout readiness:** **NO** — Pass R remains open until the hardened security / forensic substrate, adversarial validation lanes, and retained evidence verification all exist in shipped code.

##### Why the implementation lane is ready

1. **The threat driver is explicit and legitimate.**
    - The pass is not speculative hardening for its own sake; it is directly tied to the stated downstream executable-payload transport/unpack risk.
2. **The mode model is now bounded.**
    - `operational`, `security`, and `forensic` provide a concrete posture ladder instead of an undefined "more secure later" promise.
3. **The key hardening requirements are specific and testable.**
    - deny-by-default executable handling,
    - provenance uplift,
    - tamper-evident chaining,
    - stronger verifier-friendly signing,
    - and dedicated adversarial Calamum coverage are all stated as concrete deliverables rather than general aspirations.
4. **The validation contract is complete.**
    - focused hardening lane -> adjacent reruns -> `blindtag-all` -> retained evidence verification is the same mature execution shape already used elsewhere in BlindTag.
5. **The remaining approval boundary is explicit instead of hidden.**
    - The proposal already records that any new crypto/runtime dependency required for verifier-friendly public-key signing remains an explicit operator approval gate under BlindTag dependency policy. That is an execution checkpoint, not uncontrolled scope drift.

##### Governance alignment assessment

| Governance surface                                               | Verdict | Evidence basis                                                                                                                                                       |
| ---------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `projects/blindtag/AGENT_INSTRUCTIONS.md` scope/minimalism rules | ALIGNED | Pass R stays focused on reporting/security hardening, preserves API/codec stability expectations, and does not normalize broad architectural sprawl.                 |
| BlindTag dependency policy                                       | ALIGNED | The proposal prefers stronger verifier-friendly signing but explicitly preserves the operator approval gate for any new runtime crypto dependency.                   |
| Pass J continuity / project precedent                            | ALIGNED | Pass R is framed as a follow-on hardening layer on top of the shipped Pass J substrate rather than a rewrite or repudiation of the retained-reporting baseline.      |
| Calamum validation discipline                                    | ALIGNED | The proposal requires a dedicated hardening lane, adjacent reruns where needed, full `blindtag-all`, and retained artifact verification.                             |
| Calamum security / evidence posture                              | ALIGNED | The proposal preserves names-only signing-state reporting, fail-closed trust handling, and manifest/checksum/signature verification after write.                     |
| Polymath security expectations                                   | ALIGNED | The proposal centers explicit authorization, names-only evidence, path containment, fail-closed ambiguity handling, and verifiable retained artifacts.               |
| Polymath user-facing expectations                                | ALIGNED | The proposed forensic/security outputs remain required to explain what failed, why, what happens next, and where the evidence lives without leaking secret material. |

##### Remaining blockers to final signoff

Pass R is ready to execute, but these remain intentional blockers to closure until the work actually lands:

1. `security` / `forensic` policy modes do not yet exist in shipped BlindTag code.
2. Executable transport/unpack deny-by-default scope enforcement is not yet implemented.
3. Tamper-evident ledger chaining and segment sealing do not yet exist.
4. Provenance-grade retained fields for derived executable artifacts do not yet exist.
5. High-trust forensic export bundles and quarantine/denied-action evidence packets do not yet exist.
6. Focused Calamum adversarial coverage for the hardening lane does not yet exist.
7. Any stronger public-key verification path beyond the current shared-key posture remains unimplemented and, if it requires a new dependency, still operator-gated.
8. No sandbox-simulated elevated-provenance test lane exists yet to validate output content and handoff-completion posture for the high-trust modes.

##### Final judgment

Pass R is **execution-ready and governance-aligned**.

Pass R is **not** implementation-complete, validation-complete, or closeout-ready until the hardened security / forensic substrate lands in code, the adversarial Calamum lane passes, and the retained evidence family verifies under the stricter fail-closed trust rules defined above.

#### R.11 — Implementation receipt and validation closeout

**Execution date:** 2026-05-31

Pass R is now **implemented and validation-complete**.

Delivered surfaces:

1. `blindtag/reporting.py` now ships explicit `operational`, `security`, and `forensic` modes with provenance-grade retained fields.
2. Elevated provenance records now enforce deny-by-default executable scope rules, tamper-evident `previous_record_hash` / `record_hash` chaining, and per-segment seals under `.blindtag/generated/reporting/seals/`.
3. High-trust export now supports verifier-friendly Ed25519 request verification and artifact signing for `security` / `forensic` bundles while preserving the existing shared-key operational export lane.
4. Forensic export bundles now include provenance summaries, chain verification, segment-seal summaries, and sandbox-simulated handoff assessment packets that validate output content and final handoff-completion posture.
5. `blindtag/api.py` now supports `policy_mode` / `action_phase` filters on reporting queries and export requests so the elevated provenance lane is reachable through the public localhost transport surface.
6. `tests/test_reporting.py` and `tests/test_api.py` now cover elevated provenance modes, chain tamper detection, deny-by-default executable handling, and sandbox-simulated handoff verification.
7. `catalog/test_definitions.json` now includes the dedicated `blindtag-forensic` Calamum lane.

Validation evidence:

- Focused sandbox / forensic gate: `20260531T233221Z-blindtag-forensic` — `decision: go`
- Adjacent reporting gate: `20260531T233239Z-blindtag-reporting` — `decision: go`
- Adjacent API gate: `20260531T233256Z-blindtag-api` — `decision: go`
- Full project gate: `20260531T233314Z-blindtag-all` — `decision: go`

Integrity posture observed in retained evidence:

- Calamum emitted the expected report / manifest / checksums artifact family for each validation gate.
- The dedicated sandbox-simulated lane verified elevated-mode output content and handoff-completion posture rather than relying on smoke-style process success alone.
- The full gate passed after the hardened reporting/export substrate landed without reopening widget, CLI, or core-code regressions.

Final implementation judgment for Pass R:

- **Implementation status:** COMPLETE
- **Validation status:** COMPLETE
- **Governance status:** ALIGNED
- **Closeout status:** READY

### Pass S — Proposed: Pre-package security audit

**Proposal posture:** BlindTag now has a stronger retained-evidence and elevated-provenance substrate, but package readiness should not rely on feature validation alone. Before packaging/public release, BlindTag should complete one explicit **pre-package security audit** that reviews shipped behavior, generated outputs, retained evidence, package contents, and operator-facing trust surfaces as a single release-hygiene lane.

This is an audit pass, not a feature-growth pass. The goal is to prove that the codebase, local generated state, security messaging, package artifacts, and trust-bearing outputs are ready for publication without hidden drift.

#### S.1 — Audit objective

The pre-package security audit should answer five questions:

1. **Does BlindTag fail closed where trust should fail closed?**
2. **Do retained outputs, export bundles, and elevated-provenance artifacts prove what they claim to prove?**
3. **Do package artifacts exclude local-only state, signing material, and machine-local overlays?**
4. **Do human-facing security surfaces explain failures clearly without leaking secrets or overclaiming success?**
5. **Does the shipped package behave the same way under audit as the source tree claims it does?**

#### S.2 — Audit scope

This audit pass should cover:

- `blindtag/core.py`
- `blindtag/api.py`
- `blindtag/reporting.py`
- `blindtag/cli.py`
- `blindtag/widget.py`
- package metadata and artifact-generation surfaces (`pyproject.toml`, `MANIFEST.in`, wheel/sdist outputs)
- local-only generated-state routing (`.blindtag/`, `.calamum/`, `report_tmp/`, `.env`, signing material)
- security documentation truthfulness (`README.md`, `SECURITY.md`, package metadata text)

#### S.3 — Required audit tactics

The audit must use multiple complementary tactics rather than one shallow sweep.

##### Lane S-A — Deep code-review audit

Required method:

- perform line-level source review of trust-bearing modules and launch surfaces;
- inspect failure paths, not just success paths;
- trace where secrets, signing material, local paths, retained evidence, and operator-facing messages enter and leave the system;
- verify that localhost-only assumptions, deny-by-default paths, and path containment are implemented consistently rather than described aspirationally.

Minimum review targets:

- request verification and export verification flows;
- retained evidence generation and post-write verification;
- package-entry launch surfaces;
- clipboard / widget surfaces for silent data escape risk;
- any path that could overclaim completion or under-report denial/quarantine states.

##### Lane S-B — Sandbox content-based review

Required method:

- run sandbox-simulated reviews for elevated provenance / handoff paths;
- inspect generated program output content, not just exit codes or whether the process survived;
- verify that the final handoff posture is correctly classified as `complete`, `blocked`, `quarantined`, or `incomplete`;
- verify that exported forensic/security bundles contain the provenance, chain, seal, and handoff evidence they claim to contain.

Minimum sandbox review targets:

- successful elevated handoff;
- blocked executable handoff;
- quarantined executable handoff;
- incomplete / malformed provenance sequence;
- tampered chain or seal state;
- mismatched exported content vs manifest/checksum/signature claims.

##### Lane S-C — Diagnostic script audit

Required method:

- use bounded local diagnostic scripts for questions that are awkward to settle by inspection alone;
- keep scripts local-only and review-oriented;
- scripts may inspect package contents, verify artifact families, enumerate retained outputs, simulate path-containment escape attempts, and compare manifest claims to real files.

Preferred diagnostic-script targets:

- wheel/sdist contents vs expected publishable files;
- local-only exclusion audit (`.env`, `.blindtag`, `.calamum`, signing material, report_tmp);
- checksum/signature/sidecar consistency audit;
- generated-bundle completeness audit;
- help/output truthfulness audit for CLI and API-facing surfaces;
- package metadata rendering and classifier sanity.

##### Lane S-D — Dependency and artifact review

Required method:

- inspect runtime dependencies for scope fit and release necessity;
- verify that cryptography/signing dependencies are documented and intentional;
- build publication artifacts and inspect them before any publish step;
- confirm package metadata, entry points, and included files match the documented product surface.

Minimum artifact checks:

- wheel/sdist build succeeds;
- rendered metadata is valid;
- no local state or secret-bearing files are included;
- no retained evidence roots are accidentally included;
- widget / CLI / API entry points are represented correctly.

##### Lane S-E — Operator-surface security messaging audit

Required method:

- review human-facing no-go / warning / denial packets for secret safety and clarity;
- verify that security failures explain what failed, why, what next, and where evidence lives;
- confirm that operator-facing success messages do not overstate completion when trust verification or handoff posture is incomplete.

Minimum messaging targets:

- export denial paths;
- elevated provenance failures;
- package/build/audit failures;
- CLI help and launcher-facing summaries;
- any publish-readiness verdict or package-readiness verdict.

##### Lane S-F — Final adversarial lane

Required method:

- run one explicit adversarial closeout lane at the **end** of the pre-package audit after the ordinary audit slices, reruns, and package-artifact inspection have already passed;
- treat this as an aggressive hostile-input / hostile-state challenge pass, not as a light smoke rerun;
- use the adversarial lane to attack the exact trust-bearing claims BlindTag is preparing to ship: retained evidence truthfulness, export verification, path containment, denial/quarantine posture, and package-content boundaries;
- record the adversarial findings as first-class retained evidence rather than folding them into casual notes.

Execution posture:

- this lane runs **last**;
- this lane runs **aggressively**;
- this lane is intended to break assumptions that earlier slices may have only confirmed under cooperative conditions.

Minimum adversarial targets:

- malformed or contradictory provenance packets;
- replayed, expired, or mismatched signed/high-trust request material;
- forged or edited retained ledger rows;
- tampered manifest/checksum/signature families;
- path-escape attempts against reporting/export/package-review roots;
- package-content surprises such as local-only overlays or generated-state leakage;
- operator-surface cases that falsely imply success after denial, quarantine, or incomplete handoff.

#### S.4 — Calamum and audit-ladder contract

The pre-package security audit should validate through a layered ladder rather than one monolithic run.

1. **Focused security-audit slice**
    - deep code-review findings captured and converted into concrete audit checks.
2. **Sandbox content-validation slice**
    - elevated provenance output content and handoff posture verified under simulated conditions.
3. **Diagnostic-script slice**
    - package/artifact/local-state assertions checked through bounded local review scripts.
4. **Adjacent validation reruns**
    - rerun affected Calamum definitions where the audit touches trust-bearing surfaces.
5. **Full `blindtag-all` gate**
    - confirm the package still passes the standard release-gate baseline.
6. **Artifact verification gate**
    - verify report / manifest / checksum / signature materials after the audit run.
7. **Package artifact inspection gate**
    - inspect wheel/sdist outputs before any publish decision.
8. **Final adversarial gate**
   - run the aggressive hostile-input / hostile-state lane last, after the cooperative audit slices are already green, and require retained evidence for its results.

#### S.5 — Audit checklist

The audit should not be considered complete until all of the following are explicitly checked:

1. No secret values, local overlays, `.env`, or signing material are included in package artifacts.
2. Local-only generated roots remain local-only and are not accidentally publishable.
3. Retained evidence/export bundles verify after write and match actual files on disk.
4. Elevated provenance outputs contain the required provenance and handoff fields.
5. Sandbox review confirms output content and final handoff posture, not just command success.
6. Path-containment failures deny safely and do not escape declared roots.
7. Denied, quarantined, and incomplete states are represented truthfully in outputs.
8. CLI/API/widget/user-facing messages remain calm, actionable, and secret-safe.
9. Package metadata and entry points match the documented product surface.
10. The final package-readiness judgment cites retained audit evidence rather than informal confidence.
11. A final aggressive adversarial lane has been executed last, and its findings are reflected in the package-readiness judgment.

#### S.6 — Gaps this audit is meant to catch

This audit pass is specifically meant to catch the failure families that ordinary feature validation can miss:

- package includes local-only files or generated state;
- export bundles verify incompletely or drift from their manifests;
- sandbox handoff posture is mislabeled as complete;
- adversarial hostile-input behavior breaks trust claims only after the ordinary slices are green;
- operator-facing messages overclaim success;
- docs/security claims drift from shipped behavior;
- release artifacts contain unexpected files or missing entry points;
- path-containment or trust-boundary assumptions hold in code comments but not in code paths.

#### S.7 — Final proposal judgment

This proposed pre-package security audit is **aligned** with BlindTag local instructions, Calamum adversarial-testing precedent, and Polymath security expectations.

It is also ORACL's recommendation that **Pass S (or an equivalent pre-package security audit lane) be completed before any public packaging or publication decision for BlindTag.**

#### S.8 — Final implementation readiness and governance alignment assessment

**Assessment date:** 2026-05-31  
**Assessment scope:** readiness to execute Pass S exactly as bounded above; not a claim that the pre-package security audit has already been executed or that package/publication clearance has been granted.

##### Verdict summary

- **Implementation readiness:** **YES** — Pass S is sufficiently bounded, sequenced, and evidence-anchored to execute without another planning expansion.
- **Governance alignment:** **YES** — the locked audit lane aligns with BlindTag local instructions, the Calamum adversarial-testing contract, and the parent Polymath security/style expectations.
- **Closeout readiness:** **NO** — Pass S remains open until the audit is actually executed, retained audit evidence is collected, the final adversarial gate runs last, and the package-readiness judgment is issued from those retained results.

##### Why the implementation lane is ready

1. **The audit objective is explicit rather than generic.**
    - Pass S now answers concrete release questions: fail-closed behavior, retained-output truthfulness, package-content hygiene, operator-surface honesty, and package-vs-source parity.
2. **The audit tactics are complementary and bounded.**
    - Deep code review, sandbox content review, diagnostic scripts, artifact/dependency inspection, operator-message review, and the final adversarial pass are each named and scoped rather than left as implied audit work.
3. **The execution order is deterministic.**
    - The audit ladder now establishes a specific sequence from cooperative review slices through artifact inspection and then into the mandatory final adversarial gate.
4. **The strongest release-risk families are directly represented.**
    - Package-content leakage, retained-evidence drift, mislabeled handoff posture, path escape, false-success messaging, and hostile-input breakage are all called out as explicit targets rather than assumed to be covered indirectly.
5. **The final adversarial requirement closes the biggest false-confidence gap.**
    - By requiring one aggressive hostile-input / hostile-state lane at the end, Pass S avoids declaring package readiness from only cooperative or nominal-path audit evidence.

##### Governance alignment assessment

| Governance surface                                               | Verdict | Evidence basis                                                                                                                                                                  |
| ---------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `projects/blindtag/AGENT_INSTRUCTIONS.md` scope/minimalism rules | ALIGNED | Pass S is documentation-first and planning-bounded, centered on audit execution rather than feature growth or unrequested architecture expansion.                               |
| BlindTag dependency policy                                       | ALIGNED | The audit plan inspects runtime dependencies and packaging surfaces but does not normalize new dependency growth as part of the audit itself.                                   |
| BlindTag package/publication boundary                            | ALIGNED | Pass S is explicitly framed as a pre-package / pre-publication gate rather than a casual optional review.                                                                       |
| Calamum adversarial-testing contract                             | ALIGNED | The plan treats adversarial testing as a first-class final gate while still routing it through the normal validation machinery rather than inventing a separate authority lane. |
| Calamum evidence / integrity posture                             | ALIGNED | The audit ladder preserves report / manifest / checksum / signature verification expectations and requires retained evidence for the final adversarial findings.                |
| Polymath security expectations                                   | ALIGNED | Pass S preserves names-only evidence, fail-closed trust posture, path containment scrutiny, and verifiable retained outputs.                                                    |
| Polymath user-facing expectations                                | ALIGNED | The audit explicitly reviews operator-facing denial/success messaging for clarity, next-step guidance, and overclaim prevention.                                                |

##### Remaining blockers to final signoff

Pass S is ready to execute, but these remain intentional blockers to closure until the audit is actually run:

1. The deep code-review audit has not yet been executed and recorded as retained audit evidence.
2. The sandbox content-based review has not yet been executed against the package-readiness lane.
3. The bounded diagnostic-script audit has not yet produced retained findings for package contents, artifact families, and local-only exclusions.
4. The dependency/artifact inspection has not yet verified the actual wheel/sdist publish surfaces.
5. The operator-surface security messaging audit has not yet been performed against the final pre-package candidate state.
6. The mandatory final adversarial lane has not yet been executed last.
7. No Pass S retained evidence packet yet exists to support a package-readiness verdict.

##### Final judgment

Pass S is **execution-ready and governance-aligned**.

Pass S is **not** audit-complete, validation-complete, or package-ready until the bounded audit lane runs end to end, the aggressive adversarial closeout gate executes last, and the package-readiness judgment is tied to retained audit evidence rather than planning confidence alone.

#### S.9 — Audit execution receipt and package-readiness verdict

**Execution date:** 2026-05-31

Pass S has now been **executed as an audit lane**. The cooperative validation slices and the final adversarial closeout gate were run, retained evidence was produced, and the package-artifact inspection was completed.

**Critical outcome:** the audit does **not** clear BlindTag for packaging/publication yet.

The audit found real package-surface blockers even though the validation gates remained green.

##### Executed evidence lanes

- Focused reporting gate: `20260531T235518Z-blindtag-reporting` — `decision: go`
- Full project gate: `20260531T235533Z-blindtag-all` — `decision: go`
- Final aggressive adversarial / forensic gate: `20260531T235604Z-blindtag-forensic` — `decision: go`

Retained artifact family confirmed for these runs:

- `report.json`
- `report.md`
- `manifest.json`
- `checksums.json`
- checksum sidecars for the retained JSON/Markdown artifacts

Package audit artifact written locally:

- `report_tmp/pass_s_package_audit.json`

##### Audit findings — passes

1. **Local-only exclusion discipline held for the built artifacts.**
    - The built wheel and sdist did **not** include `.env`, `.calamum`, `.blindtag`, or `report_tmp` content.
2. **Package build succeeded.**
    - Wheel and sdist were produced successfully under `report_tmp/pass_s_dist/`.
3. **Declared entry points are present in the wheel metadata.**
    - `blindtag`
    - `blindtag-api`
    - `blindtag-widget`
4. **The final hostile lane ran last and passed.**
    - The final retained run was the elevated provenance/adversarial definition `blindtag-forensic`, matching the locked Pass S execution order.

##### Audit findings — blockers

1. **Package assets are not present in the built wheel.**
    - The wheel contains Python modules and metadata only.
    - It does **not** include the `assets/` tree used by the README image references and by widget runtime surfaces such as image/icon loading.
    - This is a package-readiness blocker because an installed wheel is not equivalent to the source-tree behavior BlindTag documents and depends on.
2. **The built sdist also omits the asset tree.**
    - The source distribution does not currently include the BlindTag asset files either.
    - This means the packaging lane is relying on incomplete source contents for publication artifacts.
3. **`MANIFEST.in` is absent.**
    - Package inclusion is currently relying on setuptools defaults plus the generated source list rather than an explicit inclusion contract for non-Python assets.
    - Given the missing asset tree in both wheel and sdist, this absence is now an evidenced packaging-control gap rather than a harmless omission.
4. **README markup is malformed in shipped metadata.**
    - The built package metadata includes the malformed top-of-file fragment beginning with `<p` / `="center">,k.$$...`.
    - This is a publication-surface defect because the packaged long description is not cleanly rendered/truthful at the top of the shipped metadata.
5. **Build-time metadata deprecation warnings were emitted.**
    - The build emitted setuptools deprecation warnings around the TOML-table `project.license` form and license classifiers.
    - These are not the primary publication blocker today, but they are real packaging-hygiene findings that should be corrected in the package lane.

##### Package-readiness judgment

**Package readiness:** **NO**

Why this is a no-go verdict:

- the built artifacts do not yet preserve source-tree asset expectations;
- the shipped metadata is carrying malformed README markup;
- the package-content contract for non-Python assets is not explicit enough to support a trustworthy publication lane.

##### What Pass S did prove

Pass S did prove that:

- the current trust-bearing reporting and elevated-provenance code paths still validate cleanly under Calamum;
- retained evidence packets and checksum sidecars are being emitted for the fresh reporting / full-suite / forensic runs;
- local-only overlays are not leaking into the currently built wheel/sdist;
- the final hostile lane can run last without reopening the previously validated reporting/security substrate.

##### Final implementation judgment for Pass S

- **Audit execution status:** COMPLETE
- **Validation gate status:** COMPLETE
- **Governance status:** ALIGNED
- **Package readiness:** NO-GO
- **Closeout status:** OPEN — packaging/publication remains blocked pending packaging-surface remediation.

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

## Section 11 — Planned: Packaging, publication, and Windows installer lane

**Status:** LOCKED — planning/documentation lane updated on 2026-05-31.  
**Dependency:** Pass S remains the governing package-audit evidence source. Packaging/publication execution stays blocked until the Pass S blockers are remediated in code and then re-verified from built artifacts.  
**Primary checklist:** `projects/blindtag/docs/PACKAGING_AND_PUBLICATION_CHECKLIST.md`

### 11.1 — Guidance sources reviewed for this lane

This packaging/publication update is grounded in the highest-signal relevant guidance already present in the workspace:

- `projects/blindtag/docs/WIDGET_SCHEMA.md`
  - confirms widget assets must resolve relative to the installed package, not just the source tree.
- `projects/blindtag/docs/CLI_IMPLEMENTATION_CHECKLIST.md`
  - preserves the release expectation that publishable artifacts exclude `.env`, signing material, and local-only state.
- `docs/installation/SHIPPED_CODESENTINEL_OFFLINE_INSTALL_PACKAGE_20260104.md`
  - establishes deterministic shipped-install posture, checksum/manifest discipline, optional Windows `.exe` installer precedent, and operator-facing helper flow.
- `docs/installation/INSTALLATION.md`
  - confirms multiple install surfaces are acceptable when they are clearly explained and followed by verification.
- `docs/installation/README.md`
  - reinforces installer-first operator guidance for Windows GUI install surfaces.
- `docs/installation/INSTALL_PROFILES.md`
  - reinforces profile-driven installation choices rather than one opaque install path.
- `docs/architecture/general/PACKAGING_PIPELINE_DIRECTIVE.md`
  - reinforces explicit build, wheel/sdist inspection, and metadata verification before any publish decision.
- `projects/unc-data-science-notes/temp/seam_offline_bundle_1.1.5-py3-none-any.whl/howtos/docs/guides/QUICK_PUBLISH_REFERENCE.md`
  - reinforces the staged `build -> validate -> TestPyPI -> install/retest -> production PyPI` sequence.

### 11.2 — Package/publication posture carried forward from Pass S

Pass S is still authoritative for the current package-readiness verdict:

- wheel and sdist builds succeed;
- local-only overlays are not leaking into the package artifacts;
- package readiness remains **NO-GO** because the current wheel/sdist omit required asset content, the package-side asset inclusion contract is not explicit enough, and shipped metadata still carries malformed README markup.

Therefore this lane is **not** a casual publish checklist bolted on top of unresolved packaging defects. It is the locked release path that begins with package-surface remediation and ends only after rebuilt artifacts, installer behavior, and staged publication evidence all agree.

### 11.3 — Locked artifact family for the release lane

BlindTag's release lane now has two sibling deliverable surfaces:

1. **Python publication surface**
    - source distribution (`sdist`)
    - wheel (`whl`)
    - verified package metadata
    - staged TestPyPI validation before any production PyPI upload

2. **Windows widget install surface**
    - a Windows `.exe` installer for widget-oriented usage
    - installer-owned presentation for install choices
    - sandbox install validation on the built installer artifact before any release closeout

Where practical, the Windows installer lane should also emit operator-facing integrity/support artifacts in the same spirit as the shipped-install precedent:

- installer build identifier/version
- artifact checksums
- manifest of included release artifacts
- short install/readback notes pointing the operator to the packaged README

### 11.4 — Locked Windows installer experience contract

The Windows installer is now a required planning/output surface for BlindTag's widget-based operations.

#### Installer positioning

- The installer must gently steer mainstream users toward the ordinary/safe path without sounding patronizing.
- The default option should be presented as the most natural choice for recreational/everyday use.
- The advanced option should remain available, but the copy should make clear that it is for users who specifically need custom install behavior.

#### Required top-level install choices

The installer must offer two primary install modes:

1. **Default (Recommended)**
    - presentation goal: subtly preferred and easiest to choose
    - intended audience: recreational/everyday BlindTag usage
    - expected behavior: install the normal widget/CLI surface with the standard release assets and no unnecessary decision burden

2. **Advanced**
    - presentation goal: available but visually and textually secondary to Default
    - required warning language: this mode is for custom setup decisions and should be used only when the operator specifically needs non-default behavior
    - expected scope: custom path/surface/options selection, without implying that ordinary users should start here

#### Required installer options

The installer must explicitly offer these options:

- `Create shortcut`
- `Enable quick launch`
- `Display README.md after install`

These options must be treated as first-class install choices, not buried post-install surprises.

#### Minimum Default-mode behavior

Default mode should, at minimum:

- install the normal BlindTag package surface;
- install the widget launch surface expected for terminal-free use;
- include the runtime asset set required by the widget and packaged documentation references;
- verify the bundled BlindTag payload against installer-owned integrity hashes before installation and fail closed on mismatch;
- automatically satisfy prerequisite/runtime dependencies that ordinary Windows users should not be asked to manage manually, including Python installation when Python is absent;
- trust-check downloaded Python bootstrap installers before execution;
- own any required elevation handoff so the operator burden stays near `click OK` instead of `open a terminal and do setup work`;
- make the ordinary post-install launch path obvious;
- preserve a calm, low-friction install flow.

#### Minimum Advanced-mode behavior

Advanced mode may expose:

- install-location control;
- shortcut/quick-launch toggles;
- optional post-install launch behavior;
- optional documentation display behavior;
- any future packaging-profile switches needed for custom/operator scenarios.

Advanced mode must **not** become an excuse to leave Default underspecified or misleading.

### 11.5 — Locked execution ladder for packaging/publication

This is the required release order for BlindTag once code remediation begins:

1. **Remediate Pass S package blockers**
    - restore asset inclusion in wheel/sdist;
    - make package inclusion rules explicit;
    - fix malformed README packaging metadata;
    - clear packaging-hygiene warnings that materially affect publication trust.

2. **Rebuild and inspect publication artifacts**
    - build `sdist` and `wheel`;
    - inspect artifact contents, metadata, and entry points;
    - confirm widget/runtime assets are present in the shipped artifacts;
    - confirm local-only/generated roots remain excluded.

3. **Build the Windows installer artifact**
    - produce the `.exe` installer for widget-based operations;
    - verify that installer content matches the packaged product surface rather than a source-tree-only layout;
    - verify bundled and/or online bootstrap behavior for missing Python prerequisites remains truthful and installer-owned;
    - verify the required mode/options contract is present.

4. **Run sandbox install validation**
    - test the installer in a sandboxed/simulated environment;
    - validate output content, installed surface truthfulness, and handoff completion posture;
    - validate the missing-Python lane and any required elevation handoff;
    - emit a retained JSON + Markdown sandbox evidence packet for scenario simulation and handoff reporting;
    - verify the widget launch path, shortcuts, quick-launch behavior, and README display option behave as claimed.

5. **Run the publication staging lane**
    - run package validation checks on the final artifacts;
    - publish to TestPyPI first;
    - install from the staged publication artifact and re-run sanity checks.

6. **Production publication lane**
    - publish to production only after TestPyPI/install verification passes;
    - record release evidence, artifact identifiers, and the final publish verdict.

### 11.6 — Acceptance criteria for this lane

The packaging/publication lane is complete only when all of the following are true:

1. Pass S package blockers have been remediated and re-verified from built artifacts.
2. The shipped wheel/sdist include the runtime/documentation assets BlindTag actually depends on.
3. Packaged README/metadata render truthfully at the top of the shipped distribution surface.
4. The Windows `.exe` installer exists and matches the locked Default-vs-Advanced experience contract.
5. The installer exposes `Create shortcut`, `Enable quick launch`, and `Display README.md after install` as explicit options.
6. Default-mode Windows installation remains effectively zero-burden for ordinary users: the installer owns prerequisite setup, including Python bootstrap when needed, and only escalates with Windows permission prompts when actually required.
7. Sandbox install validation proves content, launch path, and handoff posture rather than acting as a smoke-only ritual.
8. TestPyPI publication and install validation complete before any production upload.
9. Final package/publication judgment cites retained build/install/publication evidence rather than informal confidence.

---

## Sign-off Readiness

| Gate                     | Status                                                                                                                                                      |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Code review              | Done (this document)                                                                                                                                        |
| Test suite review        | Done — 5 gaps identified                                                                                                                                    |
| Security alignment       | Done — 2 gaps flagged                                                                                                                                       |
| Calamum config           | DONE — baseline established Pass D                                                                                                                          |
| CI pipeline              | DONE — GitHub Actions wired Pass A                                                                                                                          |
| Force push authorization | Pending joediggidyyy                                                                                                                                        |
| Pass K plan              | LOCKED — aesthetic alignment, glow button, taskbar icon; execute before Pass I                                                                              |
| Pass I plan              | LOCKED — widget-based background posture; execute after Pass K gate                                                                                         |
| Tray process (§10)       | DEFERRED — preserved for future pass after Pass I ships                                                                                                     |
| Pass M plan              | LOCKED — bounded implementation plan aligned to Polymath + Calamum contracts                                                                                |
| Pass N plan              | LOCKED — corrective widget closure pass for terminal-free launch, hidden notification, and top-toggle parity                                                |
| Pass O plan              | LOCKED — clipboard reliability and pressed-state truthfulness closure aligned to Calamum test/security and Polymath guides                                  |
| PyPI publish readiness   | COMPLETE — BlindTag `1.0.0` published to TestPyPI and production PyPI with fresh-install validation (`https://test.pypi.org/project/blindtag/1.0.0/`, `https://pypi.org/project/blindtag/1.0.0/`) |
| Pass J plan              | COMPLETE — logging/reporting shipped and validated (`20260531T230143Z-blindtag-reporting`, `20260531T230637Z-blindtag-all`)                                 |
| Pass R proposal          | COMPLETE — elevated provenance hardening and sandbox-verified forensic lane shipped (`20260531T233221Z-blindtag-forensic`, `20260531T233314Z-blindtag-all`) |
| Pass S proposal          | COMPLETE — package-surface remediation closed and re-verified from built artifacts (`report_tmp/pass_s_package_audit.json`)                                 |
| Pass T plan              | COMPLETE — packaging/publication checklist, installer sandbox validation, TestPyPI staging, and production PyPI publication closed with retained evidence   |

**Execution sequence:** Pass K (aesthetic) → Pass I (background posture) → Pass M (library editor + button cleanup) → Pass N (widget closure corrections) → Pass O (clipboard reliability + pressed-state truthfulness + live publish blocker closure) → Pass J (logging).

**Packaging/publication follow-on:** COMPLETE — Pass S remediation, Pass T checklist execution, Windows installer sandbox validation, TestPyPI validation, and production publication all closed for BlindTag `1.0.0`.

**Packaging/publication evidence:** `report_tmp/pass_s_package_audit.json`; `report_tmp/windows_installer_sandbox_validation/windows_installer_sandbox_validation.{json,md}`; TestPyPI `https://test.pypi.org/project/blindtag/1.0.0/`; PyPI `https://pypi.org/project/blindtag/1.0.0/`; wheel `SHA256 2f7531a02146f7811dc6a56c6c09a0b7a9b435f40619a711b26a62cc07a5f25e`; sdist `SHA256 a56179cefa9b41214531eae7c24a32782b1935f46199e5dadf6a9bf6238b6826`; installer `SHA256 59a671828e1e63f04dcb5cd7c198f97947763e7f4b676a460cf58bda0bfa8946`.

**Follow-on security precondition:** Before BlindTag is reused as a transport/unpack substrate for executable payloads, land Pass R (or an equivalent hardening lane) so the reporting/security surface moves from operational integrity to chain-of-custody-grade security / forensic posture.

Pass M is implementation-ready and bounded by the contracts in M.4–M.6.
