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

from blindtag.api import MAX_HIDDEN_CHARS, MAX_RAW_TEXT_CHARS, app
from blindtag.core import decode

client = TestClient(app, raise_server_exceptions=True)


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
