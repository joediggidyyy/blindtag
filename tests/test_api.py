"""
tests/test_api.py
=================
Integration tests for the BlindTag FastAPI endpoints.

Uses FastAPI's synchronous TestClient (wraps httpx), so no async
test infrastructure is required. The full ASGI app is exercised
end-to-end including Pydantic validation and exception handlers.

Run with:
    pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from blindtag.api import MAX_HIDDEN_CHARS, MAX_RAW_TEXT_CHARS, app
from blindtag.core import decode
from blindtag import reporting

client = TestClient(app, raise_server_exceptions=True)


def _sha256_text(value: str) -> str:
    import hashlib

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
) -> str:
    canonical = reporting._signature_payload(
        export_format=export_format,
        policy_mode=policy_mode,
        request_id=request_id,
        operation=None,
        level=None,
        limit=limit,
        requester_id=requester_id,
        scope=scope,
        expires_at=expires_at,
    )
    return private_key.sign(canonical.encode("utf-8")).hex()


@pytest.fixture(autouse=True)
def isolate_reporting_root(tmp_path: Path):
    previous = getattr(app.state, "reporting_base_dir", None)
    app.state.reporting_base_dir = tmp_path
    yield tmp_path
    if previous is None:
        delattr(app.state, "reporting_base_dir")
    else:
        app.state.reporting_base_dir = previous


# =============================================================================
# Health endpoint
# =============================================================================

class TestHealthEndpoint:

    def test_health_ok(self) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "BlindTag API"
        assert body["version"] == "1.0.0"


# =============================================================================
# POST /v1/encode
# =============================================================================

class TestEncodeEndpoint:

    def test_basic_encode_returns_200(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "Hello, World!", "hidden_message": "secret"},
        )
        assert r.status_code == 200

    def test_encode_response_schema(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "Hello", "hidden_message": "world"},
        )
        body = r.json()
        assert "result" in body
        assert body["anchor_length"] == len("Hello")
        assert body["payload_length"] == len("world")
        assert body["total_length"] == len(body["result"])

    def test_result_is_decodable(self) -> None:
        """The API-encoded string must be decodable by the core engine."""
        r = client.post(
            "/v1/encode",
            json={"anchor": "cover text", "hidden_message": "API_PAYLOAD_42"},
        )
        result = r.json()["result"]
        assert decode(result) == "API_PAYLOAD_42"

    def test_result_longer_than_anchor(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "short", "hidden_message": "x"},
        )
        body = r.json()
        assert body["total_length"] > body["anchor_length"]

    def test_non_ascii_payload_rejected_422(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "cover", "hidden_message": "café"},
        )
        assert r.status_code == 422

    def test_control_char_payload_rejected_422(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "cover", "hidden_message": "bad\x01char"},
        )
        assert r.status_code == 422

    def test_empty_payload_rejected_422(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "cover", "hidden_message": ""},
        )
        assert r.status_code == 422

    def test_empty_anchor_rejected_422(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "", "hidden_message": "payload"},
        )
        assert r.status_code == 422

    def test_oversized_payload_rejected_422(self) -> None:
        r = client.post(
            "/v1/encode",
            json={
                "anchor": "cover",
                "hidden_message": "A" * (MAX_HIDDEN_CHARS + 1),
            },
        )
        assert r.status_code == 422

    def test_full_printable_ascii_payload_accepted(self) -> None:
        payload = "".join(chr(c) for c in range(0x20, 0x7F))
        r = client.post(
            "/v1/encode",
            json={"anchor": "full ASCII test", "hidden_message": payload},
        )
        assert r.status_code == 200
        assert decode(r.json()["result"]) == payload

    def test_emoji_anchor_accepted(self) -> None:
        r = client.post(
            "/v1/encode",
            json={"anchor": "🔐 Secure msg 🌐", "hidden_message": "emoji_anchor"},
        )
        assert r.status_code == 200


# =============================================================================
# POST /v1/decode
# =============================================================================

class TestDecodeEndpoint:

    def _encode_via_api(self, anchor: str, hidden: str) -> str:
        r = client.post("/v1/encode", json={"anchor": anchor, "hidden_message": hidden})
        return r.json()["result"]

    def test_decode_finds_payload(self) -> None:
        encoded = self._encode_via_api("cover text", "found_it")
        r = client.post("/v1/decode", json={"raw_text": encoded})
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["message"] == "found_it"

    def test_decode_response_schema(self) -> None:
        encoded = self._encode_via_api("anchor", "schema_check")
        r = client.post("/v1/decode", json={"raw_text": encoded})
        body = r.json()
        assert "found" in body
        assert "message" in body
        assert "detail" in body

    def test_decode_round_trip_api(self) -> None:
        """Full API round-trip: encode endpoint → decode endpoint."""
        payload = "ROUND_TRIP:OK:2024"
        encoded = self._encode_via_api("cover string", payload)
        r = client.post("/v1/decode", json={"raw_text": encoded})
        assert r.json()["message"] == payload

    def test_decode_no_payload_returns_found_false(self) -> None:
        r = client.post(
            "/v1/decode",
            json={"raw_text": "This is plain text with no hidden content."},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False
        assert body["message"] is None

    def test_decode_empty_raw_text_rejected_422(self) -> None:
        r = client.post("/v1/decode", json={"raw_text": ""})
        assert r.status_code == 422

    def test_decode_oversized_raw_text_rejected_422(self) -> None:
        r = client.post(
            "/v1/decode",
            json={"raw_text": "A" * (MAX_RAW_TEXT_CHARS + 1)},
        )
        assert r.status_code == 422

    def test_decode_emoji_anchor_extracts_correctly(self) -> None:
        encoded = self._encode_via_api("🔐 Secure channel 🌐", "emoji_ok")
        r = client.post("/v1/decode", json={"raw_text": encoded})
        assert r.json()["message"] == "emoji_ok"

    def test_decode_detail_message_on_success(self) -> None:
        encoded = self._encode_via_api("anchor", "detail_test")
        r = client.post("/v1/decode", json={"raw_text": encoded})
        assert "extracted" in r.json()["detail"].lower()

    def test_decode_detail_message_on_miss(self) -> None:
        r = client.post("/v1/decode", json={"raw_text": "clean text"})
        assert "no" in r.json()["detail"].lower()


# =============================================================================
# CORS policy
# =============================================================================

class TestCorsPolicy:
    """
    CORS is restricted to localhost loopback origins only.
    Preflight OPTIONS requests from allowed origins must return
    Access-Control-Allow-Origin; external origins must not be reflected.
    """

    def test_cors_allowed_origin_localhost(self) -> None:
        r = client.options(
            "/v1/encode",
            headers={
                "Origin": "http://localhost",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert r.headers.get("access-control-allow-origin") == "http://localhost"

    def test_cors_allowed_origin_127(self) -> None:
        r = client.options(
            "/v1/encode",
            headers={
                "Origin": "http://127.0.0.1",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1"

    def test_cors_external_origin_not_reflected(self) -> None:
        """External origins must not appear in the allow-origin header."""
        r = client.options(
            "/v1/encode",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        origin_header = r.headers.get("access-control-allow-origin", "")
        assert "evil.example.com" not in origin_header

    def test_cors_simple_get_health_allowed_origin(self) -> None:
        """Simple GET to /health from an allowed origin gets ACAO header."""
        r = client.get("/health", headers={"Origin": "http://localhost:8000"})
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"


# =============================================================================
# Security headers
# =============================================================================

import re as _re

_UUID4_RE = _re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class TestSecurityHeaders:
    """Every response must carry X-Content-Type-Options, X-Frame-Options, X-Request-Id."""

    def test_x_content_type_options_on_health(self) -> None:
        r = client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options_on_health(self) -> None:
        r = client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY"

    def test_x_request_id_on_health(self) -> None:
        r = client.get("/health")
        val = r.headers.get("x-request-id", "")
        assert _UUID4_RE.match(val), f"x-request-id not a UUID4: {val!r}"

    def test_x_content_type_options_on_encode(self) -> None:
        r = client.post("/v1/encode", json={"anchor": "test", "hidden_message": "hdr"})
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options_on_encode(self) -> None:
        r = client.post("/v1/encode", json={"anchor": "test", "hidden_message": "hdr"})
        assert r.headers.get("x-frame-options") == "DENY"

    def test_x_request_id_unique_per_request(self) -> None:
        r1 = client.get("/health")
        r2 = client.get("/health")
        id1 = r1.headers.get("x-request-id", "")
        id2 = r2.headers.get("x-request-id", "")
        assert _UUID4_RE.match(id1) and _UUID4_RE.match(id2)
        assert id1 != id2

    def test_security_headers_on_error_response(self) -> None:
        r = client.post("/v1/encode", json={"anchor": "", "hidden_message": ""})
        assert r.status_code == 422
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"


class TestReportingEndpoints:

    def test_log_query_returns_retained_item_for_request_id(self) -> None:
        encode_response = client.post(
            "/v1/encode",
            json={"anchor": "query anchor", "hidden_message": "query_payload"},
        )
        request_id = encode_response.headers["x-request-id"]

        query_response = client.get("/v1/log", params={"request_id": request_id})
        assert query_response.status_code == 200
        body = query_response.json()
        assert body["count"] == 1
        assert body["items"][0]["request_id"] == request_id
        assert body["items"][0]["operation"] == "encode"
        assert body["items"][0]["outcome"] == "payload_encoded"

    def test_log_export_writes_artifact_family_under_reporting_root(self, tmp_path: Path) -> None:
        client.post(
            "/v1/encode",
            json={"anchor": "export anchor", "hidden_message": "export_payload"},
        )

        export_response = client.post(
            "/v1/log/export",
            json={"format": "json", "limit": 10},
        )
        assert export_response.status_code == 200
        body = export_response.json()
        assert body["decision"] == "export_written"
        payload_path = tmp_path / body["artifact_family"]["payload"]
        manifest_path = tmp_path / body["artifact_family"]["manifest"]
        checksums_path = tmp_path / body["artifact_family"]["checksums"]
        assert payload_path.exists()
        assert manifest_path.exists()
        assert checksums_path.exists()
        assert body["verification"]["payload_checksum"] is True
        assert body["verification"]["manifest_checksum"] is True
        assert body["verification"]["checksums_checksum"] is True

    def test_log_export_fails_closed_when_signing_is_configured_without_request_material(
        self,
        monkeypatch,
    ) -> None:
        client.post(
            "/v1/encode",
            json={"anchor": "signed export", "hidden_message": "payload"},
        )
        monkeypatch.setenv("BLINDTAG_EXPORT_SIGNING_KEY", "shared-secret")

        export_response = client.post(
            "/v1/log/export",
            json={"format": "json", "limit": 10},
        )
        assert export_response.status_code == 403
        assert "missing" in export_response.json()["detail"].lower()

    def test_log_export_forensic_mode_writes_sandbox_assessment(self, tmp_path: Path, monkeypatch) -> None:
        private_key = _configure_forensic_keys(monkeypatch)
        request_id = "api-forensic-001"
        source_sha = _sha256_text("payload.exe")
        derived_sha = _sha256_text("payload-unpacked.exe")

        for operation, subject_kind, phase, scope, derived in (
            ("transport", "archive_payload", "received", reporting.TRANSPORT_SCOPE, None),
            ("transport_verify", "archive_payload", "verified", reporting.TRANSPORT_SCOPE, None),
            ("unpack", "unpacked_executable", "unpacked", reporting.UNPACK_SCOPE, derived_sha),
            ("release", "unpacked_executable", "released", reporting.RELEASE_SCOPE, derived_sha),
        ):
            record = reporting.build_event_record(
                surface="api",
                operation=operation,
                severity="info",
                outcome=f"{operation}_ok",
                detail=f"{operation} completed in sandbox.",
                request_id=request_id,
                policy_mode="forensic",
                subject_kind=subject_kind,
                source_artifact_sha256=source_sha,
                derived_artifact_sha256=derived,
                requester_id="ops-user",
                key_id="ed25519-test-key",
                scope=scope,
                action_phase=phase,
            )
            reporting.append_event(record, base_dir=tmp_path)

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

        export_response = client.post(
            "/v1/log/export",
            json={
                "format": "json",
                "policy_mode": "forensic",
                "request_id": request_id,
                "limit": 10,
                "requester_id": "ops-user",
                "scope": reporting.FORENSIC_EXPORT_SCOPE,
                "expires_at": expires_at,
                "signature": signature,
            },
        )
        assert export_response.status_code == 200
        body = export_response.json()
        assert body["policy_mode"] == "forensic"
        assert body["verification"]["chain_verified"] is True
        assert body["verification"]["segment_seals_verified"] is True
        assert body["verification"]["handoff_posture_verified"] is True
        assert body["sandbox_assessment"]["handoff_completion_posture"] == "complete"
        sandbox_path = tmp_path / body["artifact_family"]["supplemental"]["sandbox_simulation"]
        assert sandbox_path.exists()

    def test_log_export_forensic_mode_fails_without_public_key_material(self) -> None:
        export_response = client.post(
            "/v1/log/export",
            json={
                "format": "json",
                "policy_mode": "forensic",
                "limit": 10,
                "requester_id": "ops-user",
                "scope": reporting.FORENSIC_EXPORT_SCOPE,
                "expires_at": "2099-01-01T00:00:00Z",
                "signature": "00",
            },
        )
        assert export_response.status_code == 403
        assert "public_key" in export_response.json()["detail"].lower()
