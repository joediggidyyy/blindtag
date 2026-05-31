# BlindTag CLI — Locked Implementation Checklist

**Status**: COMPLETE — all 7 steps executed and verified; calamum evidence `20260530T202620Z-blindtag-all` (`decision: go`); committed `69cdda4`, pushed to `origin/main`  
**Pass**: C — Unified CLI Scaffold  
**Precondition**: Pass A and Pass B are complete and committed (see CHANGELOG.md [1.0.0] + [Unreleased])  
**Schema authority**: [docs/CLI_SCHEMA.md](CLI_SCHEMA.md)  
**Drift guard**: Any deviation from this checklist requires explicit re-lock before execution resumes

---

## Pre-implementation gates (all must be green before any code is written)

- [ ] `calamum test run blindtag-all --project "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"` reports `decision: go` with 0 failures on the current HEAD
- [ ] `git -C "projects/blindtag" status` is clean (no uncommitted changes)
- [ ] This checklist file is committed to the repo before any implementation begins

---

## Step 1 — Catalog update (first artifact; no implementation code yet)

Update `catalog/test_definitions.json` to add the `blindtag-cli` definition **before** `blindtag/cli.py` exists.

### 1.1 Add `blindtag-cli` definition

Insert as the fourth definition (after `blindtag-api`, before `blindtag-all`):

```json
{
  "id": "blindtag-cli",
  "title": "BlindTag Unified CLI",
  "summary": "Tests for the blindtag root CLI entry point: encode, decode, strip subcommands (text + JSON output, stdin piping, exit codes), api shim delegation, widget shim delegation, --version flag.",
  "status": "active",
  "category": "integration",
  "selector_policy": "exact-name-only",
  "profiles": ["default", "release"],
  "tags": ["cli", "smoke"],
  "policy_flags": ["deterministic-output", "local-only", "release-gate"],
  "evidence_requirements": ["stdout_capture", "stderr_capture", "report_json"],
  "default_lanes": ["pytest"],
  "metadata": {
    "module": "blindtag.cli",
    "test_file": "tests/test_cli.py"
  },
  "lanes": {
    "pytest": [
      {
        "id": "cli-pytest",
        "title": "pytest tests/test_cli.py",
        "command": ["{python}", "-m", "pytest", "tests/test_cli.py", "-v", "--tb=short"],
        "expected_artifacts": ["stdout", "stderr"],
        "evidence_requirements": ["stdout_capture", "stderr_capture"],
        "notes": "CLI subcommand contracts, exit codes, JSON output, stdin piping, compat shims."
      }
    ],
    "sandbox_test": [],
    "empirical_test": []
  }
}
```

### 1.2 Update `blindtag-all` lane command to include `tests/test_cli.py`

The existing `all-pytest` command uses `tests/` (directory scan), so it already picks up `test_cli.py` automatically — **no change needed** to the `blindtag-all` definition. Verify after `test_cli.py` is written that calamum still resolves it correctly.

**Commit message for this step:**

```
catalog: add blindtag-cli test definition for unified CLI (pre-implementation gate)
```

---

## Step 2 — `tests/test_cli.py` skeleton (test file before implementation)

Create `tests/test_cli.py` with the full class/method skeleton and `pytest.mark.skip(reason="cli not yet implemented")` on each test body. This establishes the contract before code is written and ensures calamum can see the file.

### 2.1 Required test classes and methods

```
TestVersion
  test_version_flag_exits_zero
  test_version_flag_prints_version_string

TestEncodeSubcommand
  test_encode_basic_roundtrip_via_decode
  test_encode_json_output_fields
  test_encode_invalid_payload_exits_1
  test_encode_usage_error_exits_2

TestDecodeSubcommand
  test_decode_found_prints_payload
  test_decode_not_found_prints_nothing_exits_0
  test_decode_stdin_pipe
  test_decode_json_output_found
  test_decode_json_output_not_found
  test_decode_invalid_plane14_exits_1

TestStripSubcommand
  test_strip_removes_plane14_chars
  test_strip_stdin_pipe
  test_strip_json_output_field
  test_strip_clean_string_passthrough

TestApiShim
  test_api_shim_delegates_to_cli
  test_api_shim_passes_flags_through

TestWidgetShim
  test_widget_shim_delegates_to_cli

TestHelpPages
  test_root_help_exits_zero
  test_encode_help_exits_zero
  test_decode_help_exits_zero
  test_strip_help_exits_zero
  test_api_help_exits_zero
  test_widget_help_exits_zero
```

**Total: 26 test stubs**

### 2.2 Test infrastructure requirements

- Invoke CLI through `subprocess.run(["python", "-m", "blindtag", ...], capture_output=True, text=True)` — do NOT import `main()` and call directly in tests. The subprocess approach validates the installed entry point path and the exit-code contract simultaneously.
- For stdin piping tests: use `subprocess.run(..., input="<text>", ...)`.
- Tests must not require a live PySide6 display; widget shim test must verify delegation happens without actually launching the GUI (mock the `run_widget` call or catch the `ImportError`/`SystemExit` before GUI initializes).

**Commit message for this step:**

```
tests: add test_cli.py skeleton with 26 contract stubs (pre-implementation)
```

---

## Step 3 — `blindtag/cli.py` implementation

### 3.1 Module structure (locked)

```python
# blindtag/cli.py
#
# Top-level import budget: argparse, sys, json — ONLY.
# PySide6, fastapi, uvicorn, blindtag.api, blindtag.widget must be
# lazy-imported INSIDE each handler. This keeps --help and --version
# instantaneous and prevents GUI toolkit initialization on encode/decode calls.

import argparse
import json
import sys
from typing import NoReturn

from blindtag import __version__

def main(argv: list[str] | None = None) -> None: ...
def _api_shim() -> None: ...
def _widget_shim() -> None: ...
```

### 3.2 `argparse` shape (locked)

```
parser = ArgumentParser(prog="blindtag", description="BlindTag steganographic toolkit")
parser.add_argument("--version", "-V", action="version", version=f"blindtag {__version__}")
subparsers = parser.add_subparsers(dest="command", required=True)
```

Subparsers:

| name     | positional args                 | flags                                         |
| -------- | ------------------------------- | --------------------------------------------- |
| `encode` | `anchor` (str), `payload` (str) | `--out {text,json}` default `text`            |
| `decode` | `text` (str, may be `-`)        | `--out {text,json}` default `text`            |
| `strip`  | `text` (str, may be `-`)        | `--out {text,json}` default `text`            |
| `api`    | none                            | `--host`, `--port`, `--reload`, `--log-level` |
| `widget` | none                            | none                                          |

### 3.3 Exit code contract (locked, non-negotiable)

| Code | Condition                                                              |
| ---- | ---------------------------------------------------------------------- |
| 0    | Success; `decode`/`strip` emit nothing and exit 0 when input is clean  |
| 1    | Domain error (`InvalidPayloadError`, `DecodingError`, startup failure) |
| 2    | Argparse usage error (argparse default behavior — do not override)     |

`sys.exit(1)` on domain errors; `sys.exit(0)` on clean miss in `decode`.

### 3.4 Stdin contract (locked)

When `text == "-"`: read from `sys.stdin.read()`. This applies to `decode` and `strip` only (not `encode`, which takes two positional args).

### 3.5 `--out json` output schemas (locked)

**encode:**
```json
{"result": "<tagged string>", "anchor_length": 31, "payload_length": 21, "total_length": 53}
```

**decode (found):**
```json
{"found": true, "message": "<payload>"}
```

**decode (not found):**
```json
{"found": false, "message": null}
```

**strip:**
```json
{"result": "<clean string>"}
```

These schemas mirror the API response shapes where applicable. No additional fields without explicit authorization.

### 3.6 Output rules (locked, from Polymath style contract)

- ASCII-only. No emoji, no ANSI escape sequences, no Unicode decorators in any CLI output path.
- `--out text` (default): print the result to stdout, newline-terminated. Nothing else.
- `--out json`: print clean JSON to stdout only. Any progress or error messaging goes to stderr.
- Error messages (exit 1): one line to stderr, format `blindtag <subcommand>: <plain-language reason>`. No stack trace.
- Help pages: must answer "what does this do" + "example" at a minimum. Follow `COMMAND_FORMAT_GUIDELINES.md`: examples in fenced code blocks, not bullet prose.

### 3.7 Shim contract (locked)

```python
def _api_shim() -> None:
    # Called as `blindtag-api [args]` entry point.
    # Reconstructs sys.argv with "api" prepended and delegates to main().
    import sys
    sys.argv = ["blindtag", "api"] + sys.argv[1:]
    main()

def _widget_shim() -> None:
    import sys
    sys.argv = ["blindtag", "widget"] + sys.argv[1:]
    main()
```

### 3.8 `__main__.py` (new file, enables `python -m blindtag`)

```python
# blindtag/__main__.py
from blindtag.cli import main
main()
```

This is required for `subprocess.run(["python", "-m", "blindtag", ...])` to work in tests.

**Commit message for this step:**

```
feat: add blindtag/cli.py unified CLI root and blindtag/__main__.py
```

---

## Step 4 — `pyproject.toml` entry point update

Change the `[project.scripts]` block from:

```toml
[project.scripts]
blindtag-api    = "blindtag.api:run_server"
blindtag-widget = "blindtag.widget:run_widget"
```

To:

```toml
[project.scripts]
blindtag        = "blindtag.cli:main"
blindtag-api    = "blindtag.cli:_api_shim"
blindtag-widget = "blindtag.cli:_widget_shim"
```

No other changes to `pyproject.toml` this pass.

**Commit message for this step:**

```
pyproject: add blindtag entry point; convert api/widget to cli shims
```

---

## Step 5 — Stale docstring fixes (deferred from Pass B)

These are in scope for Pass C because they are caused by the PySide6 rewrite already committed.

### 5.1 `run_widget.py` docstring

Remove all references to `customtkinter`, `pyperclip`, and Linux `xclip`/`xsel` clipboard instructions. Replace the Requirements section:

```
Requirements
------------
  PySide6 >= 6.8  (installed with: pip install -e .)

Platform notes
--------------
  Windows  — Works natively. DPI handling managed by Qt.
  macOS    — Works natively. Grant Accessibility permissions if prompted.
  Linux    — Requires a running display server (X11 or Wayland via XWayland).
```

### 5.2 `blindtag/__init__.py` module docstring

Change the widget line from:

```
blindtag.widget     — Desktop observer widget (customtkinter)
```

To:

```
blindtag.widget     — Desktop observer widget (PySide6)
```

**Commit message for this step:**

```
docs: fix stale customtkinter/pyperclip references in run_widget.py and __init__.py
```

---

## Step 6 — `tests/test_cli.py` — fill implementations

With `blindtag/cli.py` written, remove all `pytest.mark.skip` markers and implement each test body as specified in Step 2.

### 6.1 Implementation invariants for each test class

**TestVersion**: assert `returncode == 0` and `"blindtag " + __version__` appears in stdout.

**TestEncodeSubcommand**:
- `test_encode_basic_roundtrip_via_decode`: call encode with known args, pipe stdout into decode call, assert payload recovered.
- `test_encode_json_output_fields`: assert all four JSON keys present (`result`, `anchor_length`, `payload_length`, `total_length`) with correct types.
- `test_encode_invalid_payload_exits_1`: pass a non-ASCII payload char (e.g. `café`), assert `returncode == 1` and error text in stderr.
- `test_encode_usage_error_exits_2`: omit one required positional, assert `returncode == 2`.

**TestDecodeSubcommand**:
- `test_decode_found_prints_payload`: pre-encode in test, decode the result, assert stdout.strip() == original payload.
- `test_decode_not_found_prints_nothing_exits_0`: pass plain ASCII string, assert `returncode == 0` and `stdout == ""`.
- `test_decode_stdin_pipe`: use `input=` param in subprocess, assert payload recovered.
- JSON tests: assert JSON field values match expected types and values.
- `test_decode_invalid_plane14_exits_1`: construct synthetic out-of-range Plane 14 bytes, assert `returncode == 1`.

**TestStripSubcommand**:
- `test_strip_removes_plane14_chars`: encode a known payload, strip, assert output matches anchor with no tag chars.
- `test_strip_stdin_pipe`: same but via stdin.
- `test_strip_json_output_field`: assert `result` key present in output JSON.
- `test_strip_clean_string_passthrough`: strip a clean string, assert stdout.strip() == input.

**TestApiShim / TestWidgetShim**:
- Verify that `blindtag-api --help` exits 0 and help text mentions `api` subcommand vocabulary.
- Verify that `blindtag-widget --help` exits 0 and help text mentions `widget`.
- Do NOT attempt to start the actual server or GUI in tests.

**TestHelpPages**: all must exit 0 and stdout must be non-empty.

**Commit message for this step:**

```
tests: implement test_cli.py (26 tests, all passing)
```

---

## Step 7 — Calamum evidence gate

Run the full suite and capture the evidence receipt before any commit in this step.

```
.venv-core\Scripts\calamum.exe test run blindtag-all --project "c:\Users\joedi\Documents\CodeSentinel-1\projects\blindtag"
```

**Required evidence conditions:**
- `decision: go`
- 0 failures
- Run ID retained under `.calamum/generated/runs/<run-id>/`
- `report.json` artifact present and readable

**Only after this gate passes:**

```
git -C "projects/blindtag" add .
git -C "projects/blindtag" commit -m "pass-c: unified CLI scaffold complete; calamum evidence <run-id>"
git -C "projects/blindtag" push origin main
```

Then update the submodule pointer in the parent repo:

```
git add projects/blindtag
git commit -m "submodule: update blindtag to pass-c HEAD (unified CLI)"
```

---

## Security alignment checklist (from POLYMATH_SECURITY_MEASURES_AND_EXPECTATIONS.md)

These must be verified true before the final commit in Step 7.

- [ ] No secret values committed
- [ ] `.env.example` is placeholder-only (existing; verify unchanged)
- [ ] `blindtag/cli.py` does not log, print, or expose any env var values
- [ ] `blindtag/cli.py` does not read files outside the current working directory
- [ ] Path containment: CLI subcommands produce output to stdout/stderr only; no file writes
- [ ] Error messages include reason + next action, no raw Python tracebacks
- [ ] `blindtag --help`, `blindtag encode --help`, etc. are self-orienting (no README dependency)
- [ ] Publishable artifact (wheel/sdist) does not include `.env`, private paths, or signing material
- [ ] `codesentinel scan` (or equivalent) passes after CLI module addition

---

## Calamum security alignment checklist (evidence integrity)

- [ ] `blindtag-cli` catalog definition carries `policy_flags: ["deterministic-output", "local-only", "release-gate"]`
- [ ] `blindtag-cli` definition carries `evidence_requirements: ["stdout_capture", "stderr_capture", "report_json"]`
- [ ] `blindtag-all` evidence run after CLI addition produces `report_json` artifact
- [ ] Run index entry written to `.calamum/generated/runs/run_index.jsonl`
- [ ] Run ID format is `<timestamp>Z-blindtag-all` (existing calamum convention confirmed)
- [ ] No test in `test_cli.py` modifies or writes to `.calamum/` (path containment)

---

## Polymath style alignment checklist (from POLYMATH_USER_FACING_STYLE_AND_FORMATTING_EXPECTATIONS.md)

- [ ] CLI output answers: what ran, what happened, why, what next — without requiring the user to inspect logs
- [ ] `--out text` path: result only on stdout, no decoration
- [ ] `--out json` path: clean JSON on stdout; any error goes to stderr
- [ ] Error output: reason + next action, not raw exception name as primary message
- [ ] Help pages: usage + summary + options + at least one example per subcommand
- [ ] Examples in help text use fenced code block style where possible (doc convention)
- [ ] Decision vocabulary: encode → success/fail; decode → found/not-found; strip → success — no invented terms

---

## What is NOT in scope for Pass C

These items are explicitly out of scope and must not be implemented during this pass:

| Item                                                               | Reason                                                         |
| ------------------------------------------------------------------ | -------------------------------------------------------------- |
| `X-Request-Id` API response header                                 | Planned for a separate API hardening pass                      |
| `X-Content-Type-Options` / `X-Frame-Options` headers               | Same                                                           |
| `tests/test_widget.py`                                             | Deferred; widget tests require separate planning               |
| Rate limiting on API                                               | Accepted risk (localhost-only); documented in SECURITY.md      |
| `ruff` / `mypy` config in `pyproject.toml`                         | Separate tooling-config pass                                   |
| `blindtag check` subcommand or any subcommand not in CLI_SCHEMA.md | Not in schema; requires re-lock                                |
| Any new runtime dependency                                         | Prohibited by dependency policy without explicit authorization |

---

## Drift detection rules

If during implementation any of the following occur, STOP and request re-lock from joediggidyyy:

1. A new subcommand is needed that is not in `docs/CLI_SCHEMA.md`
2. A test requires a new runtime dependency
3. The `--out json` schema needs a field not listed in Step 3.5
4. A shim requires different behavior than Step 3.7 specifies
5. The calamum catalog structure needs to differ from Step 1.1
6. The widget shim test cannot be written without launching a real GUI

---

*Document locked: 2026-05-30. Implementation proceeds only after joediggidyyy confirms: "locked, proceed."*
