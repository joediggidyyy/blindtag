# Changelog

All notable changes to BlindTag are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
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
- Stale `run_widget.py` docstring: replaced `customtkinter`/`pyperclip`/Linux xclip references with PySide6 requirements (Pass C — `69cdda4`)
- Stale `blindtag/__init__.py` module docstring: widget description updated from `(customtkinter)` to `(PySide6)` (Pass C — `69cdda4`)
- `README.md`: architecture block and Linux clipboard section updated to reflect PySide6 rewrite (planning pass — `3ab3a26`)

### Planned (see [docs/REVIEW_AND_MATURITY_PLAN.md](docs/REVIEW_AND_MATURITY_PLAN.md) and [docs/WIDGET_SCHEMA.md](docs/WIDGET_SCHEMA.md))
- **Widget guidance panel** — left-side slide-out `?` panel with collapsed problem-definition cards (Anchor text, Hidden payload, Emoji aliases, Obfuscate & Copy, Clip Watch); see [docs/WIDGET_SCHEMA.md](docs/WIDGET_SCHEMA.md)
- **Emoji alias selector** — inline `☺` trigger on the Hidden Payload row; floating `QFrame` flyout (not modal) showing emoji + alias pairs; clicking appends alias to payload field; aliases are printable ASCII so they encode cleanly through the Plane 14 codec
- **Emoji library editor** — fourth panel in `_stack`, accessible from flyout `Edit library` link; add/delete entries; writes through to `assets/emoji_library.json`; alias validated as printable ASCII on entry
- `assets/emoji_library_default.json` — 20-entry curated default library shipped with the package; seeded into user-local `assets/emoji_library.json` on first run
- Resolve `test_only_tag_cancel_yields_none_or_empty` test ambiguity
- Add `tests/test_widget.py` (import smoke + plumbing + emoji library + guidance panel)
- Add `X-Request-Id` response header to API
- Add security headers to API responses
- Add project authors, URLs, and classifiers to `pyproject.toml`

---

## [1.0.0] — 2026-05-30

### Added
- Core Plane 14 steganographic codec engine (`blindtag.core`)
- FastAPI local transport layer with `/encode`, `/decode`, `/strip`, `/health` endpoints (`blindtag.api`)
- Desktop observer widget with live clipboard detection (`blindtag.widget`)
- Domain exception hierarchy (`blindtag.exceptions`)
- CLI launchers `blindtag-api` and `blindtag-widget`
- Full pytest suite — core round-trip, adversarial, normalization, and API integration tests
