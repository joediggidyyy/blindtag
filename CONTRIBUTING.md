# Contributing to BlindTag

BlindTag is a [Polymath](https://polymath-global.com) / CodeSentinel project.

## Getting started

```bash
git clone https://github.com/joediggidyyy/blindtag.git
cd blindtag
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

## Guidelines

- Keep the package dependency footprint minimal.
- All codec changes must include corresponding test coverage in `tests/test_core.py`.
- API surface changes must include endpoint tests in `tests/test_api.py`.
- Follow existing docstring and type annotation style.
- ASCII-only console output.
- No secrets in source control.

## Submitting changes

Open a pull request against `main`. Describe the problem, the fix, and how to test it.
