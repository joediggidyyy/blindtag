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

from blindtag import reporting


def _append_sample_event(base_dir: Path, operation: str, request_id: str) -> dict[str, object]:
    record = reporting.build_event_record(
        surface="api",
        operation=operation,
        severity="info",
        outcome=f"{operation}_ok",
        detail=f"{operation} completed.",
        request_id=request_id,
        anchor_length=5,
        payload_length=6,
        reason=f"{operation}_test",
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
