"""
blindtag.api
============
Secure local transport layer for BlindTag encode/decode operations.

Architecture
------------
A lightweight FastAPI ASGI application with four functional endpoints:

  POST /v1/encode      Embeds a hidden ASCII payload into visible cover text.
  POST /v1/decode      Extracts any Plane 14 tag payload from a raw string.
  GET  /v1/log         Queries retained structured BlindTag event records.
  POST /v1/log/export  Writes a controlled retained-evidence export packet.

Security Model
--------------
• Payload size limits are enforced at the Pydantic validation layer BEFORE
  any codec logic executes — preventing memory pressure from oversized inputs.
• Non-ASCII characters in hidden_message are rejected at the schema level,
  providing a second defence layer on top of the core engine's own checks.
• All exceptions from the core engine are caught and surfaced as structured
  JSON error responses — no stack traces leak to callers.
• Retained reporting is local-only and path-contained under
  `.blindtag/generated/reporting/`.
• Intended for localhost-only use; CORS is restricted accordingly.

Running the server
------------------
  python run_api.py
  # or:
  uvicorn blindtag.api:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from . import reporting
from .core import decode, encode
from .exceptions import InvalidPayloadError

LOGGER = logging.getLogger(__name__)

# ─── Payload size policy ──────────────────────────────────────────────────────

MAX_ANCHOR_CHARS: int = 10_000
MAX_HIDDEN_CHARS: int = 1_000
MAX_RAW_TEXT_CHARS: int = 50_000

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
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(InvalidPayloadError)
async def invalid_payload_handler(
    request: Request, exc: InvalidPayloadError
) -> JSONResponse:
    """Surface BlindTag domain errors as 422 Unprocessable Entity."""
    LOGGER.warning("BlindTag invalid payload rejected for request_id=%s", _request_id(request))
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
        """Reject non-printable or non-ASCII payloads at the HTTP boundary."""
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


class OperationRecord(BaseModel):
    recorded_at: str
    event_id: str
    request_id: Optional[str] = None
    surface: str
    operation: str
    severity: str
    decision: str
    outcome: str
    anchor_length: Optional[int] = None
    payload_length: Optional[int] = None
    resolved_token_count: Optional[int] = None
    error_type: Optional[str] = None
    detail: str
    reason: Optional[str] = None
    policy_mode: str = "operational"
    subject_kind: str = "text_payload"
    source_artifact_sha256: Optional[str] = None
    derived_artifact_sha256: Optional[str] = None
    parent_event_id: Optional[str] = None
    requester_id: Optional[str] = None
    key_id: Optional[str] = None
    scope: Optional[str] = None
    action_phase: Optional[str] = None
    tool_version: Optional[str] = None
    session_id: Optional[str] = None
    host_context: Optional[str] = None
    previous_record_hash: Optional[str] = None
    record_hash: Optional[str] = None
    segment_id: Optional[str] = None


class LogQueryResponse(BaseModel):
    detail: str
    count: int
    limit: int
    filters: dict[str, Optional[str | int]]
    items: list[OperationRecord]


class LogExportRequest(BaseModel):
    format: str = Field(default="json", pattern="^(json|markdown)$")
    request_id: Optional[str] = None
    operation: Optional[str] = None
    level: Optional[str] = None
    policy_mode: str = Field(default="operational", pattern="^(operational|security|forensic)$")
    action_phase: Optional[str] = Field(
        default=None,
        pattern="^(received|verified|exported|blocked|quarantined|unpacked|released)$",
    )
    limit: int = Field(
        default=reporting.DEFAULT_QUERY_LIMIT,
        ge=1,
        le=reporting.MAX_EXPORT_LIMIT,
    )
    requester_id: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[str] = None
    signature: Optional[str] = None


class LogExportResponse(BaseModel):
    decision: str
    detail: str
    export_id: str
    format: str
    policy_mode: str
    record_count: int
    filters: dict[str, Optional[str | int]]
    artifact_family: dict[str, object]
    signature_state: dict[str, object]
    verification: dict[str, bool]
    sandbox_assessment: Optional[dict[str, object]] = None
    next_action: str


def _reporting_base_dir(http_request: Request) -> object:
    """Return the current retained reporting base directory."""
    return getattr(http_request.app.state, "reporting_base_dir", None)


def _request_id(http_request: Request) -> Optional[str]:
    """Return the middleware-assigned request identifier."""
    return getattr(http_request.state, "request_id", None)


def _record_api_event(
    http_request: Request,
    *,
    operation: str,
    severity: str,
    outcome: str,
    detail: str,
    anchor_length: Optional[int] = None,
    payload_length: Optional[int] = None,
    resolved_token_count: Optional[int] = None,
    error_type: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Persist one API-owned retained event."""
    record = reporting.build_event_record(
        surface="api",
        operation=operation,
        severity=severity,
        outcome=outcome,
        detail=detail,
        request_id=_request_id(http_request),
        anchor_length=anchor_length,
        payload_length=payload_length,
        resolved_token_count=resolved_token_count,
        error_type=error_type,
        reason=reason,
    )
    reporting.append_event(record, base_dir=_reporting_base_dir(http_request))


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post(
    "/v1/encode",
    response_model=EncodeResponse,
    summary="Embed hidden payload into cover text",
    tags=["Codec"],
)
async def encode_endpoint(payload: EncodeRequest, http_request: Request) -> EncodeResponse:
    """Embed *hidden_message* into *anchor* using invisible Plane 14 tag characters."""
    try:
        result = encode(anchor=payload.anchor, hidden_message=payload.hidden_message)
    except InvalidPayloadError as exc:
        _record_api_event(
            http_request,
            operation="encode",
            severity="warning",
            outcome="invalid_payload",
            detail=str(exc),
            anchor_length=len(payload.anchor),
            payload_length=len(payload.hidden_message),
            error_type="InvalidPayloadError",
            reason="invalid_payload",
        )
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        _record_api_event(
            http_request,
            operation="encode",
            severity="warning",
            outcome="rejected_input",
            detail=str(exc),
            anchor_length=len(payload.anchor),
            payload_length=len(payload.hidden_message),
            error_type="ValueError",
            reason="invalid_input",
        )
        raise HTTPException(status_code=400, detail=str(exc))

    _record_api_event(
        http_request,
        operation="encode",
        severity="info",
        outcome="payload_encoded",
        detail="Payload encoded and returned successfully.",
        anchor_length=len(payload.anchor),
        payload_length=len(payload.hidden_message),
        reason="encode_success",
    )

    return EncodeResponse(
        result=result,
        anchor_length=len(payload.anchor),
        payload_length=len(payload.hidden_message),
        total_length=len(result),
    )


@app.post(
    "/v1/decode",
    response_model=DecodeResponse,
    summary="Extract hidden payload from raw text",
    tags=["Codec"],
)
async def decode_endpoint(payload: DecodeRequest, http_request: Request) -> DecodeResponse:
    """Scan *raw_text* for an embedded Plane 14 tag payload."""
    try:
        message = decode(payload.raw_text)
    except InvalidPayloadError as exc:
        _record_api_event(
            http_request,
            operation="decode",
            severity="warning",
            outcome="invalid_payload",
            detail=str(exc),
            anchor_length=len(payload.raw_text),
            error_type="InvalidPayloadError",
            reason="invalid_payload",
        )
        raise HTTPException(status_code=422, detail=str(exc))

    if message is None:
        _record_api_event(
            http_request,
            operation="decode",
            severity="info",
            outcome="no_payload_found",
            detail="No Plane 14 tag payload detected in the provided text.",
            anchor_length=len(payload.raw_text),
            payload_length=0,
            reason="no_payload_found",
        )
        return DecodeResponse(
            found=False,
            message=None,
            detail="No Plane 14 tag payload detected in the provided text.",
        )

    _record_api_event(
        http_request,
        operation="decode",
        severity="info",
        outcome="payload_found",
        detail=f"Payload successfully extracted ({len(message)} characters).",
        anchor_length=len(payload.raw_text),
        payload_length=len(message),
        reason="decode_success",
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


@app.get(
    "/v1/log",
    response_model=LogQueryResponse,
    summary="Query retained BlindTag operation events",
    tags=["Operational"],
)
async def log_query_endpoint(
    http_request: Request,
    request_id: Optional[str] = Query(default=None),
    operation: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    policy_mode: Optional[str] = Query(default=None, pattern="^(operational|security|forensic)$"),
    action_phase: Optional[str] = Query(
        default=None,
        pattern="^(received|verified|exported|blocked|quarantined|unpacked|released)$",
    ),
    limit: int = Query(
        default=reporting.DEFAULT_QUERY_LIMIT,
        ge=1,
        le=reporting.MAX_QUERY_LIMIT,
    ),
) -> LogQueryResponse:
    """Return the newest retained events matching the provided filters."""
    try:
        items = reporting.query_events(
            base_dir=_reporting_base_dir(http_request),
            request_id=request_id,
            operation=operation,
            level=level,
            policy_mode=policy_mode,
            action_phase=action_phase,
            limit=limit,
        )
    except reporting.ReportingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _record_api_event(
        http_request,
        operation="log_query",
        severity="info",
        outcome="query_returned",
        detail=f"Retained log query returned {len(items)} matching records.",
        resolved_token_count=len(items),
        reason="query_success",
    )
    return LogQueryResponse(
        detail=f"Returned {len(items)} retained BlindTag event records.",
        count=len(items),
        limit=limit,
        filters={
            "request_id": request_id,
            "operation": operation,
            "level": level,
            "policy_mode": policy_mode,
            "action_phase": action_phase,
            "limit": limit,
        },
        items=[OperationRecord(**item) for item in items],
    )


@app.post(
    "/v1/log/export",
    response_model=LogExportResponse,
    summary="Export retained BlindTag operation evidence",
    tags=["Operational"],
)
async def log_export_endpoint(payload: LogExportRequest, http_request: Request) -> LogExportResponse:
    """Write a controlled retained-evidence export under the reporting root."""
    try:
        export_packet = reporting.export_events(
            export_format=payload.format,
            base_dir=_reporting_base_dir(http_request),
            request_id=payload.request_id,
            operation=payload.operation,
            level=payload.level,
            policy_mode=payload.policy_mode,
            action_phase=payload.action_phase,
            limit=payload.limit,
            requester_id=payload.requester_id,
            scope=payload.scope,
            expires_at=payload.expires_at,
            signature=payload.signature,
        )
    except reporting.ExportAuthorizationError as exc:
        _record_api_event(
            http_request,
            operation="log_export",
            severity="warning",
            outcome="export_denied",
            detail=str(exc),
            error_type="ExportAuthorizationError",
            reason="export_authorization_failed",
        )
        raise HTTPException(status_code=403, detail=str(exc))
    except reporting.ReportingError as exc:
        _record_api_event(
            http_request,
            operation="log_export",
            severity="error",
            outcome="export_failed",
            detail=str(exc),
            error_type="ReportingError",
            reason="export_failed",
        )
        raise HTTPException(status_code=400, detail=str(exc))

    _record_api_event(
        http_request,
        operation="log_export",
        severity="info",
        outcome="export_written",
        detail=f"Retained export wrote {export_packet['record_count']} records as {payload.format}.",
        resolved_token_count=export_packet["record_count"],
        reason="export_success",
    )
    return LogExportResponse(**export_packet)


# ─── Programmatic server launch ───────────────────────────────────────────────

def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """Launch the BlindTag FastAPI server via Uvicorn."""
    uvicorn.run(
        "blindtag.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_server()
