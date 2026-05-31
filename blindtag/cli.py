"""
blindtag.cli — Unified CLI root for the BlindTag steganographic toolkit.

Top-level import budget: argparse, sys, json only.
PySide6, fastapi, uvicorn, blindtag.api, and blindtag.widget are lazy-imported
inside their respective handlers to keep --help and --version instantaneous
and to prevent GUI toolkit initialisation on encode/decode calls.
"""
import argparse
import json
import sys
from typing import List, Optional

from blindtag import __version__
from blindtag.core import decode, encode, strip_plane14
from blindtag.exceptions import DecodingError, InvalidPayloadError

# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blindtag",
        description=(
            "BlindTag steganographic toolkit — embed invisible Plane 14 payloads "
            "inside ordinary Unicode text."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  blindtag encode 'Meeting notes' 'CONFIDENTIAL'\n"
            "  blindtag decode '<tagged text>'\n"
            "  blindtag strip '<tagged text>'\n"
            "  blindtag api --port 8080"
        ),
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"blindtag {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- encode ---
    enc_p = subparsers.add_parser(
        "encode",
        help="Embed a payload string inside anchor text.",
        description="Encode an invisible Plane 14 payload into anchor text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  blindtag encode 'Meeting notes' 'CONFIDENTIAL'\n"
            "  blindtag encode 'anchor' 'payload' --out json"
        ),
    )
    enc_p.add_argument("anchor", help="Visible carrier text.")
    enc_p.add_argument("payload", help="ASCII payload to embed (printable ASCII only).")
    enc_p.add_argument(
        "--out", choices=["text", "json"], default="text",
        help="Output format. 'text' (default) prints the tagged string; 'json' prints a JSON object.",
    )

    # --- decode ---
    dec_p = subparsers.add_parser(
        "decode",
        help="Extract the payload from tagged text.",
        description="Decode and print any embedded Plane 14 payload found in the input text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  blindtag decode '<tagged text>'\n"
            "  echo '<tagged text>' | blindtag decode -\n"
            "  blindtag decode '<tagged text>' --out json"
        ),
    )
    dec_p.add_argument(
        "text",
        help="Text to inspect. Use '-' to read from stdin.",
    )
    dec_p.add_argument(
        "--out", choices=["text", "json"], default="text",
        help="Output format.",
    )

    # --- strip ---
    strip_p = subparsers.add_parser(
        "strip",
        help="Remove all Plane 14 tag characters from text.",
        description="Strip every embedded Plane 14 payload from the input, returning clean text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  blindtag strip '<tagged text>'\n"
            "  echo '<tagged text>' | blindtag strip -\n"
            "  blindtag strip '<tagged text>' --out json"
        ),
    )
    strip_p.add_argument(
        "text",
        help="Text to strip. Use '-' to read from stdin.",
    )
    strip_p.add_argument(
        "--out", choices=["text", "json"], default="text",
        help="Output format.",
    )

    # --- api ---
    api_p = subparsers.add_parser(
        "api",
        help="Start the BlindTag FastAPI server.",
        description="Launch the BlindTag FastAPI server (binds to localhost by default).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  blindtag api\n"
            "  blindtag api --port 8080\n"
            "  blindtag api --host 127.0.0.1 --port 8000 --log-level debug"
        ),
    )
    api_p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    api_p.add_argument("--port", type=int, default=8000, help="TCP port (default: 8000).")
    api_p.add_argument("--reload", action="store_true", help="Enable Uvicorn hot-reload.")
    api_p.add_argument(
        "--log-level", default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        dest="log_level",
        help="Uvicorn log verbosity (default: info).",
    )

    return parser


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _handle_encode(args: argparse.Namespace) -> int:
    try:
        result = encode(args.anchor, args.payload)
    except (InvalidPayloadError, ValueError) as exc:
        print(f"blindtag encode: {exc}", file=sys.stderr)
        return 1

    if args.out == "json":
        payload_doc = {
            "result": result,
            "anchor_length": len(args.anchor),
            "payload_length": len(args.payload),
            "total_length": len(result),
        }
        print(json.dumps(payload_doc))
    else:
        print(result)
    return 0


def _read_text_or_stdin(text_arg: str) -> str:
    if text_arg == "-":
        return sys.stdin.read()
    return text_arg


def _handle_decode(args: argparse.Namespace) -> int:
    text = _read_text_or_stdin(args.text)
    try:
        payload = decode(text)
    except (DecodingError, InvalidPayloadError) as exc:
        print(f"blindtag decode: {exc}", file=sys.stderr)
        return 1

    if args.out == "json":
        if payload is None:
            print(json.dumps({"found": False, "message": None}))
        else:
            print(json.dumps({"found": True, "message": payload}))
    else:
        if payload is not None:
            print(payload)
    return 0


def _handle_strip(args: argparse.Namespace) -> int:
    text = _read_text_or_stdin(args.text)
    result = strip_plane14(text)

    if args.out == "json":
        print(json.dumps({"result": result}))
    else:
        print(result)
    return 0


def _handle_api(args: argparse.Namespace) -> int:
    try:
        from blindtag.api import run_server  # lazy import
    except ImportError as exc:
        print(f"blindtag api: could not import server dependencies — {exc}", file=sys.stderr)
        return 1

    run_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_HANDLERS = {
    "encode": _handle_encode,
    "decode": _handle_decode,
    "strip": _handle_strip,
    "api": _handle_api,
}


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for the `blindtag` CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    code = _HANDLERS[args.command](args)
    sys.exit(code)


def _api_shim() -> None:
    """
    Entry point for the `blindtag-api` console script.
    Reconstructs sys.argv with 'api' prepended and delegates to main().
    """
    sys.argv = ["blindtag", "api"] + sys.argv[1:]
    main()


def _widget_shim() -> None:
    """
    Entry point for the `blindtag-widget` GUI script.
    Launches the widget directly so the supported widget surface remains
    terminal-free and decoupled from the root CLI parser.
    """
    if len(sys.argv) > 1:
        print(
            "blindtag-widget: no arguments are supported; launch the widget directly.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        from blindtag.widget import run_widget  # lazy import
    except ImportError as exc:
        print(
            f"blindtag-widget: could not import widget dependencies — {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    run_widget()
