# CLAUDE.md — BlindTag Agent Instructions

BlindTag is a sub-project of **CodeSentinel**, part of the **Polymath** ecosystem (polymath-global.com).  
Operator: **joediggidyyy**.

## Operating principles (SEAM order)

- **Security**: Never hardcode credentials or API keys. Use environment variables.
- **Efficiency**: Targeted diffs only — no sweeping refactors or unrequested additions.
- **Awareness**: Verify facts from repo evidence before stating them. Label unverified claims explicitly.
- **Minimalism**: Archive before delete. No feature creep beyond the approved scope.

## Scope

This repository is the standalone BlindTag package. Changes here should not reach into the parent CodeSentinel-1 repository unless explicitly authorized.

## Code rules

- Python 3.11+; type annotations required on all public functions.
- ASCII-only console output.
- All codec changes require a test update in `tests/test_core.py`.
- All API surface changes require a test update in `tests/test_api.py`.
- Run `pytest tests/ -v` before declaring any change complete.

## Response style

Lead with a TL;DR, end with a locked next-action statement. Keep responses concise and evidence-backed.
