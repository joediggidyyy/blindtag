"""
tests/test_reporting.py
=======================
Focused tests for BlindTag's retained reporting helpers.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from blindtag import reporting


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _configure_forensic_keys(monkeypatch, requester: str = "ops-user") -> Ed25519PrivateKey:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    monkeypatch.setenv("BLINDTAG_FORENSIC_SIGNING_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("BLINDTAG_FORENSIC_SIGNING_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("BLINDTAG_FORENSIC_SIGNING_KEY_ID", "ed25519-test-key")
    monkeypatch.setenv("BLINDTAG_FORENSIC_ALLOWED_REQUESTERS", requester)
    return private_key


def _sign_export_request(
    private_key: Ed25519PrivateKey,
    *,
    policy_mode: str,
    export_format: str,
    limit: int,
    requester_id: str,
    scope: str,
    expires_at: str,
    request_id: str | None = None,
    operation: str | None = None,
    level: str | None = None,
) -> str:
    canonical = reporting._signature_payload(
        export_format=export_format,
        policy_mode=policy_mode,
        request_id=request_id,
        operation=operation,
        level=level,
        limit=limit,
        requester_id=requester_id,
        scope=scope,
        expires_at=expires_at,
    )
    return private_key.sign(canonical.encode("utf-8")).hex()


def _append_sample_event(
    base_dir: Path,
    operation: str,
    request_id: str,
    **overrides,
) -> dict[str, object]:
    detail = overrides.pop("detail", f"{operation} completed.")
    reason = overrides.pop("reason", f"{operation}_test")
    record = reporting.build_event_record(
        surface="api",
        operation=operation,
        severity="info",
        outcome=f"{operation}_ok",
        detail=detail,
        request_id=request_id,
        anchor_length=5,
        payload_length=6,
        reason=reason,
        **overrides,
    )
    reporting.append_event(record, base_dir=base_dir)
    return record


class TestRetainedQuery:
    def test_query_returns_newest_first_with_filters(self, tmp_path: Path) -> None:
        first = _append_sample_event(tmp_path, "encode", "req-1")
        second = _append_sample_event(tmp_path, "decode", "req-2")

        newest = reporting.query_events(base_dir=tmp_path, limit=1)
        assert len(newest) == 1
        assert newest[0]["event_id"] == second["event_id"]

        filtered = reporting.query_events(base_dir=tmp_path, request_id="req-1", limit=5)
        assert len(filtered) == 1
        assert filtered[0]["event_id"] == first["event_id"]
        assert filtered[0]["operation"] == "encode"

    def test_query_supports_policy_mode_filter(self, tmp_path: Path, monkeypatch) -> None:
        _configure_forensic_keys(monkeypatch)
        _append_sample_event(tmp_path, "encode", "req-op")
        _append_sample_event(
            tmp_path,
            "transport",
            "req-forensic",
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=_sha256_text("archive.bin"),
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="received",
        )

        filtered = reporting.query_events(base_dir=tmp_path, policy_mode="forensic", limit=5)
        assert len(filtered) == 1
        assert filtered[0]["policy_mode"] == "forensic"
        assert filtered[0]["subject_kind"] == "archive_payload"


class TestRetainedExport:
    def test_json_export_writes_artifact_family_and_checksums(self, tmp_path: Path) -> None:
        _append_sample_event(tmp_path, "encode", "req-export-json")

        packet = reporting.export_events(
            export_format="json",
            base_dir=tmp_path,
            limit=10,
        )

        assert packet["decision"] == "export_written"
        payload_path = tmp_path / packet["artifact_family"]["payload"]
        manifest_path = tmp_path / packet["artifact_family"]["manifest"]
        checksums_path = tmp_path / packet["artifact_family"]["checksums"]
        assert payload_path.exists()
        assert manifest_path.exists()
        assert checksums_path.exists()
        payload_doc = json.loads(payload_path.read_text(encoding="utf-8"))
        assert payload_doc["record_count"] == 1
        assert packet["verification"]["payload_checksum"] is True
        assert packet["verification"]["manifest_checksum"] is True
        assert packet["verification"]["checksums_checksum"] is True
        assert packet["signature_state"]["configured"] is False

    def test_markdown_export_writes_readable_report(self, tmp_path: Path) -> None:
        _append_sample_event(tmp_path, "decode", "req-export-md")

        packet = reporting.export_events(
            export_format="markdown",
            base_dir=tmp_path,
            limit=10,
        )

        payload_path = tmp_path / packet["artifact_family"]["payload"]
        content = payload_path.read_text(encoding="utf-8")
        assert payload_path.suffix == ".md"
        assert "# BlindTag retained log export" in content
        assert "decode" in content

    def test_signed_export_requires_verified_request_and_emits_signature_sidecars(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        _append_sample_event(tmp_path, "encode", "req-signed")
        monkeypatch.setenv("BLINDTAG_EXPORT_SIGNING_KEY", "shared-secret")
        monkeypatch.setenv("BLINDTAG_EXPORT_SIGNING_KEY_ID", "test-key")
        monkeypatch.setenv("BLINDTAG_EXPORT_ALLOWED_REQUESTERS", "ops-user")

        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        canonical = reporting._signature_payload(
            export_format="json",
            policy_mode="operational",
            request_id=None,
            operation=None,
            level=None,
            limit=10,
            requester_id="ops-user",
            scope=reporting.EXPORT_SCOPE,
            expires_at=expires_at,
        )
        signature = hmac.new(
            b"shared-secret",
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        packet = reporting.export_events(
            export_format="json",
            base_dir=tmp_path,
            policy_mode="operational",
            limit=10,
            requester_id="ops-user",
            scope=reporting.EXPORT_SCOPE,
            expires_at=expires_at,
            signature=signature,
        )

        assert packet["signature_state"]["configured"] is True
        assert packet["signature_state"]["verification"] == "verified"
        assert packet["verification"]["signatures_verified"] is True
        assert len(packet["artifact_family"]["signature_sidecars"]) == 3


class TestHighTrustProvenance:
    def test_forensic_export_writes_chain_seal_and_sandbox_bundle(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        private_key = _configure_forensic_keys(monkeypatch)
        request_id = "handoff-001"
        source_sha = _sha256_text("payload.exe")
        derived_sha = _sha256_text("payload-unpacked.exe")

        received = _append_sample_event(
            tmp_path,
            "transport",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="received",
            detail="Archive payload received into sandbox.",
        )
        verified = _append_sample_event(
            tmp_path,
            "transport_verify",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="verified",
            parent_event_id=str(received["event_id"]),
            detail="Archive payload verified in sandbox.",
        )
        unpacked = _append_sample_event(
            tmp_path,
            "unpack",
            request_id,
            policy_mode="forensic",
            subject_kind="unpacked_executable",
            source_artifact_sha256=source_sha,
            derived_artifact_sha256=derived_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.UNPACK_SCOPE,
            action_phase="unpacked",
            parent_event_id=str(verified["event_id"]),
            detail="Executable payload unpacked inside sandbox.",
        )
        _append_sample_event(
            tmp_path,
            "release",
            request_id,
            policy_mode="forensic",
            subject_kind="unpacked_executable",
            source_artifact_sha256=source_sha,
            derived_artifact_sha256=derived_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.RELEASE_SCOPE,
            action_phase="released",
            parent_event_id=str(unpacked["event_id"]),
            detail="Executable payload handoff completed from sandbox.",
        )

        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        signature = _sign_export_request(
            private_key,
            policy_mode="forensic",
            export_format="json",
            limit=10,
            requester_id="ops-user",
            scope=reporting.FORENSIC_EXPORT_SCOPE,
            expires_at=expires_at,
            request_id=request_id,
        )

        packet = reporting.export_events(
            export_format="json",
            base_dir=tmp_path,
            request_id=request_id,
            policy_mode="forensic",
            limit=10,
            requester_id="ops-user",
            scope=reporting.FORENSIC_EXPORT_SCOPE,
            expires_at=expires_at,
            signature=signature,
        )

        assert packet["policy_mode"] == "forensic"
        assert packet["verification"]["chain_verified"] is True
        assert packet["verification"]["segment_seals_verified"] is True
        assert packet["verification"]["sandbox_content_verified"] is True
        assert packet["verification"]["handoff_posture_verified"] is True
        assert packet["signature_state"]["verification_profile"] == "ed25519_public_key"
        assert packet["sandbox_assessment"]["decision"] == "sandbox_verified"
        assert packet["sandbox_assessment"]["handoff_completion_posture"] == "complete"
        assert packet["sandbox_assessment"]["output_content_validation"]["required_provenance_fields_present"] is True
        assert packet["sandbox_assessment"]["output_content_validation"]["phase_sequence_present"] is True

        provenance_path = tmp_path / packet["artifact_family"]["supplemental"]["provenance_summary"]
        chain_path = tmp_path / packet["artifact_family"]["supplemental"]["chain_verification"]
        sandbox_path = tmp_path / packet["artifact_family"]["supplemental"]["sandbox_simulation"]
        segment_path = tmp_path / packet["artifact_family"]["supplemental"]["segment_seals"]
        assert provenance_path.exists()
        assert chain_path.exists()
        assert sandbox_path.exists()
        assert segment_path.exists()

        sandbox_doc = json.loads(sandbox_path.read_text(encoding="utf-8"))
        assert sandbox_doc["handoff_completion_posture"] == "complete"
        assert sandbox_doc["final_action_phase"] == "released"
        assert sandbox_doc["output_content_validation"]["segment_seals_valid"] is True

    def test_forensic_export_fails_when_chain_is_tampered(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        private_key = _configure_forensic_keys(monkeypatch)
        request_id = "tamper-001"
        source_sha = _sha256_text("payload.exe")

        _append_sample_event(
            tmp_path,
            "transport",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="received",
        )
        _append_sample_event(
            tmp_path,
            "transport_verify",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="verified",
        )

        ledger_path = reporting.operations_ledger_path(tmp_path)
        rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows[-1]["record_hash"] = "0" * 64
        ledger_path.write_text("\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        signature = _sign_export_request(
            private_key,
            policy_mode="forensic",
            export_format="json",
            limit=10,
            requester_id="ops-user",
            scope=reporting.FORENSIC_EXPORT_SCOPE,
            expires_at=expires_at,
            request_id=request_id,
        )

        with pytest.raises(reporting.ReportingError, match="chain verification failed"):
            reporting.export_events(
                export_format="json",
                base_dir=tmp_path,
                request_id=request_id,
                policy_mode="forensic",
                limit=10,
                requester_id="ops-user",
                scope=reporting.FORENSIC_EXPORT_SCOPE,
                expires_at=expires_at,
                signature=signature,
            )

    def test_high_trust_append_denies_unauthorized_executable_scope(self, tmp_path: Path) -> None:
        record = reporting.build_event_record(
            surface="api",
            operation="unpack",
            severity="warning",
            outcome="attempted_unpack",
            detail="Unauthorized unpack attempt.",
            request_id="blocked-001",
            policy_mode="security",
            subject_kind="unpacked_executable",
            source_artifact_sha256=_sha256_text("payload.exe"),
            derived_artifact_sha256=_sha256_text("payload-unpacked.exe"),
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="unpacked",
        )

        with pytest.raises(reporting.ReportingError, match="requires scope"):
            reporting.append_event(record, base_dir=tmp_path)

    def test_sandbox_assessment_reports_quarantined_posture(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        private_key = _configure_forensic_keys(monkeypatch)
        request_id = "quarantine-001"
        source_sha = _sha256_text("payload.exe")

        _append_sample_event(
            tmp_path,
            "transport",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="received",
        )
        _append_sample_event(
            tmp_path,
            "transport_verify",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            requester_id="ops-user",
            key_id="ed25519-test-key",
            scope=reporting.TRANSPORT_SCOPE,
            action_phase="verified",
        )
        _append_sample_event(
            tmp_path,
            "quarantine",
            request_id,
            policy_mode="forensic",
            subject_kind="archive_payload",
            source_artifact_sha256=source_sha,
            action_phase="quarantined",
            detail="Payload quarantined in sandbox.",
        )

        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        signature = _sign_export_request(
            private_key,
            policy_mode="forensic",
            export_format="json",
            limit=10,
            requester_id="ops-user",
            scope=reporting.FORENSIC_EXPORT_SCOPE,
            expires_at=expires_at,
            request_id=request_id,
        )

        packet = reporting.export_events(
            export_format="json",
            base_dir=tmp_path,
            request_id=request_id,
            policy_mode="forensic",
            limit=10,
            requester_id="ops-user",
            scope=reporting.FORENSIC_EXPORT_SCOPE,
            expires_at=expires_at,
            signature=signature,
        )

        assert packet["sandbox_assessment"]["handoff_completion_posture"] == "quarantined"
        assert packet["sandbox_assessment"]["handoff_verified"] is True
