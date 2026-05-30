# Changelog

All notable changes to BlindTag are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Planned (see [docs/REVIEW_AND_MATURITY_PLAN.md](docs/REVIEW_AND_MATURITY_PLAN.md))
- Fix `pyproject.toml` build backend (deprecated `legacy:build` → `setuptools.build_meta`)
- Add project authors, URLs, and classifiers to `pyproject.toml`
- Add `.env.example` placeholder
- Add GitHub Actions CI workflow
- Add Calamum test catalog
- Resolve `test_only_tag_cancel_yields_none_or_empty` test ambiguity
- Add `DecodingError` test coverage
- Add `tests/test_widget.py` (import smoke + plumbing)
- Add `X-Request-Id` response header to API
- Add security headers to API responses

---

## [1.0.0] — 2026-05-30

### Added
- Core Plane 14 steganographic codec engine (`blindtag.core`)
- FastAPI local transport layer with `/encode`, `/decode`, `/strip`, `/health` endpoints (`blindtag.api`)
- Desktop observer widget with live clipboard detection (`blindtag.widget`)
- Domain exception hierarchy (`blindtag.exceptions`)
- CLI launchers `blindtag-api` and `blindtag-widget`
- Full pytest suite — core round-trip, adversarial, normalization, and API integration tests
