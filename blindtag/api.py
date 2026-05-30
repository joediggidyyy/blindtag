"""
blindtag.api
============
Secure local transport layer for BlindTag encode/decode operations.

Architecture
------------
A lightweight FastAPI ASGI application with two functional endpoints:

  POST /v1/encode  — Embeds a hidden ASCII payload into visible cover text.
  POST /v1/decode  — Extracts any Plane 14 tag payload from a raw string.

Security Model
--------------
• Payload size limits are enforced at the Pydantic validation layer BEFORE
  any codec logic executes — preventing memory pressure from oversized inputs.
• Non-ASCII characters in hidden_message are rejected at the schema level,
  providing a second defence layer on top of the core engine's own checks.
• All exceptions from the core engine are caught and surfaced as structured
  JSON error responses — no stack traces leak to callers.
• Intended for localhost-only use; CORS is restricted accordingly.

Running the server
------------------
  python run_api.py
  # or:
  uvicorn blindtag.api:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .core import decode, encode
from .exceptions import InvalidPayloadError

# ─── Payload size policy ──────────────────────────────────────────────────────

MAX_ANCHOR_CHARS: int   = 10_000   # ~10 KB of cover text
MAX_HIDDEN_CHARS: int   =  1_000   # Plane 14 payload ceiling
MAX_RAW_TEXT_CHARS: int = 50_000   # Input ceiling for decode scans

# ─── Application factory ──────────────────────────────────────────────────────

app = FastAPI(
    title="BlindTag API",
    description=(
        "Local transport layer for Unicode Plane 14 steganographic "
        "encode/decode operations. Run on localhost only."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Restrict CORS to loopback origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)


# ─── Security headers middleware ──────────────────────────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Inject mandatory security headers on every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Request-Id"] = str(uuid.uuid4())
    return response



@app.exception_handler(InvalidPayloadError)
async def invalid_payload_handler(
    request: Request, exc: InvalidPayloadError
) -> JSONResponse:
    """Surface BlindTag domain errors as 422 Unprocessable Entity."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "error_type": "InvalidPayloadError"},
    )


# ─── Request / Response schemas ───────────────────────────────────────────────

class EncodeRequest(BaseModel):
    """Schema for POST /v1/encode."""

    anchor: str = Field(
        ...,
        min_length=1,
        max_length=MAX_ANCHOR_CHARS,
        description=(
            "Visible cover text into which the payload will be embedded. "
            "Accepts any valid Unicode string (emoji, CJK, RTL, etc.)."
        ),
        examples=["Meeting notes from Monday's sync"],
    )
    hidden_message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_HIDDEN_CHARS,
        description=(
            "Secret payload to embed. MUST consist exclusively of printable "
            "ASCII characters (U+0020 SPACE through U+007E TILDE). "
            f"Maximum length: {MAX_HIDDEN_CHARS} characters."
        ),
        examples=["PRIORITY:HIGH;REF:INV-4821"],
    )

    @field_validator("hidden_message")
    @classmethod
    def must_be_printable_ascii(cls, value: str) -> str:
        """
        Schema-level ASCII guard — runs before the core engine.

        Rejects any payload containing characters outside the printable
        ASCII window at the HTTP boundary, returning a structured 422
        before codec execution begins.
        """
        for idx, char in enumerate(value):
            code = ord(char)
            if not (0x20 <= code <= 0x7E):
                raise ValueError(
                    f"hidden_message[{idx}] = U+{code:04X} {char!r} is not "
                    "printable ASCII. Only characters U+0020–U+007E are accepted."
                )
        return value


class EncodeResponse(BaseModel):
    """Schema for POST /v1/encode response."""

    result: str = Field(
        description="Composite string: visible anchor + invisible Plane 14 payload."
    )
    anchor_length: int = Field(description="Character count of the anchor text.")
    payload_length: int = Field(description="Character count of the hidden message.")
    total_length: int = Field(
        description=(
            "Total character count of result "
            "(anchor + tag chars + TAG_CANCEL sentinel)."
        )
    )


class DecodeRequest(BaseModel):
    """Schema for POST /v1/decode."""

    raw_text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_RAW_TEXT_CHARS,
        description=(
            "Raw text to scan for embedded Plane 14 tag payloads. "
            f"Maximum length: {MAX_RAW_TEXT_CHARS} characters."
        ),
    )


class DecodeResponse(BaseModel):
    """Schema for POST /v1/decode response."""

    found: bool = Field(description="True if a Plane 14 payload was detected.")
    message: Optional[str] = Field(
        default=None,
        description="Extracted payload, or null if no Plane 14 data was found.",
    )
    detail: str = Field(description="Human-readable status description.")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post(
    "/v1/encode",
    response_model=EncodeResponse,
    summary="Embed hidden payload into cover text",
    tags=["Codec"],
)
async def encode_endpoint(request: EncodeRequest) -> EncodeResponse:
    """
    Embed *hidden_message* into *anchor* using invisible Plane 14 tag characters.

    The returned ``result`` string is visually indistinguishable from the
    anchor text. Copy and paste it into any Unicode-preserving medium
    to transport the payload covertly.

    **Size limits**

    | Field          | Maximum      |
    |----------------|-------------|
    | anchor         | 10 000 chars |
    | hidden_message |  1 000 chars |
    """
    try:
        result = encode(anchor=request.anchor, hidden_message=request.hidden_message)
    except InvalidPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return EncodeResponse(
        result=result,
        anchor_length=len(request.anchor),
        payload_length=len(request.hidden_message),
        total_length=len(result),
    )


@app.post(
    "/v1/decode",
    response_model=DecodeResponse,
    summary="Extract hidden payload from raw text",
    tags=["Codec"],
)
async def decode_endpoint(request: DecodeRequest) -> DecodeResponse:
    """
    Scan *raw_text* for an embedded Plane 14 tag payload.

    Returns the extracted secret message if any Plane 14 codepoints are found.
    Returns a clear ``found: false`` response with informative detail if the
    input contains no tag characters.

    A ``422`` error is returned if a tag codepoint decodes to an out-of-range
    value, indicating a corrupted or synthetically crafted payload.
    """
    try:
        message = decode(request.raw_text)
    except InvalidPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if message is None:
        return DecodeResponse(
            found=False,
            message=None,
            detail="No Plane 14 tag payload detected in the provided text.",
        )

    return DecodeResponse(
        found=True,
        message=message,
        detail=f"Payload successfully extracted ({len(message)} characters).",
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["Operational"],
)
async def health_check() -> HealthResponse:
    """Simple liveness probe for monitoring or container health checks."""
    return HealthResponse(
        status="ok",
        service="BlindTag API",
        version="1.0.0",
    )


# ─── Programmatic server launch ───────────────────────────────────────────────

def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """
    Launch the BlindTag FastAPI server via Uvicorn.

    Always binds to localhost by default to prevent unintended exposure.
    Pass ``host="0.0.0.0"`` only in explicitly controlled environments.

    Args:
        host:      Bind address. Default: "127.0.0.1" (loopback only).
        port:      TCP port. Default: 8000.
        reload:    Enable Uvicorn hot-reload (development mode).
        log_level: Uvicorn log verbosity ("debug", "info", "warning", "error").
    """
    uvicorn.run(
        "blindtag.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_server()
