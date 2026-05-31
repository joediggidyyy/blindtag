"""
blindtag.reporting
==================
Local retained reporting helpers for BlindTag.

Pass J establishes one append-only JSONL ledger as the first retained
reporting authority. The helpers in this module provide:

- structured event creation;
- append-only writes to `.blindtag/generated/reporting/operations.jsonl`;
- filtered read-only queries;
- controlled JSON / Markdown export with checksum sidecars;
- optional detached-signature verification for export operations when
  shared-key signing is explicitly configured.

The module intentionally uses only the Python standard library.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)

REPORTING_RELATIVE_ROOT = Path(".blindtag") / "generated" / "reporting"
OPERATIONS_LEDGER_NAME = "operations.jsonl"
EXPORTS_DIRNAME = "exports"
EXPORT_SCOPE = "blindtag.log.export"
DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200
MAX_EXPORT_LIMIT = 500
_ALLOWED_SEVERITIES = {"debug", "info", "warning", "error", "critical"}


class ReportingError(RuntimeError):
    """Base exception for retained reporting failures."""


class PathContainmentError(ReportingError):
    """Raised when a derived path escapes the reporting root."""


class ExportAuthorizationError(ReportingError):
    """Raised when a privileged export request fails verification."""


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with a ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_root(base_dir: Optional[Path | str] = None) -> Path:
    """Resolve the current project root for reporting operations."""
    return Path.cwd().resolve() if base_dir is None else Path(base_dir).resolve()


def get_reporting_root(base_dir: Optional[Path | str] = None) -> Path:
    """Return the canonical retained reporting root."""
    root = (_project_root(base_dir) / REPORTING_RELATIVE_ROOT).resolve()
    return root


def _ensure_contained(path: Path, root: Path) -> Path:
    """Fail closed if *path* escapes *root*."""
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathContainmentError(
            f"derived reporting path escapes the retained root: {resolved}"
        ) from exc
    return resolved


def _relative_to_project(path: Path, base_dir: Optional[Path | str] = None) -> str:
    """Return a project-relative POSIX path for user-facing responses."""
    return _ensure_contained(path, _project_root(base_dir)).relative_to(_project_root(base_dir)).as_posix()


def ensure_reporting_layout(base_dir: Optional[Path | str] = None) -> Path:
    """Create the retained reporting directory tree if needed."""
    root = get_reporting_root(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    exports_root = _ensure_contained(root / EXPORTS_DIRNAME, root)
    exports_root.mkdir(parents=True, exist_ok=True)
    return root


def operations_ledger_path(base_dir: Optional[Path | str] = None) -> Path:
    """Return the append-only retained operations ledger path."""
    root = ensure_reporting_layout(base_dir)
    return _ensure_contained(root / OPERATIONS_LEDGER_NAME, root)


def build_event_record(
    *,
    surface: str,
    operation: str,
    severity: str,
    outcome: str,
    detail: str,
    request_id: Optional[str] = None,
    anchor_length: Optional[int] = None,
    payload_length: Optional[int] = None,
    resolved_token_count: Optional[int] = None,
    error_type: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Build one stable retained event record."""
    normalized_severity = severity.lower().strip()
    if normalized_severity not in _ALLOWED_SEVERITIES:
        raise ReportingError(f"unsupported severity: {severity!r}")

    return {
        "recorded_at": utc_now_iso(),
        "event_id": str(uuid.uuid4()),
        "request_id": request_id,
        "surface": surface,
        "operation": operation,
        "severity": normalized_severity,
        "decision": outcome,
        "outcome": outcome,
        "anchor_length": anchor_length,
        "payload_length": payload_length,
        "resolved_token_count": resolved_token_count,
        "error_type": error_type,
        "detail": detail,
        "reason": reason,
    }


def append_event(record: dict[str, Any], base_dir: Optional[Path | str] = None) -> str:
    """Append one structured event to the JSONL ledger and return its path."""
    ledger_path = operations_ledger_path(base_dir)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True))
        handle.write("\n")
    LOGGER.debug("Appended BlindTag retained event to %s", ledger_path)
    return _relative_to_project(ledger_path, base_dir)


def _load_events(base_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Load retained events from the append-only ledger."""
    ledger_path = operations_ledger_path(base_dir)
    if not ledger_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReportingError(
                    f"retained operations ledger is invalid at line {line_number}"
                ) from exc
            if not isinstance(parsed, dict):
                raise ReportingError(
                    f"retained operations ledger contains a non-object row at line {line_number}"
                )
            records.append(parsed)
    return records


def query_events(
    *,
    base_dir: Optional[Path | str] = None,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[dict[str, Any]]:
    """Return the newest retained events matching the provided filters."""
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise ReportingError(
            f"log query limit must be between 1 and {MAX_QUERY_LIMIT}"
        )

    normalized_level = level.lower().strip() if level else None
    if normalized_level is not None and normalized_level not in _ALLOWED_SEVERITIES:
        raise ReportingError(f"unsupported log level filter: {level!r}")

    filtered: list[dict[str, Any]] = []
    for event in reversed(_load_events(base_dir)):
        if request_id and event.get("request_id") != request_id:
            continue
        if operation and event.get("operation") != operation:
            continue
        if normalized_level and event.get("severity") != normalized_level:
            continue
        filtered.append(event)
        if len(filtered) >= limit:
            break
    return filtered


def _sha256_hex(data: bytes) -> str:
    """Return the SHA-256 digest for *data*."""
    return hashlib.sha256(data).hexdigest()


def _write_text(path: Path, content: str) -> None:
    """Write UTF-8 text with normalized newlines."""
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_sidecar(path: Path, digest: str) -> Path:
    """Write a simple detached SHA-256 sidecar next to *path*."""
    sidecar = path.with_name(f"{path.name}.sha256")
    _write_text(sidecar, f"{digest}  {path.name}\n")
    return sidecar


def _parse_sidecar(path: Path) -> str:
    """Parse a ``.sha256`` sidecar and return the digest token."""
    content = path.read_text(encoding="utf-8").strip()
    digest = content.split()[0] if content else ""
    if len(digest) != 64:
        raise ReportingError(f"invalid checksum sidecar for {path.name}")
    return digest


def _signature_key() -> Optional[str]:
    """Return the optional shared-key signing secret."""
    value = os.getenv("BLINDTAG_EXPORT_SIGNING_KEY", "").strip()
    return value or None


def _signature_key_id() -> str:
    """Return a names-only key identifier for export signing."""
    return os.getenv("BLINDTAG_EXPORT_SIGNING_KEY_ID", "configured-shared-key").strip() or "configured-shared-key"


def _allowed_requesters() -> list[str]:
    """Return the configured requester allowlist, if any."""
    raw = os.getenv("BLINDTAG_EXPORT_ALLOWED_REQUESTERS", "")
    return [token.strip() for token in raw.split(",") if token.strip()]


def _signature_payload(
    *,
    export_format: str,
    request_id: Optional[str],
    operation: Optional[str],
    level: Optional[str],
    limit: int,
    requester_id: str,
    scope: str,
    expires_at: str,
) -> str:
    """Return the canonical authorization payload string."""
    payload = {
        "expires_at": expires_at,
        "format": export_format,
        "level": level,
        "limit": limit,
        "operation": operation,
        "request_id": request_id,
        "requester_id": requester_id,
        "scope": scope,
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sign_blob(content: bytes, key: str) -> str:
    """Return a detached HMAC-SHA256 signature for *content*."""
    return hmac.new(key.encode("utf-8"), content, hashlib.sha256).hexdigest()


def authorize_export(
    *,
    export_format: str,
    request_id: Optional[str],
    operation: Optional[str],
    level: Optional[str],
    limit: int,
    requester_id: Optional[str],
    scope: Optional[str],
    expires_at: Optional[str],
    signature: Optional[str],
) -> dict[str, Any]:
    """Verify a privileged export request when signing is configured."""
    key = _signature_key()
    if key is None:
        return {
            "configured": False,
            "verification": "not_configured",
            "key_id": None,
            "requester_id": None,
            "scope": None,
            "allowlist_applied": False,
        }

    missing: list[str] = []
    for field_name, value in (
        ("requester_id", requester_id),
        ("scope", scope),
        ("expires_at", expires_at),
        ("signature", signature),
    ):
        if value is None or not str(value).strip():
            missing.append(field_name)
    if missing:
        raise ExportAuthorizationError(
            "export signing is configured but the privileged request is missing: "
            + ", ".join(missing)
        )

    assert requester_id is not None
    assert scope is not None
    assert expires_at is not None
    assert signature is not None

    if scope != EXPORT_SCOPE:
        raise ExportAuthorizationError(
            f"export request scope must be {EXPORT_SCOPE!r}, received {scope!r}"
        )

    allowlist = _allowed_requesters()
    if allowlist and requester_id not in allowlist:
        raise ExportAuthorizationError(
            f"requester_id {requester_id!r} is not in the configured export allowlist"
        )

    try:
        parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExportAuthorizationError("expires_at must be a valid ISO-8601 timestamp") from exc
    if parsed_expiry.tzinfo is None:
        parsed_expiry = parsed_expiry.replace(tzinfo=timezone.utc)
    if parsed_expiry <= datetime.now(timezone.utc):
        raise ExportAuthorizationError("export request has expired")

    expected = _sign_blob(
        _signature_payload(
            export_format=export_format,
            request_id=request_id,
            operation=operation,
            level=level,
            limit=limit,
            requester_id=requester_id,
            scope=scope,
            expires_at=expires_at,
        ).encode("utf-8"),
        key,
    )
    if not hmac.compare_digest(expected, signature):
        raise ExportAuthorizationError("export request signature verification failed")

    return {
        "configured": True,
        "verification": "verified",
        "key_id": _signature_key_id(),
        "requester_id": requester_id,
        "scope": scope,
        "allowlist_applied": bool(allowlist),
        "expires_at": expires_at,
    }


def _render_markdown(
    *,
    export_id: str,
    generated_at: str,
    filters: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    """Render a simple retained-event Markdown report."""
    lines = [
        "# BlindTag retained log export",
        "",
        f"- export_id: {export_id}",
        f"- generated_at: {generated_at}",
        f"- record_count: {len(records)}",
        f"- filters: {json.dumps(filters, ensure_ascii=True, sort_keys=True)}",
        "",
        "## Records",
        "",
    ]
    if not records:
        lines.append("No retained events matched the requested filters.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| recorded_at | request_id | surface | operation | severity | outcome | detail |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in records:
        lines.append(
            "| {recorded_at} | {request_id} | {surface} | {operation} | {severity} | {outcome} | {detail} |".format(
                recorded_at=str(record.get("recorded_at", "")),
                request_id=str(record.get("request_id", "") or "-"),
                surface=str(record.get("surface", "")),
                operation=str(record.get("operation", "")),
                severity=str(record.get("severity", "")),
                outcome=str(record.get("outcome", "")),
                detail=str(record.get("detail", "")).replace("|", "\\|"),
            )
        )
    return "\n".join(lines) + "\n"


def export_events(
    *,
    export_format: str,
    base_dir: Optional[Path | str] = None,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = DEFAULT_QUERY_LIMIT,
    requester_id: Optional[str] = None,
    scope: Optional[str] = None,
    expires_at: Optional[str] = None,
    signature: Optional[str] = None,
) -> dict[str, Any]:
    """Export filtered retained events into a controlled artifact family."""
    normalized_format = export_format.lower().strip()
    if normalized_format not in {"json", "markdown"}:
        raise ReportingError("export format must be 'json' or 'markdown'")
    if limit < 1 or limit > MAX_EXPORT_LIMIT:
        raise ReportingError(
            f"export limit must be between 1 and {MAX_EXPORT_LIMIT}"
        )

    signature_state = authorize_export(
        export_format=normalized_format,
        request_id=request_id,
        operation=operation,
        level=level,
        limit=limit,
        requester_id=requester_id,
        scope=scope,
        expires_at=expires_at,
        signature=signature,
    )

    records = query_events(
        base_dir=base_dir,
        request_id=request_id,
        operation=operation,
        level=level,
        limit=min(limit, MAX_QUERY_LIMIT),
    )
    generated_at = utc_now_iso()
    export_id = f"export-{generated_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    root = ensure_reporting_layout(base_dir)
    export_dir = _ensure_contained(root / EXPORTS_DIRNAME / export_id, root)
    export_dir.mkdir(parents=True, exist_ok=False)

    filters = {
        "request_id": request_id,
        "operation": operation,
        "level": level,
        "limit": limit,
    }
    payload_name = "export.json" if normalized_format == "json" else "export.md"
    payload_path = _ensure_contained(export_dir / payload_name, root)

    if normalized_format == "json":
        payload_doc = {
            "generated_at": generated_at,
            "export_id": export_id,
            "format": normalized_format,
            "filters": filters,
            "record_count": len(records),
            "items": records,
        }
        _write_text(payload_path, json.dumps(payload_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    else:
        _write_text(
            payload_path,
            _render_markdown(
                export_id=export_id,
                generated_at=generated_at,
                filters=filters,
                records=records,
            ),
        )

    manifest_path = _ensure_contained(export_dir / "manifest.json", root)
    manifest_doc = {
        "generated_at": generated_at,
        "export_id": export_id,
        "artifact_family": "blindtag_reporting_export_v1",
        "format": normalized_format,
        "record_count": len(records),
        "filters": filters,
        "files": [
            payload_name,
            "manifest.json",
            "checksums.json",
            f"{payload_name}.sha256",
            "manifest.json.sha256",
            "checksums.json.sha256",
        ],
        "signature_state": {
            "configured": signature_state["configured"],
            "verification": signature_state["verification"],
            "key_id": signature_state["key_id"],
            "requester_id": signature_state["requester_id"],
            "scope": signature_state["scope"],
            "allowlist_applied": signature_state["allowlist_applied"],
        },
    }
    _write_text(manifest_path, json.dumps(manifest_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    payload_sha = _sha256_hex(payload_path.read_bytes())
    manifest_sha = _sha256_hex(manifest_path.read_bytes())
    checksums_path = _ensure_contained(export_dir / "checksums.json", root)
    checksums_doc = {
        "generated_at": generated_at,
        "export_id": export_id,
        "checksums": {
            payload_name: payload_sha,
            "manifest.json": manifest_sha,
        },
        "signatures_configured": signature_state["configured"],
    }
    _write_text(checksums_path, json.dumps(checksums_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    checksums_sha = _sha256_hex(checksums_path.read_bytes())

    payload_sha_path = _write_sidecar(payload_path, payload_sha)
    manifest_sha_path = _write_sidecar(manifest_path, manifest_sha)
    checksums_sha_path = _write_sidecar(checksums_path, checksums_sha)

    signature_files: list[str] = []
    if signature_state["configured"]:
        signature_files = [
            f"{payload_path.name}.sig",
            f"{manifest_path.name}.sig",
            f"{checksums_path.name}.sig",
        ]
        manifest_doc["files"].extend(signature_files)
        _write_text(manifest_path, json.dumps(manifest_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        manifest_sha = _sha256_hex(manifest_path.read_bytes())
        _write_text(manifest_sha_path, f"{manifest_sha}  {manifest_path.name}\n")
        checksums_doc["checksums"]["manifest.json"] = manifest_sha
        _write_text(checksums_path, json.dumps(checksums_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        checksums_sha = _sha256_hex(checksums_path.read_bytes())
        _write_text(checksums_sha_path, f"{checksums_sha}  {checksums_path.name}\n")

        key = _signature_key()
        assert key is not None
        for artifact_path in (payload_path, manifest_path, checksums_path):
            signature_path = artifact_path.with_name(f"{artifact_path.name}.sig")
            _write_text(signature_path, _sign_blob(artifact_path.read_bytes(), key) + "\n")

    verification = {
        "payload_checksum": payload_sha == _parse_sidecar(payload_sha_path),
        "manifest_checksum": manifest_sha == _parse_sidecar(manifest_sha_path),
        "checksums_checksum": checksums_sha == _parse_sidecar(checksums_sha_path),
        "checksums_manifest_match": json.loads(checksums_path.read_text(encoding="utf-8"))["checksums"]["manifest.json"] == manifest_sha,
        "checksums_payload_match": json.loads(checksums_path.read_text(encoding="utf-8"))["checksums"][payload_name] == payload_sha,
        "signatures_verified": not signature_state["configured"],
    }

    if signature_state["configured"]:
        key = _signature_key()
        assert key is not None
        signature_results: list[bool] = []
        for artifact_path in (payload_path, manifest_path, checksums_path):
            signature_path = artifact_path.with_name(f"{artifact_path.name}.sig")
            expected_signature = _sign_blob(artifact_path.read_bytes(), key)
            actual_signature = signature_path.read_text(encoding="utf-8").strip()
            signature_results.append(hmac.compare_digest(expected_signature, actual_signature))
        verification["signatures_verified"] = all(signature_results)

    if not all(bool(value) for value in verification.values()):
        raise ReportingError("export artifact family verification failed after write")

    LOGGER.info("BlindTag retained export written to %s", export_dir)
    return {
        "decision": "export_written",
        "detail": f"Export wrote {len(records)} retained records as {normalized_format}.",
        "export_id": export_id,
        "format": normalized_format,
        "record_count": len(records),
        "filters": filters,
        "artifact_family": {
            "payload": _relative_to_project(payload_path, base_dir),
            "manifest": _relative_to_project(manifest_path, base_dir),
            "checksums": _relative_to_project(checksums_path, base_dir),
            "checksum_sidecars": [
                _relative_to_project(payload_sha_path, base_dir),
                _relative_to_project(manifest_sha_path, base_dir),
                _relative_to_project(checksums_sha_path, base_dir),
            ],
            "signature_sidecars": [
                _relative_to_project(export_dir / name, base_dir) for name in signature_files
            ],
        },
        "signature_state": signature_state,
        "verification": verification,
        "next_action": (
            f"Review {_relative_to_project(payload_path, base_dir)} and "
            f"{_relative_to_project(manifest_path, base_dir)} for retained evidence details."
        ),
    }
