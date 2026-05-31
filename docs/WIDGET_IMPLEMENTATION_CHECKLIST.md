# BlindTag Widget — Locked Implementation Checklist

**Status**: COMPLETE — Pass D executed and validated by ORACL  
**Pass**: D — Widget Guidance Panel + Emoji Selector + Library Editor  
**Precondition**: Pass C complete (`e134dab`); `9c62510` pushed; calamum evidence `20260530T210251Z-blindtag-all` (`decision: go`)  
**Completion evidence**: calamum `20260530T215832Z-blindtag-widget` (`decision: go`) + `20260530T220231Z-blindtag-all` (`decision: go`, 0 failures)  
**Schema authority**: [docs/WIDGET_SCHEMA.md](WIDGET_SCHEMA.md)  
**Drift guard**: Any deviation from this checklist requires explicit re-lock before execution resumes

---

## Pre-implementation gates (all must be green before any code is written)

- [ ] `calamum test run blindtag-all --project "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"` reports `decision: go` with 0 failures on current HEAD
- [ ] `git -C "projects/blindtag" status` is clean (no uncommitted changes)
- [ ] This checklist file is committed to the repo before any implementation begins

---

## Step 1 — Catalog update (first artifact; no implementation code yet)

Update `catalog/test_definitions.json` to add the `blindtag-widget` definition and update `blindtag-all` to reference `tests/test_widget.py` coverage.

### 1.1 Add `blindtag-widget` definition

Insert as the fourth definition (after `blindtag-cli`, before `blindtag-all`):

```json
{
  "id": "blindtag-widget",
  "title": "BlindTag Widget — Library, Guidance Panel, Emoji Selector",
  "summary": "Headless unit tests for the EmojiLibrary load/save/validate logic; panel open/close smoke; flyout cell count and alias-append contract; requires QApplication fixture from conftest.py for widget tests.",
  "status": "active",
  "category": "integration",
  "selector_policy": "exact-name-only",
  "profiles": ["default", "release"],
  "tags": ["widget", "smoke"],
  "policy_flags": ["deterministic-output", "local-only", "release-gate"],
  "evidence_requirements": ["stdout_capture", "stderr_capture", "report_json"],
  "default_lanes": ["pytest"],
  "metadata": {
    "module": "blindtag.widget",
    "test_file": "tests/test_widget.py"
  },
  "lanes": {
    "pytest": [
      {
        "id": "widget-pytest",
        "title": "pytest tests/test_widget.py",
        "command": ["{python}", "-m", "pytest", "tests/test_widget.py", "-v", "--tb=short"],
        "expected_artifacts": ["stdout", "stderr"],
        "evidence_requirements": ["stdout_capture", "stderr_capture"],
        "notes": "EmojiLibrary schema, validation, add/remove, alias selection (headless). GuidancePanel and EmojiFlyout smokes via QApplication fixture."
      }
    ],
    "sandbox_test": [],
    "empirical_test": []
  }
}
```

### 1.2 Update `blindtag-all` summary

The `blindtag-all` summary line currently reads `"Rollup lane running the complete test suite (core + API)."` — update to `"Rollup lane running the complete test suite (core + API + CLI + widget)."`. No other change to the all-pytest lane is required; `pytest tests/` already picks up `test_widget.py`.

### 1.3 Run calamum against HEAD before touching any .py files

```powershell
& "c:\Users\joedi\Documents\CodeSentinel-1\.venv-core\Scripts\calamum.exe" test run blindtag-all --project "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"
```

This must report `decision: go` before Step 2 begins. Record the run ID as the pre-implementation baseline receipt.

---

## Step 2 — Library data file

Create `assets/emoji_library_default.json` with the 20-entry canonical default library as specified in [docs/WIDGET_SCHEMA.md — Persistence section](WIDGET_SCHEMA.md).

Rules:
- Every entry: `{ "emoji": "...", "alias": "...", "codes": [...], "label": "..." }`
- `alias` must be a member of `codes` for every entry
- Every code must match `^[ -~]+$` (printable ASCII 0x20–0x7E)
- Array is ordered to match the 6-column grid layout (first 6 = row 1, etc.)
- File is UTF-8, no BOM, LF line endings

Verify after creation:
```powershell
python -c "import json,pathlib; data=json.loads(pathlib.Path('assets/emoji_library_default.json').read_text('utf-8')); print(len(data), 'entries'); assert all(e['alias'] in e['codes'] for e in data), 'alias not in codes'; import re; p=re.compile(r'^[ -~]+$'); assert all(p.match(c) for e in data for c in e['codes']), 'non-ASCII code'; print('OK')"
```

---

## Step 3 — `EmojiLibrary` helper class (headless, no Qt)

Add an `EmojiLibrary` class to `blindtag/widget.py` before any Qt class definitions.

**Contract:**
- `__init__(self, path: Path)` — accepts explicit path (dependency injection for tests)
- `load() -> list[dict]` — loads and validates JSON; on malformed JSON logs a warning string and returns `[]`; on valid JSON returns the entry list; validates alias-in-codes and printable-ASCII contracts; entries that fail validation are silently dropped with a warning per dropped entry
- `save(entries: list[dict]) -> None` — serializes and writes atomically (write to `.tmp`, rename)
- `validate_codes(codes: list[str]) -> bool` — returns True if all codes match `^[ -~]+$`
- `validate_entry(entry: dict) -> bool` — returns True if `alias in codes` and `validate_codes(codes)` and required keys present
- `add_entry(entry: dict) -> None` — validates, appends, saves
- `remove_entry(emoji: str) -> None` — removes entry by emoji glyph, saves
- `set_active_alias(emoji: str, code: str) -> None` — sets `alias` for given entry to `code` (must be in `codes`), saves

**Path resolution** (used by `BlindTagWindow.__init__`):
```python
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_DEFAULT_LIBRARY_PATH = _ASSETS_DIR / "emoji_library_default.json"
```
This resolves correctly regardless of working directory.

---

## Step 4 — `_GuidancePanel` class

Add `_GuidancePanel(QWidget)` to `blindtag/widget.py`.

Spec:
- Width: `200px` fixed; background `C_SECONDARY`; border-right `1px solid #303030`
- Overlays (does not push) the encode/decode panel — `QWidget` child of `BlindTagWindow`, `raise_()` on show, shown/hidden by `?` toggle
- Five `_EmojiCard` items: Anchor text, Hidden payload, Emoji aliases, Obfuscate & Copy, Clip Watch
- Card content per [WIDGET_SCHEMA.md Surface 1 — Card content table](WIDGET_SCHEMA.md)
- Card with caret: header row clickable, body expands in-place (`QLabel`, `wordWrap=True`, `C_MUTED`, `9pt`)
- Cards with shallow content (none in the defined set — all 5 have caret) display expand caret
- Z-order: always above `_stack` panels; below title bar and status bar

---

## Step 5 — `_EmojiFlyout` class

Add `_EmojiFlyout(QFrame)` to `blindtag/widget.py`.

Spec:
- `QFrame`, `StyledPanel` shape; not a separate window; width `240px`; max height `220px`; background `C_SURFACE`; border `1px solid #303030`
- `QGridLayout`, 6 columns; each cell a `QPushButton` showing the emoji glyph only (no alias text)
- Button style: `_btn_ghost_style()` + `font-size: 18pt; padding: 6px`; fixed `44×44`
- On click: append entry's `alias` to `_hidden_input`, close flyout
- Dismiss on Escape or click-outside (event filter installed on parent window)
- Bottom: `Edit library ⚙` link (`QPushButton`, ghost style); clicking switches `_stack` to library editor panel and closes flyout
- Populated from `EmojiLibrary.load()` at open time

---

## Step 6 — `_LibraryEditorPanel` class

Add `_LibraryEditorPanel(QWidget)` to `blindtag/widget.py` as the 4th panel in `_stack`.

Spec:
- Not exposed in toggle strip; entered from flyout, exited via `← Back` ghost button at top
- Per row: glyph (`18pt`, non-editable) | active indicator `●` in `C_ACCENT` | active alias text label | codes picker (`QFrame`-based popup listing `codes` array, selecting sets active alias immediately and calls `EmojiLibrary.set_active_alias`) | label (`C_MUTED`) | delete `✕` (calls `EmojiLibrary.remove_entry`, removes row)
- Add-entry form: Emoji field (single char) | Label field | Codes field (comma-separated); `Add` button right-aligned; validation on submit: each code must pass `EmojiLibrary.validate_codes`; red border on invalid, no modal/dialog
- All mutations call `EmojiLibrary` methods which write through immediately; no Save button
- `← Back` returns `_stack` to the previously active encode/decode panel

---

## Step 7 — Wire-up

### 7.1 `?` button in `_TitleBar`

Insert after the title label, before `addStretch()`:
```python
self._btn_help = QPushButton("?")
self._btn_help.setFixedSize(26, 26)
self._btn_help.setStyleSheet(_btn_ghost_style())
layout.addWidget(self._btn_help)
```
Connect in `BlindTagWindow.__init__`: `self._title_bar._btn_help.clicked.connect(self._toggle_guidance_panel)`.

`_toggle_guidance_panel` shows/hides `_guidance_panel` and calls `_guidance_panel.raise_()` on show.

### 7.2 `☺` trigger in `_build_encode_panel()`

In the `HIDDEN PAYLOAD` section label row, add `☺` button (`26×26`, `_btn_ghost_style()`) on the right side of the label row. Connect to `self._open_emoji_flyout()`.

`_open_emoji_flyout()` creates/recreates `_EmojiFlyout`, positions it below the trigger button, calls `show()` + `raise_()`.

---

## Step 8 — `tests/conftest.py`

Create `tests/conftest.py` with a session-scoped `qapp` fixture. No new runtime dependency — `PySide6` is already a project dependency.

```python
import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
```

This fixture is required by `TestGuidancePanel` and `TestEmojiFlyout`. `TestEmojiLibrary` does not use it.

---

## Step 9 — `tests/test_widget.py`

Create `tests/test_widget.py` with three test classes:

### `TestEmojiLibrary` (headless — no `qapp` fixture)

| Test                                | Assert                                                                  |
| ----------------------------------- | ----------------------------------------------------------------------- |
| `test_load_default_library`         | Load `assets/emoji_library_default.json`; len == 20                     |
| `test_schema_completeness`          | Every entry has `emoji`, `alias`, `codes`, `label`                      |
| `test_alias_in_codes`               | `entry["alias"] in entry["codes"]` for every entry                      |
| `test_all_codes_printable_ascii`    | All codes match `^[ -~]+$`                                              |
| `test_add_and_remove_entry`         | Add entry via `EmojiLibrary(tmp_path)`, remove it; file reflects change |
| `test_set_active_alias`             | Set alias to second code; JSON updated correctly                        |
| `test_invalid_code_rejected`        | `validate_codes(["bad\x80code"])` returns False                         |
| `test_alias_not_in_codes_rejected`  | `validate_entry` returns False when alias not in codes                  |
| `test_malformed_json_returns_empty` | Write `{invalid}` to tmp JSON; `EmojiLibrary.load()` returns `[]`       |

Note: `TestEmojiLibrary` uses `tmp_path` (pytest built-in) for write tests; it never writes to `assets/emoji_library_default.json`.

### `TestGuidancePanel` (uses `qapp` fixture)

| Test                       | Assert                                                  |
| -------------------------- | ------------------------------------------------------- |
| `test_panel_instantiates`  | `_GuidancePanel` constructs without error               |
| `test_card_count`          | 5 cards present (one per schema entry)                  |
| `test_card_text_not_empty` | No card has an empty header or empty expanded body text |

### `TestEmojiFlyout` (uses `qapp` fixture)

| Test                              | Assert                                                                |
| --------------------------------- | --------------------------------------------------------------------- |
| `test_flyout_instantiates`        | `_EmojiFlyout` constructs with a populated library                    |
| `test_cell_count_matches_library` | Grid cell count == library entry count                                |
| `test_click_appends_alias`        | Clicking cell 0 appends `library[0]["alias"]` to a mock payload field |

---

## Step 10 — Validation gate

Run the full suite via calamum:

```powershell
& "c:\Users\joedi\Documents\CodeSentinel-1\.venv-core\Scripts\calamum.exe" test run blindtag-all --project "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"
```

Required outcome: `decision: go`, 0 failures across all test files (core + api + cli + widget). Record run ID as the Pass D completion receipt.

---

## Step 11 — Commit and push

```powershell
git -C "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag" add -A
git -C "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag" commit -m "feat(Pass D): guidance panel, emoji selector, library editor, test_widget.py"
git -C "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag" push origin main
```

Then advance the CodeSentinel-1 submodule pointer:

```powershell
git -C "c:\Users\joedi\Documents\CodeSentinel-1" add projects/blindtag
git -C "c:\Users\joedi\Documents\CodeSentinel-1" commit -m "submodule: advance blindtag to Pass D (guidance panel + emoji selector + library editor)"
```

---

## Pass D completion criteria (all required)

- [x] `assets/emoji_library_default.json` exists, 20 entries, all schema-valid
- [x] `blindtag-widget` definition present in `catalog/test_definitions.json`
- [x] `tests/conftest.py` with `qapp` fixture present
- [x] `tests/test_widget.py` with all three test classes present (15 tests, 15 passed)
- [x] `calamum test run blindtag-all` → `decision: go`, 0 failures — run `20260530T220231Z-blindtag-all`
- [x] Commit pushed to `origin/main`
- [x] CodeSentinel-1 submodule pointer advanced

---

## Deferred items (separate passes)

### Pass E — API security headers

Planned items from [docs/REVIEW_AND_MATURITY_PLAN.md](REVIEW_AND_MATURITY_PLAN.md):

| Item                                  | Spec                                                                                      |
| ------------------------------------- | ----------------------------------------------------------------------------------------- |
| `X-Request-Id` response header        | Add middleware to `blindtag/api.py`; generate UUID4 per request; include in all responses |
| `X-Content-Type-Options: nosniff`     | Add as static response header middleware                                                  |
| `X-Frame-Options: DENY`               | Add as static response header middleware                                                  |
| API test coverage for headers         | Add `TestSecurityHeaders` class to `tests/test_api.py`                                    |
| Update `blindtag-api` catalog summary | Reference new test class                                                                  |

### Pass F — Code quality

| Item                                                  | Spec                                                                                                                                 |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `test_only_tag_cancel_yields_none_or_empty` ambiguity | Change `assert result is None or result == ""` to `assert result is None` — TAG_CANCEL with no payload chars is unambiguously `None` |
| `Optional` import from `typing` in `core.py`          | Replace with `str \| None` union type (Python 3.10+ style)                                                                           |
| `__all__` export list in `core.py`                    | Add to lock the public surface                                                                                                       |
| `pyproject.toml` metadata                             | Add project authors, `project.urls` classifier entries, trove classifiers                                                            |

---

## Security alignment record

| Polymath invariant                     | Alignment                                                                                                                                                                                       |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No secrets in source control           | Satisfied — `assets/emoji_library_default.json` is non-secret data                                                                                                                              |
| Path containment                       | Enforced — library load/save uses `Path(__file__)`-relative resolution; no user-supplied path escapes the assets dir                                                                            |
| Fail closed on malformed input         | Enforced — malformed JSON → empty library + status bar warning; no crash                                                                                                                        |
| Retained evidence verifiable           | Calamum `report_json` evidence requirement on all definitions; run IDs recorded in checklist                                                                                                    |
| No modal dialogs for validation errors | Enforced — red border only; no modal or dialog on invalid code input                                                                                                                            |
| Signed evidence                        | Noted gap — `signed-evidence` policy flag not yet added to release-gate catalog entries; accepted at current maturity level; revisit when calamum signing integration is ready for this project |
