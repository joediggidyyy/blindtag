# ⬡ BlindTag

<p align="center">
  <img src="assets/images/blindtag_logo.png" alt="BlindTag" width="180">
</p>

> Unicode Plane 14 Steganographic Obfuscation Toolkit

A [Polymath](https://polymath-global.com) open-source project.

BlindTag embeds invisible payloads inside ordinary Unicode text using characters from the **Tags block** (U+E0000–U+E007F) in Unicode Plane 14. The result is visually indistinguishable from the original string and survives NFC / NFD / NFKC / NFKD normalization intact.

As of 2026-05-31, BlindTag also ships a bounded local-only retained reporting substrate under `.blindtag/generated/reporting/` for API operation records, read-only queries, and controlled evidence exports.

---

## Architecture

```text
blindtag/
├── blindtag/
│   ├── __init__.py        Public API surface
│   ├── core.py            Codec engine — encode / decode / strip_plane14
│   ├── api.py             FastAPI local transport layer
│   ├── reporting.py       Retained JSONL event store + export helpers
│   ├── widget.py          Desktop observer widget (PySide6)
│   └── exceptions.py      Domain exception hierarchy
├── assets/                Runtime/documentation assets
├── installer_app/         Windows installer UI + .exe builder tooling
├── tests/                 Pytest contract coverage
├── run_api.py             API server launcher
├── run_widget.py          Desktop widget launcher
├── pyproject.toml         Package metadata & entry points
└── requirements.txt       Runtime dependencies
```

---

## Mathematical basis

The Tags block occupies 128 codepoints in Plane 14, mirroring the ASCII table shifted by a fixed offset of **0xE0000** (917,504 decimal):

```text
Encode:  ord(ascii_char)    + 0xE0000  ->  Plane 14 tag codepoint
Decode:  plane14_codepoint  - 0xE0000  ->  ord(ascii_char)
```

| ASCII character | Codepoint | Plane 14 tag |
| --------------- | --------- | ------------ |
| `A`             | U+0041    | U+E0041      |
| `z`             | U+007A    | U+E007A      |
| `!`             | U+0021    | U+E0021      |
| `~`             | U+007E    | U+E007E      |

Every payload is terminated by **U+E007F (TAG CANCEL)** — the only Plane 14 character outside the printable ASCII mirror. The decoder uses it as an end-of-stream sentinel.

```text
[ anchor text ][ U+E0020…U+E007E payload chars ][ U+E007F TAG_CANCEL ]
```

---

## Installation

### From source

```bash
git clone https://github.com/joediggidyyy/blindtag.git
cd blindtag

# Runtime only
pip install -e .

# Runtime + dev/testing tools
pip install -e ".[dev]"
```

### Explicit runtime requirements

```bash
pip install -r requirements.txt
```

**Python requirement:** 3.11 or later.

### Windows installer surfaces

BlindTag now includes a Windows installer application source surface and a one-file installer builder:

```bash
# Validate the installer contract (Default/Advanced + required options)
python installer_app/windows_installer.py --validate-contract

# Print the resolved install plan without changing the machine
python installer_app/windows_installer.py --dry-run-install

# Build the Windows .exe installer from an audited wheel
python installer_app/build_windows_installer.py
```

Installer contract highlights:

- **Default (Recommended)** — aimed at recreational/everyday BlindTag use
- **Advanced** — custom setup path with explicit cautionary language
- The installer automatically satisfies the Python/runtime prerequisite lane when needed and only asks Windows for elevation when that setup truly requires it
- The release installer verifies the bundled wheel/README/icon payload hashes before installation and fails closed if the packaged payload no longer matches the installer security manifest
- Downloaded Python bootstrap installers are trust-checked before execution
- Required options:
  - `Create shortcut`
  - `Enable quick launch`
  - `Display README.md after install`

For ordinary Windows users, the target experience is intentionally low-burden: click through the installer, let BlindTag handle dependency/runtime setup, and launch from the installed widget shortcut.

**Build note:** the `.exe` builder requires a locally built BlindTag wheel and `PyInstaller` in the build environment.

### Linux clipboard support

PySide6 uses Qt's native clipboard API. No `xclip` or `xsel` is required on Linux. A running display server (X11 or Wayland via XWayland) is required.

---

## Quick start

### Python API

```python
from blindtag import decode, encode, strip_plane14

# Embed a hidden payload
tagged = encode(
    anchor="Meeting notes from Monday sync.",
    hidden_message="CONFIDENTIAL:REF-INV-7821",
)

# Extract the payload
secret = decode(tagged)
print(secret)
# -> "CONFIDENTIAL:REF-INV-7821"

# Recover clean anchor text
clean = strip_plane14(tagged)
print(clean)
# -> "Meeting notes from Monday sync."
```

### Error handling

```python
from blindtag import encode
from blindtag.exceptions import InvalidPayloadError

try:
    encode("cover", "café")
except InvalidPayloadError as exc:
    print(exc)
```

---

## API server

```bash
python run_api.py
python run_api.py --port 9000
python run_api.py --reload
python run_api.py --log-level debug
```

Interactive docs: `http://127.0.0.1:8000/docs`

### Core endpoints

- `POST /v1/encode`
- `POST /v1/decode`
- `GET /health`
- `GET /v1/log`
- `POST /v1/log/export`

### `GET /v1/log`

Read-only query surface for the retained BlindTag operation ledger.

| Parameter | Meaning |
| --------- | ------- |
| `request_id` | Filter by the API request id emitted in `X-Request-Id` |
| `operation` | Filter by operation name (`encode`, `decode`, `log_query`, `log_export`) |
| `level` | Filter by severity (`debug`, `info`, `warning`, `error`, `critical`) |
| `policy_mode` | Filter by retained policy posture (`operational`, `security`, `forensic`) |
| `action_phase` | Filter by provenance handoff phase (`received`, `verified`, `exported`, `blocked`, `quarantined`, `unpacked`, `released`) |
| `limit` | Maximum records returned |

### `POST /v1/log/export`

Controlled export surface for retained evidence packets. The export root is path-contained under `.blindtag/generated/reporting/exports/`.

- `operational` mode preserves the Pass J baseline and may use the shared-key gate (`BLINDTAG_EXPORT_SIGNING_KEY`)
- `security` / `forensic` mode use verifier-friendly Ed25519 request verification and detached artifact signing (`BLINDTAG_FORENSIC_SIGNING_*`)
- elevated export bundles include provenance summaries, chain verification, segment-seal summaries, and a sandbox-simulated handoff assessment packet that validates output content and final handoff-completion posture

### Payload size policy

| Field | Maximum |
| ----- | ------- |
| `anchor` | 10,000 chars |
| `hidden_message` | 1,000 chars |
| `raw_text` | 50,000 chars |

Requests exceeding these limits receive **HTTP 422** before any codec logic runs.

---

## Desktop widget

```bash
blindtag-widget
```

### Launch surfaces

| Surface | Intended use | Terminal behavior |
| ------- | ------------ | ----------------- |
| `blindtag-widget` / `blindtag-widget.exe` | Required widget launch surface | **No terminal** — this is the required widget behavior |
| `blindtag widget` | Supported CLI compatibility launcher | Hands off to the dedicated widget surface and should return the calling CLI promptly in installed environments |
| `python run_widget.py` | Direct source-tree developer launch | Keeps a terminal attached; useful for development/debug only |

### Hotkeys

| Shortcut | Action |
| -------- | ------ |
| `Ctrl+E` | Switch to Encode panel |
| `Ctrl+D` | Switch to Decode panel |
| `Ctrl+W` | Toggle Clipboard Watcher |
| `Ctrl+Return` | Execute active panel primary action |
| `Escape` | Close widget |

### Clipboard watcher

When enabled, BlindTag listens to Qt clipboard change events on the GUI thread. If new clipboard content contains a Plane 14 payload, the widget:

1. switches to the Decode panel automatically
2. populates raw input and extracted payload fields
3. shows an inline detection banner when the window is already foregrounded
4. when hidden in background posture, shows a persistent corner relaunch notification on hide and replaces that anchor with the latest hidden payload notification until dismissed or replaced

No data leaves the local machine. Clipboard detection stays inside the Qt event loop and shuts down with the widget.

---

## Running tests

> Tests are orchestrated via **[Calamum](https://github.com/joediggidyyy/calamum)** — the Polymath test runner.
>
> <img src="assets/images/calamum_logo_color.png" alt="Calamum" width="80">

```bash
# All tests
pytest

# Core engine only
pytest tests/test_core.py -v

# API integration only
pytest tests/test_api.py -v

# With coverage report
pytest --cov=blindtag --cov-report=term-missing
```

### Validation highlights

| Class | Requirement |
| ----- | ----------- |
| `TestRoundTrip` | Encode/decode fidelity across payload types |
| `TestValidationBoundaries` | `InvalidPayloadError` for every out-of-range char |
| `TestDecodeNoPayload` | `None` return on clean strings |
| `TestReportingEndpoints` | Retained API query/export coverage and trust gating |
| `TestRetainedExport` | JSONL export family, checksums, and optional signing |
| `TestHighTrustProvenance` | Elevated provenance modes, chain/seal verification, sandbox handoff posture |
| `TestWindowsInstallerContract` | Installer mode/option contract validation |

---

## Security notes

- **Localhost only.** The API server binds to `127.0.0.1` by default. Never expose it on `0.0.0.0` in untrusted network environments.
- **Input sanitization.** The Pydantic validation layer rejects oversized and malformed payloads at the HTTP boundary before any codec code executes.
- **Local-only retained reporting.** BlindTag may persist structured API operation records and export packets under `.blindtag/generated/reporting/`. This data never leaves the local machine unless the operator intentionally copies or publishes it.
- **Elevated provenance modes.** BlindTag supports `security` and `forensic` retained-evidence modes with provenance fields, deny-by-default executable handoff scope rules, tamper-evident record chaining, segment seals, and sandbox-simulated handoff assessment.
- **Platform clipboard.** The clipboard watcher reads only from the local system clipboard (via Qt's native clipboard API). It does not transmit data over any network.

### Reporting validation evidence

Pass J baseline reporting and Pass R elevated provenance hardening were validated under Calamum on 2026-05-31:

- `20260531T230143Z-blindtag-reporting`
- `20260531T230200Z-blindtag-api`
- `20260531T230620Z-blindtag-cli`
- `20260531T230637Z-blindtag-all`
- `20260531T233221Z-blindtag-forensic`
- `20260531T233239Z-blindtag-reporting`
- `20260531T233256Z-blindtag-api`
- `20260531T233314Z-blindtag-all`

---

## License

MIT — see `LICENSE` for details.

---

<p align="center">
  <a href="https://polymath-global.com">
    <img src="assets/images/polymath_global.png" alt="Polymath Global" width="140">
  </a>
  <br>
  <em>BlindTag is developed and maintained by <a href="https://polymath-global.com">Polymath Global</a>.</em>
</p>
