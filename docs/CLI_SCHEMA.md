# BlindTag CLI Schema

**Status**: Proposed — locked for implementation  
**Implementation target**: Pass C (code hardening / CLI scaffold)  
**Execution authority**: [docs/CLI_IMPLEMENTATION_CHECKLIST.md](CLI_IMPLEMENTATION_CHECKLIST.md) — checklist is the canonical step-by-step contract  
**Entry point**: `blindtag = "blindtag.cli:main"` (to be added to `[project.scripts]`)

---

## Design principles

1. **Unified root** — a single `blindtag` command owns all subcommands. `blindtag-api` and `blindtag-widget` become backward-compat shims.
2. **Codec first** — `encode`, `decode`, and `strip` are top-level subcommands; they must work without starting a server or launching a GUI.
3. **Minimal flags** — every subcommand has the smallest flag surface that covers real usage. No flags that duplicate Python-API options unavailable at the shell boundary.
4. **Stdin piping** — `decode` and `strip` accept `-` as `<text>` to read from stdin, making the tool scriptable.
5. **Structured output** — optional `--out json` flag on codec subcommands for machine-readable results; plain text is the default.

---

## Hierarchy

```
blindtag [--version | -V] [--help | -h] [--log-level LEVEL] [--verbose]
  │
  │   --log-level LEVEL   (debug|info|warning|error|critical; default: warning)
  │                         Applied globally. Widget path defaults to silent (warning).
  │                         API path overrides this with its own --log-level flag.
  │   --verbose | -v        Shorthand for --log-level debug
  │
  ├── encode <anchor> <payload>
  │     --out {text,json}          (default: text)
  │
  ├── decode <text | ->
  │     --out {text,json}          (default: text)
  │
  ├── strip  <text | ->
  │     --out {text,json}          (default: text)
  │
  ├── api
  │     --host HOST                (default: 127.0.0.1)
  │     --port PORT                (default: 8000)
  │     --reload                   (dev hot-reload)
  │     --log-level LEVEL          (debug|info|warning|error|critical; default: info)
  │                                 Overrides global --log-level for the API server.
  │
  └── widget
        (no flags; always runs at warning-level logging regardless of global flag)
```

---

## Subcommand reference

### `blindtag encode`

Embed a hidden payload into anchor text.

```bash
blindtag encode "Meeting notes from Monday sync." "CONFIDENTIAL:REF-7821"
```

**Output (text, default)**
```
Meeting notes from Monday sync.
```
*(invisible Plane 14 chars follow the anchor in the output stream)*

**Output (`--out json`)**
```json
{ "result": "...", "anchor_length": 31, "payload_length": 21, "total_length": 53 }
```

**Exit codes**
| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | `InvalidPayloadError` — payload contains non-printable-ASCII characters |
| 2 | Usage error |

---

### `blindtag decode`

Extract the hidden payload from text. Exits 0 with empty output when no payload is present.

```bash
blindtag decode "Meeting notes from Monday sync.<invisible>"

# Piped input
pbpaste | blindtag decode -
```

**Output (text, default)**
```
CONFIDENTIAL:REF-7821
```
*(prints nothing and exits 0 when no payload is found — shell-friendly)*

**Output (`--out json`)**
```json
{ "found": true,  "message": "CONFIDENTIAL:REF-7821" }
{ "found": false, "message": null }
```

**Exit codes**
| Code | Meaning |
|---|---|
| 0 | Success (payload found OR cleanly absent) |
| 1 | `InvalidPayloadError` — malformed Plane 14 sequence |
| 2 | Usage error |

---

### `blindtag strip`

Remove all Plane 14 tag characters; print the clean anchor.

```bash
blindtag strip "Meeting notes from Monday sync.<invisible>"

# Piped input
xclip -o | blindtag strip -
```

**Exit codes**
| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Usage error |

---

### `blindtag api`

Start the FastAPI server. Equivalent to the current `blindtag-api` entry point.

```bash
blindtag api                        # 127.0.0.1:8000
blindtag api --port 9000
blindtag api --reload
blindtag api --log-level debug
blindtag api --host 0.0.0.0         # expose to LAN (use with caution)
```

No sub-subcommands; there is only one API operation (serve). Nesting a `serve` token would be unnecessary ceremony.

**Exit codes**
| Code | Meaning |
|---|---|
| 0 | Clean shutdown |
| 1 | Startup failure (port in use, import error, etc.) |
| 2 | Usage error |

---

### `blindtag widget`

Launch the desktop observer widget. Equivalent to the current `blindtag-widget` entry point.

```bash
blindtag widget
```

No flags; the widget is self-contained. Always runs at `warning` log level — the global `--log-level` flag has no effect on widget startup. Platform notes from `run_widget.py` still apply.

**Exit codes**
| Code | Meaning |
|---|---|
| 0 | Clean close |
| 1 | Import / display error |

---

## Entry point plan (`pyproject.toml`)

```toml
[project.scripts]
blindtag        = "blindtag.cli:main"          # new — unified root
blindtag-api    = "blindtag.cli:_api_shim"     # compat alias → delegates to cli
blindtag-widget = "blindtag.cli:_widget_shim"  # compat alias → delegates to cli
```

`_api_shim` and `_widget_shim` are one-line wrappers that call `main(["api", ...])` and `main(["widget"])` respectively, preserving backward compatibility.

---

## Implementation notes

- Use standard library `argparse` with `add_subparsers(dest="command", required=True)`.
- Place all CLI logic in `blindtag/cli.py`. The module must not import `PySide6` or `fastapi` at the top level; lazy-import inside each subcommand handler to keep `--help` / `--version` instantaneous.
- Create `blindtag/__main__.py` to enable `python -m blindtag` (required for subprocess-based tests).
- Stdin read: `sys.stdin.read()` when `text == "-"`.
- ASCII-only console output; no emoji in CLI paths (per SEAM code standards).
- `--version` prints `blindtag 1.0.0` and exits 0. Reads `__version__` from `blindtag.__init__`.

### Logging architecture (hooks required in Pass C; implementation in Pass J)

The CLI must wire a root `logging` logger for the `blindtag` package namespace at startup, before any subcommand handler runs. This is a **hook reservation** — the full tiered logging and reporting infrastructure is implemented in Pass J, but the hook must exist in Pass C so the reporting layer can attach without touching CLI code.

**Required in Pass C:**

```python
import logging

def _configure_logging(level_name: str) -> None:
    """Wire the blindtag root logger. Called once at CLI entry before subcommand dispatch."""
    level = getattr(logging, level_name.upper(), logging.WARNING)
    logging.getLogger("blindtag").setLevel(level)
    # Handler intentionally absent here — the reporting layer (Pass J) will attach
    # a structured handler. Until then, output propagates to the root logger (stderr).
    if not logging.getLogger("blindtag").handlers:
        _h = logging.StreamHandler()
        _h.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        logging.getLogger("blindtag").addHandler(_h)
        logging.getLogger("blindtag").propagate = False
```

**Widget path**: `_configure_logging("warning")` regardless of global flag. Do not pass the global flag into the widget subcommand.

**API path**: `_configure_logging(api_args.log_level)` overrides the global level for the server process.

**Codec paths** (`encode`, `decode`, `strip`): use the global `--log-level` value; default `warning` means no output for everyday use.

**Key design constraint**: the `blindtag` package is intended to be **imported and used via API by other applications**. The root logger must never attach a handler unconditionally at import time — only the CLI entry point configures handlers. Library consumers configure their own logging. This means:
- `blindtag/core.py`, `blindtag/api.py` use `logging.getLogger(__name__)` only — no `basicConfig`, no handler attachment at module level.
- The reporting layer (Pass J) attaches a structured file handler to `logging.getLogger("blindtag")` at runtime when invoked via the API or CLI.

---

## Stale surfaces to fix when implementing

| File | Issue |
|---|---|
| `run_widget.py` | Docstring still references `customtkinter`, `pyperclip`, Linux `xclip` (obsolete after PySide6 rewrite) |
| `blindtag/__init__.py` | Module docstring describes widget as "(customtkinter)" |
| `README.md` Security Notes | Fixed — now references Qt native clipboard API |

These can be corrected in the same pass as CLI scaffolding.

---

*Document created: 2026-05-30. Schema is design intent; implementation is pending.*
