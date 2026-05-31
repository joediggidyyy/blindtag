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

from blindtag.api import MAX_HIDDEN_CHARS, MAX_RAW_TEXT_CHARS, app
from blindtag.core import decode

client = TestClient(app, raise_server_exceptions=True)


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
