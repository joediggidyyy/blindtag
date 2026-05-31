"""
blindtag.reporting
==================
Local retained reporting helpers for BlindTag.

Pass J established the first bounded retained-event substrate.
Pass R hardens that substrate with:

- explicit `operational` / `security` / `forensic` policy modes;
- provenance-grade event fields for elevated modes;
- deny-by-default executable handoff rules;
- tamper-evident record chaining and per-segment sealing;
- controlled JSON / Markdown export with checksum sidecars;
- privileged export verification with shared-key operational support and
  verifier-friendly Ed25519 verification for elevated modes;
- sandbox-simulated handoff assessment for elevated provenance exports.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from . import __version__

LOGGER = logging.getLogger(__name__)

REPORTING_RELATIVE_ROOT = Path(".blindtag") / "generated" / "reporting"
OPERATIONS_LEDGER_NAME = "operations.jsonl"
EXPORTS_DIRNAME = "exports"
SEALS_DIRNAME = "seals"
EXPORT_SCOPE = "blindtag.log.export"
SECURITY_EXPORT_SCOPE = "blindtag.log.export.security"
FORENSIC_EXPORT_SCOPE = "blindtag.log.export.forensic"
TRANSPORT_SCOPE = "blindtag.payload.transport"
UNPACK_SCOPE = "blindtag.payload.unpack"
RELEASE_SCOPE = "blindtag.payload.release"
DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200
MAX_EXPORT_LIMIT = 500
_ALLOWED_SEVERITIES = {"debug", "info", "warning", "error", "critical"}
POLICY_MODES = {"operational", "security", "forensic"}
HIGH_TRUST_MODES = {"security", "forensic"}
SUBJECT_KINDS = {
    "text_payload",
    "binary_payload",
    "archive_payload",
    "executable_payload",
    "unpacked_executable",
}
ACTION_PHASES = {
    "received",
    "verified",
    "exported",
    "blocked",
    "quarantined",
    "unpacked",
    "released",
}
EXECUTABLE_SUBJECT_KINDS = {"archive_payload", "executable_payload", "unpacked_executable"}
NON_TERMINAL_PHASES = {"received", "verified", "unpacked"}
TERMINAL_PHASES = {"exported", "blocked", "quarantined", "released"}
EXPORT_SCOPES = {
    "operational": EXPORT_SCOPE,
    "security": SECURITY_EXPORT_SCOPE,
    "forensic": FORENSIC_EXPORT_SCOPE,
}
SANDBOX_NAME = "simulated-elevated-provenance"
SEGMENT_VERSION = "blindtag_segment_seal_v1"
FORENSIC_BUNDLE_FAMILY = "blindtag_forensic_bundle_v1"
DEFAULT_HOST_CONTEXT = f"blindtag-local:{socket.gethostname()}"


class ReportingError(RuntimeError):
    """Base exception for retained reporting failures."""


class PathContainmentError(ReportingError):
    """Raised when a derived path escapes the reporting root."""


class ExportAuthorizationError(ReportingError):
    """Raised when a privileged export request fails verification."""


def _normalize_choice(name: str, value: Optional[str], allowed: set[str]) -> Optional[str]:
    """Normalize a string choice against an allowed vocabulary."""
    if value is None:
        return None
    normalized = value.lower().strip()
    if normalized not in allowed:
        raise ReportingError(f"unsupported {name}: {value!r}")
    return normalized


def _validate_sha256(name: str, value: Optional[str]) -> Optional[str]:
    """Validate a hexadecimal SHA-256 digest when provided."""
    if value is None:
        return None
    normalized = value.lower().strip()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ReportingError(f"{name} must be a 64-character hexadecimal SHA-256 digest")
    return normalized


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
    seals_root = _ensure_contained(root / SEALS_DIRNAME, root)
    seals_root.mkdir(parents=True, exist_ok=True)
    return root


def operations_ledger_path(base_dir: Optional[Path | str] = None) -> Path:
    """Return the append-only retained operations ledger path."""
    root = ensure_reporting_layout(base_dir)
    return _ensure_contained(root / OPERATIONS_LEDGER_NAME, root)


def _seals_root(base_dir: Optional[Path | str] = None) -> Path:
    """Return the segment-seal directory."""
    root = ensure_reporting_layout(base_dir)
    return _ensure_contained(root / SEALS_DIRNAME, root)


def _segment_seal_path(segment_id: str, base_dir: Optional[Path | str] = None) -> Path:
    """Return the seal path for one segment identifier."""
    return _ensure_contained(_seals_root(base_dir) / f"{segment_id}.json", get_reporting_root(base_dir))


def _default_session_id(request_id: Optional[str]) -> str:
    """Return a stable session label for retained event records."""
    return request_id or f"blindtag-session-{uuid.uuid4().hex[:12]}"


def _current_segment_id(recorded_at: str, policy_mode: str) -> str:
    """Return the segment identifier for one retained record."""
    return f"{policy_mode}-{recorded_at.split('T', 1)[0].replace('-', '')}"


def _canonical_json(data: Any) -> str:
    """Return canonical JSON for hashing and signature payloads."""
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _record_hash_payload(record: dict[str, Any]) -> bytes:
    """Return the canonical bytes used for a record hash."""
    payload = dict(record)
    payload.pop("record_hash", None)
    return _canonical_json(payload).encode("utf-8")


def _compute_record_hash(record: dict[str, Any]) -> str:
    """Return the stable record hash for one retained event."""
    return _sha256_hex(_record_hash_payload(record))


def _expected_scope_for_subject(subject_kind: str, action_phase: Optional[str]) -> Optional[str]:
    """Return the required scope for an executable-related provenance record."""
    if subject_kind not in EXECUTABLE_SUBJECT_KINDS or action_phase is None:
        return None
    if action_phase in {"received", "verified", "exported"}:
        return TRANSPORT_SCOPE
    if action_phase == "unpacked":
        return UNPACK_SCOPE
    if action_phase == "released":
        return RELEASE_SCOPE
    return None


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Apply default values and normalize one retained record."""
    normalized = dict(record)
    normalized.setdefault("recorded_at", utc_now_iso())
    normalized.setdefault("event_id", str(uuid.uuid4()))
    normalized.setdefault("surface", "library")
    normalized.setdefault("request_id", None)
    normalized.setdefault("policy_mode", "operational")
    normalized.setdefault("subject_kind", "text_payload")
    normalized.setdefault("source_artifact_sha256", None)
    normalized.setdefault("derived_artifact_sha256", None)
    normalized.setdefault("parent_event_id", None)
    normalized.setdefault("requester_id", None)
    normalized.setdefault("key_id", None)
    normalized.setdefault("scope", None)
    normalized.setdefault("action_phase", None)
    normalized.setdefault("tool_version", __version__)
    normalized.setdefault("session_id", _default_session_id(normalized.get("request_id")))
    normalized.setdefault("host_context", DEFAULT_HOST_CONTEXT)
    normalized.setdefault("reason", None)
    normalized.setdefault("previous_record_hash", None)
    normalized.setdefault("record_hash", None)
    normalized.setdefault("segment_id", None)
    normalized["severity"] = _normalize_choice("severity", str(normalized["severity"]), _ALLOWED_SEVERITIES)  # type: ignore[index]
    normalized["policy_mode"] = _normalize_choice("policy_mode", str(normalized["policy_mode"]), POLICY_MODES)  # type: ignore[index]
    normalized["subject_kind"] = _normalize_choice("subject_kind", str(normalized["subject_kind"]), SUBJECT_KINDS)  # type: ignore[index]
    normalized["action_phase"] = _normalize_choice("action_phase", normalized.get("action_phase"), ACTION_PHASES)
    normalized["source_artifact_sha256"] = _validate_sha256("source_artifact_sha256", normalized.get("source_artifact_sha256"))
    normalized["derived_artifact_sha256"] = _validate_sha256("derived_artifact_sha256", normalized.get("derived_artifact_sha256"))
    if not normalized.get("detail"):
        raise ReportingError("retained event detail must be a non-empty string")
    return normalized


def _validate_high_trust_record(record: dict[str, Any]) -> None:
    """Fail closed if a security/forensic record is incomplete or unauthorized."""
    policy_mode = str(record.get("policy_mode"))
    if policy_mode not in HIGH_TRUST_MODES:
        return

    if not record.get("action_phase"):
        raise ReportingError("security/forensic records must declare action_phase")
    if not record.get("tool_version") or not record.get("host_context"):
        raise ReportingError(
            "security/forensic records must declare tool_version and host_context"
        )

    subject_kind = str(record.get("subject_kind"))
    action_phase = str(record.get("action_phase"))
    expected_scope = _expected_scope_for_subject(subject_kind, action_phase)

    if subject_kind in EXECUTABLE_SUBJECT_KINDS and not record.get("source_artifact_sha256"):
        raise ReportingError(
            "security/forensic executable provenance records require source_artifact_sha256"
        )

    if expected_scope is not None:
        if not record.get("requester_id") or not record.get("key_id"):
            raise ReportingError(
                "security/forensic executable provenance records require requester_id and key_id"
            )
        if record.get("scope") != expected_scope:
            raise ReportingError(
                f"security/forensic executable provenance requires scope {expected_scope!r}"
            )
        if action_phase in {"unpacked", "released"} and not record.get("derived_artifact_sha256"):
            raise ReportingError(
                f"action_phase {action_phase!r} requires derived_artifact_sha256"
            )


def _latest_record_hash(records: list[dict[str, Any]], policy_mode: str) -> Optional[str]:
    """Return the last chained record hash for one policy mode."""
    for candidate in reversed(records):
        if candidate.get("policy_mode") != policy_mode:
            continue
        if candidate.get("record_hash"):
            return str(candidate["record_hash"])
    return None


def _seal_signing_private_key() -> Optional[Ed25519PrivateKey]:
    """Return the configured Ed25519 private key for elevated export/seal signing."""
    raw = os.getenv("BLINDTAG_FORENSIC_SIGNING_PRIVATE_KEY", "").strip()
    if not raw:
        return None
    key = serialization.load_pem_private_key(raw.encode("utf-8"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ReportingError("BLINDTAG_FORENSIC_SIGNING_PRIVATE_KEY must be an Ed25519 private key")
    return key


def _seal_verification_public_key() -> Optional[Ed25519PublicKey]:
    """Return the configured Ed25519 public key for elevated request/export verification."""
    raw = os.getenv("BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY", "").strip()
    if not raw:
        return None
    key = serialization.load_pem_public_key(raw.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ReportingError("BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY must be an Ed25519 public key")
    return key


def _forensic_key_id() -> str:
    """Return the names-only key identifier for elevated provenance signing."""
    value = os.getenv("BLINDTAG_FORENSIC_SIGNING_KEY_ID", "configured-ed25519-key").strip()
    return value or "configured-ed25519-key"


def _forensic_allowed_requesters() -> list[str]:
    """Return the configured requester allowlist for elevated exports."""
    raw = os.getenv("BLINDTAG_FORENSIC_ALLOWED_REQUESTERS", "")
    return [token.strip() for token in raw.split(",") if token.strip()]


def _sign_blob_public_key(content: bytes, private_key: Ed25519PrivateKey) -> str:
    """Return a detached Ed25519 signature encoded as hex."""
    return private_key.sign(content).hex()


def _verify_blob_public_key(content: bytes, signature: str, public_key: Ed25519PublicKey) -> bool:
    """Verify a detached Ed25519 signature encoded as hex."""
    try:
        public_key.verify(bytes.fromhex(signature), content)
    except Exception:
        return False
    return True


def _seal_payload(records: list[dict[str, Any]], segment_id: str, policy_mode: str) -> dict[str, Any]:
    """Return the canonical unsigned payload for one segment seal."""
    record_hashes = [str(record.get("record_hash")) for record in records]
    return {
        "segment_version": SEGMENT_VERSION,
        "segment_id": segment_id,
        "policy_mode": policy_mode,
        "record_count": len(records),
        "first_event_id": records[0]["event_id"],
        "last_event_id": records[-1]["event_id"],
        "first_record_hash": records[0]["record_hash"],
        "last_record_hash": records[-1]["record_hash"],
        "segment_digest": _sha256_hex(_canonical_json(record_hashes).encode("utf-8")),
        "sealed_at": utc_now_iso(),
    }


def _write_segment_seal(record: dict[str, Any], base_dir: Optional[Path | str] = None) -> None:
    """Write or refresh the seal for one elevated provenance segment."""
    policy_mode = str(record["policy_mode"])
    if policy_mode not in HIGH_TRUST_MODES:
        return

    private_key = _seal_signing_private_key()
    public_key = _seal_verification_public_key()
    if private_key is None or public_key is None:
        raise ReportingError(
            "security/forensic mode requires BLINDTAG_FORENSIC_SIGNING_PRIVATE_KEY and "
            "BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY"
        )

    segment_id = str(record["segment_id"])
    segment_records = [
        item for item in _load_events(base_dir)
        if item.get("segment_id") == segment_id and item.get("policy_mode") == policy_mode
    ]
    if not segment_records:
        raise ReportingError(f"cannot seal empty segment {segment_id!r}")

    payload = _seal_payload(segment_records, segment_id, policy_mode)
    signature = _sign_blob_public_key(_canonical_json(payload).encode("utf-8"), private_key)
    doc = {
        **payload,
        "signature": signature,
        "verification_profile": "ed25519_public_key",
        "key_id": _forensic_key_id(),
    }
    path = _segment_seal_path(segment_id, base_dir)
    _write_text(path, json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")


def summarize_provenance(
    records: list[dict[str, Any]],
    *,
    policy_mode: str,
) -> dict[str, Any]:
    """Return a concise provenance summary for an elevated export bundle."""
    source_hashes = sorted({str(item["source_artifact_sha256"]) for item in records if item.get("source_artifact_sha256")})
    derived_hashes = sorted({str(item["derived_artifact_sha256"]) for item in records if item.get("derived_artifact_sha256")})
    return {
        "policy_mode": policy_mode,
        "record_count": len(records),
        "subject_kinds": sorted({str(item["subject_kind"]) for item in records}),
        "action_phases": [str(item.get("action_phase")) for item in records if item.get("action_phase")],
        "request_ids": sorted({str(item["request_id"]) for item in records if item.get("request_id")}),
        "requester_ids": sorted({str(item["requester_id"]) for item in records if item.get("requester_id")}),
        "key_ids": sorted({str(item["key_id"]) for item in records if item.get("key_id")}),
        "scopes": sorted({str(item["scope"]) for item in records if item.get("scope")}),
        "source_artifact_sha256": source_hashes,
        "derived_artifact_sha256": derived_hashes,
        "high_trust_record_count": len([item for item in records if item.get("policy_mode") in HIGH_TRUST_MODES]),
        "executable_record_count": len([item for item in records if item.get("subject_kind") in EXECUTABLE_SUBJECT_KINDS]),
    }


def verify_record_chain(
    *,
    base_dir: Optional[Path | str] = None,
    policy_mode: Optional[str] = None,
    records: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Verify high-trust record hashes and previous-hash links."""
    selected_mode = _normalize_choice("policy_mode", policy_mode, POLICY_MODES) if policy_mode else None
    source_records = list(records) if records is not None else _load_events(base_dir)
    relevant = [
        item for item in source_records
        if item.get("policy_mode") in HIGH_TRUST_MODES and (selected_mode is None or item.get("policy_mode") == selected_mode)
    ]

    previous_by_mode: dict[str, Optional[str]] = {}
    failures: list[str] = []
    inspected = 0
    for item in relevant:
        inspected += 1
        mode = str(item["policy_mode"])
        expected_previous = previous_by_mode.get(mode)
        actual_previous = item.get("previous_record_hash")
        expected_hash = _compute_record_hash(item)
        actual_hash = item.get("record_hash")
        if actual_previous != expected_previous:
            failures.append(
                f"event {item['event_id']} previous_record_hash mismatch"
            )
        if actual_hash != expected_hash:
            failures.append(f"event {item['event_id']} record_hash mismatch")
        previous_by_mode[mode] = str(actual_hash) if actual_hash else None

    return {
        "valid": not failures,
        "policy_mode": selected_mode,
        "records_inspected": inspected,
        "failures": failures,
    }


def verify_segment_seals(
    *,
    base_dir: Optional[Path | str] = None,
    policy_mode: Optional[str] = None,
    records: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Verify elevated provenance segment seals."""
    selected_mode = _normalize_choice("policy_mode", policy_mode, POLICY_MODES) if policy_mode else None
    source_records = list(records) if records is not None else _load_events(base_dir)
    relevant = [
        item for item in source_records
        if item.get("policy_mode") in HIGH_TRUST_MODES and (selected_mode is None or item.get("policy_mode") == selected_mode)
    ]

    public_key = _seal_verification_public_key()
    failures: list[str] = []
    segments: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in relevant:
        segment_id = str(item.get("segment_id") or "")
        if not segment_id:
            failures.append(f"event {item['event_id']} missing segment_id")
            continue
        grouped.setdefault(segment_id, []).append(item)

    for segment_id, items in grouped.items():
        seal_path = _segment_seal_path(segment_id, base_dir)
        if not seal_path.exists():
            failures.append(f"segment seal missing for {segment_id}")
            continue
        seal_doc = json.loads(seal_path.read_text(encoding="utf-8"))
        payload = _seal_payload(items, segment_id, str(items[0]["policy_mode"]))
        expected_signature = seal_doc.get("signature")
        if seal_doc.get("record_count") != payload["record_count"]:
            failures.append(f"segment {segment_id} record_count mismatch")
        if seal_doc.get("segment_digest") != payload["segment_digest"]:
            failures.append(f"segment {segment_id} digest mismatch")
        if seal_doc.get("first_record_hash") != payload["first_record_hash"]:
            failures.append(f"segment {segment_id} first_record_hash mismatch")
        if seal_doc.get("last_record_hash") != payload["last_record_hash"]:
            failures.append(f"segment {segment_id} last_record_hash mismatch")
        if public_key is None:
            failures.append("BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY is required for segment verification")
        elif not isinstance(expected_signature, str) or not _verify_blob_public_key(
            _canonical_json(payload).encode("utf-8"),
            expected_signature,
            public_key,
        ):
            failures.append(f"segment {segment_id} signature verification failed")
        segments.append(
            {
                "segment_id": segment_id,
                "record_count": payload["record_count"],
                "policy_mode": payload["policy_mode"],
                "seal_path": _relative_to_project(seal_path, base_dir),
                "verified": True,
            }
        )

    return {
        "valid": not failures,
        "policy_mode": selected_mode,
        "segments": segments,
        "failures": failures,
    }


def _required_provenance_fields_present(record: dict[str, Any]) -> bool:
    """Return True when the expected provenance fields are present for one record."""
    policy_mode = str(record.get("policy_mode"))
    if policy_mode not in HIGH_TRUST_MODES:
        return True
    if not record.get("action_phase") or not record.get("tool_version") or not record.get("host_context"):
        return False
    subject_kind = str(record.get("subject_kind"))
    expected_scope = _expected_scope_for_subject(subject_kind, record.get("action_phase"))
    if subject_kind in EXECUTABLE_SUBJECT_KINDS and not record.get("source_artifact_sha256"):
        return False
    if expected_scope is not None:
        if not record.get("requester_id") or not record.get("key_id") or record.get("scope") != expected_scope:
            return False
        if record.get("action_phase") in {"unpacked", "released"} and not record.get("derived_artifact_sha256"):
            return False
    return True


def evaluate_sandbox_handoff(
    *,
    records: list[dict[str, Any]],
    policy_mode: str,
    chain_verification: dict[str, Any],
    seal_verification: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate elevated-mode output content and handoff posture in a sandbox model."""
    sorted_records = list(records)
    final_phase = next(
        (str(item["action_phase"]) for item in reversed(sorted_records) if item.get("action_phase")),
        None,
    )
    subject_kinds = {str(item["subject_kind"]) for item in sorted_records}
    executable_subject = any(subject in EXECUTABLE_SUBJECT_KINDS for subject in subject_kinds)
    phases = [str(item["action_phase"]) for item in sorted_records if item.get("action_phase")]
    required_fields_present = all(_required_provenance_fields_present(item) for item in sorted_records)
    expected_sequence = ["received", "verified"]
    if executable_subject and final_phase not in {"blocked", "quarantined"}:
        expected_sequence.append("unpacked")
        expected_terminal = {"released", "blocked", "quarantined"}
    else:
        expected_terminal = {"exported", "blocked", "quarantined"}

    sequence_complete = all(phase in phases for phase in expected_sequence)
    if executable_subject and final_phase == "released":
        posture = "complete" if sequence_complete and "released" in phases else "incomplete"
    elif final_phase in {"blocked", "quarantined"}:
        posture = final_phase
    elif final_phase == "exported" and not executable_subject:
        posture = "complete" if sequence_complete else "incomplete"
    else:
        posture = "incomplete"

    output_content_validation = {
        "required_provenance_fields_present": required_fields_present,
        "chain_valid": bool(chain_verification.get("valid")),
        "segment_seals_valid": bool(seal_verification.get("valid")),
        "phase_sequence_present": sequence_complete,
        "terminal_phase_present": final_phase in expected_terminal if final_phase else False,
        "records_present": bool(sorted_records),
    }
    handoff_verified = all(bool(value) for value in output_content_validation.values()) and posture in {
        "complete",
        "blocked",
        "quarantined",
    }
    return {
        "decision": "sandbox_verified" if handoff_verified else "sandbox_failed",
        "sandbox_name": SANDBOX_NAME,
        "policy_mode": policy_mode,
        "execution_mode": "simulated",
        "network_posture": "disabled",
        "filesystem_posture": "temporary",
        "records_evaluated": len(sorted_records),
        "subject_kinds": sorted(subject_kinds),
        "phase_sequence": phases,
        "expected_sequence": expected_sequence,
        "final_action_phase": final_phase,
        "handoff_completion_posture": posture,
        "output_content_validation": output_content_validation,
        "handoff_verified": handoff_verified,
    }


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
    policy_mode: str = "operational",
    subject_kind: str = "text_payload",
    source_artifact_sha256: Optional[str] = None,
    derived_artifact_sha256: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    requester_id: Optional[str] = None,
    key_id: Optional[str] = None,
    scope: Optional[str] = None,
    action_phase: Optional[str] = None,
    tool_version: Optional[str] = None,
    session_id: Optional[str] = None,
    host_context: Optional[str] = None,
) -> dict[str, Any]:
    """Build one stable retained event record."""
    record = {
        "recorded_at": utc_now_iso(),
        "event_id": str(uuid.uuid4()),
        "request_id": request_id,
        "surface": surface,
        "operation": operation,
        "severity": severity,
        "decision": outcome,
        "outcome": outcome,
        "anchor_length": anchor_length,
        "payload_length": payload_length,
        "resolved_token_count": resolved_token_count,
        "error_type": error_type,
        "detail": detail,
        "reason": reason,
        "policy_mode": policy_mode,
        "subject_kind": subject_kind,
        "source_artifact_sha256": source_artifact_sha256,
        "derived_artifact_sha256": derived_artifact_sha256,
        "parent_event_id": parent_event_id,
        "requester_id": requester_id,
        "key_id": key_id,
        "scope": scope,
        "action_phase": action_phase,
        "tool_version": tool_version or __version__,
        "session_id": session_id or _default_session_id(request_id),
        "host_context": host_context or DEFAULT_HOST_CONTEXT,
        "previous_record_hash": None,
        "record_hash": None,
        "segment_id": None,
    }
    return _normalize_record(record)


def append_event(record: dict[str, Any], base_dir: Optional[Path | str] = None) -> str:
    """Append one structured event to the JSONL ledger and return its path."""
    normalized = _normalize_record(record)
    _validate_high_trust_record(normalized)

    ledger_records = _load_events(base_dir)
    policy_mode = str(normalized["policy_mode"])
    if policy_mode in HIGH_TRUST_MODES:
        normalized["previous_record_hash"] = _latest_record_hash(ledger_records, policy_mode)
        normalized["segment_id"] = _current_segment_id(str(normalized["recorded_at"]), policy_mode)
        normalized["record_hash"] = _compute_record_hash(normalized)

    ledger_path = operations_ledger_path(base_dir)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=True, sort_keys=True))
        handle.write("\n")
    if policy_mode in HIGH_TRUST_MODES:
        _write_segment_seal(normalized, base_dir)
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
    policy_mode: Optional[str] = None,
    action_phase: Optional[str] = None,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[dict[str, Any]]:
    """Return the newest retained events matching the provided filters."""
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise ReportingError(
            f"log query limit must be between 1 and {MAX_QUERY_LIMIT}"
        )

    normalized_level = _normalize_choice("log level filter", level, _ALLOWED_SEVERITIES) if level else None
    normalized_mode = _normalize_choice("policy_mode", policy_mode, POLICY_MODES) if policy_mode else None
    normalized_phase = _normalize_choice("action_phase", action_phase, ACTION_PHASES) if action_phase else None

    filtered: list[dict[str, Any]] = []
    for event in reversed(_load_events(base_dir)):
        if request_id and event.get("request_id") != request_id:
            continue
        if operation and event.get("operation") != operation:
            continue
        if normalized_level and event.get("severity") != normalized_level:
            continue
        if normalized_mode and event.get("policy_mode") != normalized_mode:
            continue
        if normalized_phase and event.get("action_phase") != normalized_phase:
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
    policy_mode: str,
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
        "policy_mode": policy_mode,
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
    policy_mode: str,
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
    normalized_mode = _normalize_choice("policy_mode", policy_mode, POLICY_MODES)
    expected_scope = EXPORT_SCOPES[normalized_mode]

    if normalized_mode in HIGH_TRUST_MODES:
        public_key = _seal_verification_public_key()
        if public_key is None:
            raise ExportAuthorizationError(
                "security/forensic export requires BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY"
            )

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
                "high-trust export is missing: " + ", ".join(missing)
            )

        assert requester_id is not None
        assert scope is not None
        assert expires_at is not None
        assert signature is not None
        if scope != expected_scope:
            raise ExportAuthorizationError(
                f"export request scope must be {expected_scope!r}, received {scope!r}"
            )
        allowlist = _forensic_allowed_requesters()
        if allowlist and requester_id not in allowlist:
            raise ExportAuthorizationError(
                f"requester_id {requester_id!r} is not in the configured forensic allowlist"
            )
        try:
            parsed_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ExportAuthorizationError("expires_at must be a valid ISO-8601 timestamp") from exc
        if parsed_expiry.tzinfo is None:
            parsed_expiry = parsed_expiry.replace(tzinfo=timezone.utc)
        if parsed_expiry <= datetime.now(timezone.utc):
            raise ExportAuthorizationError("export request has expired")

        canonical = _signature_payload(
            export_format=export_format,
            policy_mode=normalized_mode,
            request_id=request_id,
            operation=operation,
            level=level,
            limit=limit,
            requester_id=requester_id,
            scope=scope,
            expires_at=expires_at,
        ).encode("utf-8")
        if not _verify_blob_public_key(canonical, signature, public_key):
            raise ExportAuthorizationError("export request signature verification failed")
        return {
            "configured": True,
            "verification": "verified",
            "key_id": _forensic_key_id(),
            "requester_id": requester_id,
            "scope": scope,
            "allowlist_applied": bool(allowlist),
            "expires_at": expires_at,
            "verification_profile": "ed25519_public_key",
            "policy_mode": normalized_mode,
        }

    key = _signature_key()
    if key is None:
        return {
            "configured": False,
            "verification": "not_configured",
            "key_id": None,
            "requester_id": None,
            "scope": expected_scope,
            "allowlist_applied": False,
            "expires_at": None,
            "verification_profile": "not_configured",
            "policy_mode": normalized_mode,
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

    if scope != expected_scope:
        raise ExportAuthorizationError(
            f"export request scope must be {expected_scope!r}, received {scope!r}"
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
            policy_mode=normalized_mode,
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
        "verification_profile": "shared_key_hmac",
        "policy_mode": normalized_mode,
    }


def _artifact_signing_state(policy_mode: str) -> dict[str, Any]:
    """Return internal signing state for export artifacts."""
    normalized_mode = _normalize_choice("policy_mode", policy_mode, POLICY_MODES)
    if normalized_mode in HIGH_TRUST_MODES:
        private_key = _seal_signing_private_key()
        public_key = _seal_verification_public_key()
        if private_key is None or public_key is None:
            raise ReportingError(
                "security/forensic export signing requires BLINDTAG_FORENSIC_SIGNING_PRIVATE_KEY and BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY"
            )
        return {
            "configured": True,
            "verification_profile": "ed25519_public_key",
            "key_id": _forensic_key_id(),
            "private_key": private_key,
            "public_key": public_key,
        }

    shared_key = _signature_key()
    if shared_key is None:
        return {
            "configured": False,
            "verification_profile": "not_configured",
            "key_id": None,
            "shared_key": None,
        }
    return {
        "configured": True,
        "verification_profile": "shared_key_hmac",
        "key_id": _signature_key_id(),
        "shared_key": shared_key,
    }


def _sign_artifact(path: Path, signing_state: dict[str, Any]) -> str:
    """Write the detached signature for one artifact and return the path name."""
    signature_path = path.with_name(f"{path.name}.sig")
    if signing_state["verification_profile"] == "ed25519_public_key":
        signature = _sign_blob_public_key(path.read_bytes(), signing_state["private_key"])
    else:
        signature = _sign_blob(path.read_bytes(), signing_state["shared_key"])
    _write_text(signature_path, signature + "\n")
    return signature_path.name


def _verify_artifact_signature(path: Path, signing_state: dict[str, Any]) -> bool:
    """Verify the detached signature for one artifact."""
    signature_path = path.with_name(f"{path.name}.sig")
    if not signature_path.exists():
        return False
    signature = signature_path.read_text(encoding="utf-8").strip()
    if signing_state["verification_profile"] == "ed25519_public_key":
        return _verify_blob_public_key(path.read_bytes(), signature, signing_state["public_key"])
    expected_signature = _sign_blob(path.read_bytes(), signing_state["shared_key"])
    return hmac.compare_digest(expected_signature, signature)


def _render_markdown(
    *,
    export_id: str,
    generated_at: str,
    filters: dict[str, Any],
    records: list[dict[str, Any]],
    policy_mode: str,
) -> str:
    """Render a simple retained-event Markdown report."""
    lines = [
        "# BlindTag retained log export",
        "",
        f"- export_id: {export_id}",
        f"- generated_at: {generated_at}",
        f"- policy_mode: {policy_mode}",
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
            "| recorded_at | request_id | policy_mode | subject_kind | operation | phase | severity | outcome | detail |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in records:
        lines.append(
            "| {recorded_at} | {request_id} | {policy_mode} | {subject_kind} | {operation} | {action_phase} | {severity} | {outcome} | {detail} |".format(
                recorded_at=str(record.get("recorded_at", "")),
                request_id=str(record.get("request_id", "") or "-"),
                policy_mode=str(record.get("policy_mode", "")),
                subject_kind=str(record.get("subject_kind", "")),
                operation=str(record.get("operation", "")),
                action_phase=str(record.get("action_phase", "") or "-"),
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
    policy_mode: str = "operational",
    action_phase: Optional[str] = None,
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
    normalized_mode = _normalize_choice("policy_mode", policy_mode, POLICY_MODES)

    signature_state = authorize_export(
        export_format=normalized_format,
        policy_mode=normalized_mode,
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
        policy_mode=normalized_mode,
        action_phase=action_phase,
        limit=min(limit, MAX_QUERY_LIMIT),
    )
    if normalized_mode in HIGH_TRUST_MODES:
        records = list(reversed(records))

    chain_verification = {"valid": True, "policy_mode": normalized_mode, "records_inspected": 0, "failures": []}
    segment_verification = {"valid": True, "policy_mode": normalized_mode, "segments": [], "failures": []}
    sandbox_summary: Optional[dict[str, Any]] = None
    provenance_summary: Optional[dict[str, Any]] = None
    segment_seals_payload: Optional[dict[str, Any]] = None
    if normalized_mode in HIGH_TRUST_MODES:
        chain_verification = verify_record_chain(records=records, policy_mode=normalized_mode, base_dir=base_dir)
        if not chain_verification["valid"]:
            raise ReportingError("elevated provenance chain verification failed before export")
        segment_verification = verify_segment_seals(records=records, policy_mode=normalized_mode, base_dir=base_dir)
        if not segment_verification["valid"]:
            raise ReportingError("elevated provenance segment seal verification failed before export")
        provenance_summary = summarize_provenance(records, policy_mode=normalized_mode)
        sandbox_summary = evaluate_sandbox_handoff(
            records=records,
            policy_mode=normalized_mode,
            chain_verification=chain_verification,
            seal_verification=segment_verification,
        )
        segment_seals_payload = {
            "policy_mode": normalized_mode,
            "segments": segment_verification["segments"],
        }

    generated_at = utc_now_iso()
    export_id = f"export-{generated_at.replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
    root = ensure_reporting_layout(base_dir)
    export_dir = _ensure_contained(root / EXPORTS_DIRNAME / export_id, root)
    export_dir.mkdir(parents=True, exist_ok=False)

    filters = {
        "request_id": request_id,
        "operation": operation,
        "level": level,
        "policy_mode": normalized_mode,
        "action_phase": action_phase,
        "limit": limit,
    }
    payload_name = "export.json" if normalized_format == "json" else "export.md"
    payload_path = _ensure_contained(export_dir / payload_name, root)
    artifact_paths: list[Path] = []

    if normalized_format == "json":
        payload_doc = {
            "generated_at": generated_at,
            "export_id": export_id,
            "format": normalized_format,
            "policy_mode": normalized_mode,
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
                policy_mode=normalized_mode,
            ),
        )
    artifact_paths.append(payload_path)

    supplemental_paths: dict[str, Path] = {}
    if provenance_summary is not None:
        provenance_path = _ensure_contained(export_dir / "provenance_summary.json", root)
        _write_text(provenance_path, json.dumps(provenance_summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        supplemental_paths["provenance_summary"] = provenance_path
        artifact_paths.append(provenance_path)
    if segment_seals_payload is not None:
        segment_seals_path = _ensure_contained(export_dir / "segment_seals.json", root)
        _write_text(segment_seals_path, json.dumps(segment_seals_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        supplemental_paths["segment_seals"] = segment_seals_path
        artifact_paths.append(segment_seals_path)
    if sandbox_summary is not None:
        sandbox_path = _ensure_contained(export_dir / "sandbox_simulation.json", root)
        _write_text(sandbox_path, json.dumps(sandbox_summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        supplemental_paths["sandbox_simulation"] = sandbox_path
        artifact_paths.append(sandbox_path)
    if normalized_mode in HIGH_TRUST_MODES:
        chain_path = _ensure_contained(export_dir / "chain_verification.json", root)
        _write_text(chain_path, json.dumps(chain_verification, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
        supplemental_paths["chain_verification"] = chain_path
        artifact_paths.append(chain_path)

    manifest_path = _ensure_contained(export_dir / "manifest.json", root)
    signing_state = _artifact_signing_state(normalized_mode)
    primary_names = [path.name for path in artifact_paths]
    signature_file_names = [f"{name}.sig" for name in ([*primary_names, "manifest.json", "checksums.json"])] if signing_state["configured"] else []
    manifest_doc = {
        "generated_at": generated_at,
        "export_id": export_id,
        "artifact_family": FORENSIC_BUNDLE_FAMILY if normalized_mode in HIGH_TRUST_MODES else "blindtag_reporting_export_v1",
        "format": normalized_format,
        "policy_mode": normalized_mode,
        "record_count": len(records),
        "filters": filters,
        "files": [
            *primary_names,
            "manifest.json",
            "checksums.json",
            *(f"{name}.sha256" for name in [*primary_names, "manifest.json", "checksums.json"]),
            *signature_file_names,
        ],
        "signature_state": {
            "configured": signature_state["configured"],
            "verification": signature_state["verification"],
            "key_id": signature_state["key_id"],
            "requester_id": signature_state["requester_id"],
            "scope": signature_state["scope"],
            "allowlist_applied": signature_state["allowlist_applied"],
            "verification_profile": signature_state["verification_profile"],
        },
    }
    _write_text(manifest_path, json.dumps(manifest_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    checksums_path = _ensure_contained(export_dir / "checksums.json", root)
    primary_paths = [*artifact_paths, manifest_path]
    checksums_map = {path.name: _sha256_hex(path.read_bytes()) for path in primary_paths}
    checksums_doc = {
        "generated_at": generated_at,
        "export_id": export_id,
        "policy_mode": normalized_mode,
        "checksums": checksums_map,
        "signatures_configured": signing_state["configured"],
        "verification_profile": signing_state["verification_profile"],
    }
    _write_text(checksums_path, json.dumps(checksums_doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    all_primary_paths = [*artifact_paths, manifest_path, checksums_path]
    checksum_sidecars = [_write_sidecar(path, _sha256_hex(path.read_bytes())) for path in all_primary_paths]
    signature_files: list[str] = []
    if signing_state["configured"]:
        signature_files = [_sign_artifact(path, signing_state) for path in all_primary_paths]

    checksum_sidecars_verified = all(
        _sha256_hex(path.read_bytes()) == _parse_sidecar(path.with_name(f"{path.name}.sha256"))
        for path in all_primary_paths
    )
    checksums_doc_after = json.loads(checksums_path.read_text(encoding="utf-8"))
    checksum_manifest_match = all(
        checksums_doc_after["checksums"].get(path.name) == _sha256_hex(path.read_bytes())
        for path in primary_paths
    )
    signatures_verified = True
    if signing_state["configured"]:
        signatures_verified = all(_verify_artifact_signature(path, signing_state) for path in all_primary_paths)

    verification = {
        "payload_checksum": _sha256_hex(payload_path.read_bytes()) == _parse_sidecar(payload_path.with_name(f"{payload_path.name}.sha256")),
        "manifest_checksum": _sha256_hex(manifest_path.read_bytes()) == _parse_sidecar(manifest_path.with_name(f"{manifest_path.name}.sha256")),
        "checksums_checksum": _sha256_hex(checksums_path.read_bytes()) == _parse_sidecar(checksums_path.with_name(f"{checksums_path.name}.sha256")),
        "checksum_sidecars_verified": checksum_sidecars_verified,
        "checksums_manifest_match": checksum_manifest_match,
        "signatures_verified": signatures_verified,
        "chain_verified": bool(chain_verification.get("valid")),
        "segment_seals_verified": bool(segment_verification.get("valid")),
        "sandbox_content_verified": bool(sandbox_summary["output_content_validation"]["required_provenance_fields_present"]) if sandbox_summary else True,
        "handoff_posture_verified": bool(sandbox_summary["handoff_verified"]) if sandbox_summary else True,
    }

    if not all(bool(value) for value in verification.values()):
        raise ReportingError("export artifact family verification failed after write")

    LOGGER.info("BlindTag retained export written to %s", export_dir)
    return {
        "decision": "export_written",
        "detail": f"Export wrote {len(records)} retained records as {normalized_format}.",
        "export_id": export_id,
        "format": normalized_format,
        "policy_mode": normalized_mode,
        "record_count": len(records),
        "filters": filters,
        "artifact_family": {
            "payload": _relative_to_project(payload_path, base_dir),
            "manifest": _relative_to_project(manifest_path, base_dir),
            "checksums": _relative_to_project(checksums_path, base_dir),
            "checksum_sidecars": [
                _relative_to_project(path, base_dir) for path in checksum_sidecars
            ],
            "signature_sidecars": [
                _relative_to_project(export_dir / name, base_dir) for name in signature_files
            ],
            "supplemental": {
                key: _relative_to_project(path, base_dir)
                for key, path in supplemental_paths.items()
            },
        },
        "signature_state": signature_state,
        "verification": verification,
        "sandbox_assessment": sandbox_summary,
        "next_action": (
            f"Review {_relative_to_project(payload_path, base_dir)} and "
            f"{_relative_to_project(manifest_path, base_dir)} for retained evidence details."
        ),
    }
