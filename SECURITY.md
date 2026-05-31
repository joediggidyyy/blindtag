# Security Policy

BlindTag is maintained by [Polymath](https://polymath-global.com).

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.x     | Yes       |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, email **security@polymath-global.com** with:

- A clear description of the vulnerability and its potential impact
- Steps to reproduce or a minimal proof-of-concept
- Any suggested mitigations you have identified

You will receive an acknowledgement within **3 business days**. We aim to triage and respond with a remediation timeline within **10 business days**.

## Scope

In-scope for this project:

- The `blindtag` codec engine (`blindtag/core.py`)
- The FastAPI transport layer (`blindtag/api.py`) — particularly any path that could allow unexpected data exfiltration or remote code execution
- The desktop widget clipboard watcher (`blindtag/widget.py`) — particularly any path that could silently transmit clipboard data

Out of scope:

- Vulnerabilities in third-party dependencies (report those to the upstream project)
- The API server being accessible on a network if the operator deliberately binds it to `0.0.0.0` (the default is `127.0.0.1` loopback; exposing it is an operator decision)

## Design decisions and accepted risks

### Localhost-only API transport

The `blindtag-api` server binds to `127.0.0.1` (loopback) by default. This is an explicit design decision, not a gap:

- BlindTag is a local utility tool. No remote access is intended or supported in v1.
- The CORS middleware restricts origins to `localhost` and `127.0.0.1` only.
- Binding to `0.0.0.0` is possible by passing `--host 0.0.0.0` to `run_api.py`, but this is the operator's responsibility and is explicitly not recommended in untrusted network environments.

### No authentication on API endpoints

The API has no authentication layer. This is an accepted risk based on the localhost-only scope. If you integrate BlindTag into a multi-user or networked environment, you are responsible for adding an appropriate authentication layer upstream (reverse proxy, mTLS, etc.).

### No rate limiting

No rate limiting is implemented. The size limits enforced at the Pydantic validation layer (10 000 chars anchor, 1 000 chars payload, 50 000 chars raw decode input) provide the primary resource protection. Rate limiting is accepted as out-of-scope for a loopback utility tool in v1.
