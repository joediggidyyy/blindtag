# Contributing to BlindTag

BlindTag is an open-source project maintained by [Polymath](https://polymath-global.com).

## Setting up a development environment

```bash
git clone https://github.com/joediggidyyy/blindtag.git
cd blindtag

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# Install the package and dev dependencies
pip install -e ".[dev]"
```

**Python requirement:** 3.11 or later.

## Running tests

```bash
# Full suite
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=blindtag --cov-report=term-missing
```

All tests must pass before opening a pull request.

## Contribution guidelines

- **Scope**: Keep changes focused. One concern per pull request.
- **Tests**: All codec changes require a test update in `tests/test_core.py`. All API surface changes require a test update in `tests/test_api.py`.
- **Dependencies**: Keep the runtime dependency footprint minimal. New runtime dependencies require justification.
- **Style**: Follow existing docstring and type annotation conventions. Python 3.11+ type annotations are required on all public functions.
- **Output**: ASCII-only console output in all CLI and logging paths.
- **Security**: No secrets, tokens, or machine-local paths in source control. See [SECURITY.md](SECURITY.md) for the vulnerability disclosure process.

## Submitting a pull request

1. Fork the repository and create a feature branch off `main`.
2. Make your changes and run the full test suite.
3. Open a pull request against `main`. In the PR description, state the problem, the solution, and how to test it.

## Reporting issues

Use [GitHub Issues](https://github.com/joediggidyyy/blindtag/issues). For security vulnerabilities, follow the process in [SECURITY.md](SECURITY.md) instead of opening a public issue.
