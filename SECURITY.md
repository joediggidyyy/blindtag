# Security Policy

BlindTag is maintained by [Polymath](https://polymath-global.com).

## Supported versions

| Version | Supported |
|---------|-----------|
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

## Disclosure policy

We follow responsible disclosure. Once a fix is released, we will publish a summary in [CHANGELOG.md](CHANGELOG.md). Credit will be given to reporters unless anonymity is requested.
