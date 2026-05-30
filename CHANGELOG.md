# Changelog

All notable changes to BlindTag are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] — 2026-05-30

### Added
- Core Plane 14 steganographic codec engine (`blindtag.core`)
- FastAPI local transport layer with `/encode`, `/decode`, `/strip`, `/health` endpoints (`blindtag.api`)
- Desktop observer widget with live clipboard detection (`blindtag.widget`)
- Domain exception hierarchy (`blindtag.exceptions`)
- CLI launchers `blindtag-api` and `blindtag-widget`
- Full pytest suite — core round-trip, adversarial, normalization, and API integration tests
