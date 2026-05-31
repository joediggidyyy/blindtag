"""
blindtag.cli — Unified CLI root for the BlindTag steganographic toolkit.

Top-level import budget: argparse, json, logging, os, shutil, subprocess, sys only.
PySide6, fastapi, uvicorn, blindtag.api, and blindtag.widget are lazy-imported
inside their respective handlers to keep --help and --version instantaneous
and to prevent GUI toolkit initialisation on encode/decode calls.
"""
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from typing import List, Optional

from blindtag import __version__
from blindtag.core import decode, encode, strip_plane14
from blindtag.exceptions import DecodingError, InvalidPayloadError


_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}
_LOG_LEVELS = ["debug", "info", "warning", "error", "critical"]

# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _ascii_safe(value: object) -> str:
    """Return a console-safe ASCII rendering for *value*."""
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _should_emit_human_confirmation() -> bool:
    """Return True when BlindTag should emit friendly stderr confirmations."""
    override = os.getenv("BLINDTAG_CLI_CONFIRM", "").strip().lower()
    if override in _TRUTHY:
        return True
    if override in _FALSY:
        return False
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


def _emit_structured_block(
    command: str,
    decision: str,
    summary_items: list[tuple[str, object]],
    next_action: str,
) -> None:
    """Emit a friendly, structured stderr block for humans."""
    lines = [f"BlindTag :: {command}", f"decision: {_ascii_safe(decision)}", "", "Summary"]
    if summary_items:
        width = max(len(key) for key, _ in summary_items)
        for key, value in summary_items:
            lines.append(f"{key.ljust(width)} : {_ascii_safe(value)}")
    else:
        lines.append("status : none")
    lines.extend(["", "Next action", _ascii_safe(next_action)])
    print("\n".join(lines), file=sys.stderr)


def _emit_confirmation(
    command: str,
    decision: str,
    summary_items: list[tuple[str, object]],
    next_action: str,
) -> None:
    """Emit a structured success/miss confirmation when the human channel is active."""
    if not _should_emit_human_confirmation():
        return
    _emit_structured_block(command, decision, summary_items, next_action)


def _emit_handled_error(
    command: str,
    decision: str,
    reason: object,
    next_action: str,
    summary_items: Optional[list[tuple[str, object]]] = None,
) -> None:
    """Emit a structured handled-error block to stderr."""
    merged = [("reason", reason)]
    if summary_items:
        merged.extend(summary_items)
    _emit_structured_block(command, decision, merged, next_action)


def _resolve_log_level(args: argparse.Namespace) -> int:
    """Return the effective Python logging level for the current command."""
    if getattr(args, "command", None) == "widget":
        return logging.WARNING

    root_level = getattr(args, "root_log_level", "warning").lower()
    if getattr(args, "verbose", False) and root_level == "warning":
        root_level = "debug"

    return getattr(logging, root_level.upper(), logging.WARNING)


def _configure_logging(args: argparse.Namespace) -> None:
    """Attach runtime logging handlers without emitting import-time noise."""
    logging.basicConfig(
        level=_resolve_log_level(args),
        format="blindtag %(levelname)s %(name)s: %(message)s",
        force=True,
    )

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
            "  blindtag api --port 8080\n"
            "  blindtag widget"
        ),
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"blindtag {__version__}",
    )
    parser.add_argument(
        "--log-level",
        dest="root_log_level",
        default="warning",
        choices=_LOG_LEVELS,
        help="Root BlindTag logging level for non-widget execution paths (default: warning).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Shortcut for informational runtime logging when no explicit root --log-level is supplied.",
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
        choices=_LOG_LEVELS,
        dest="log_level",
        help="Uvicorn log verbosity (default: info).",
    )

    # --- widget ---
    subparsers.add_parser(
        "widget",
        help="Launch the BlindTag widget.",
        description=(
            "Launch the BlindTag widget through the supported compatibility "
            "CLI surface."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  blindtag widget\n"
            "  blindtag-widget"
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _handle_encode(args: argparse.Namespace) -> int:
    try:
        result = encode(args.anchor, args.payload)
    except (InvalidPayloadError, ValueError) as exc:
        _emit_handled_error(
            "encode",
            "rejected_input",
            exc,
            "Use printable ASCII payload text only, or rerun 'blindtag encode --help' for usage.",
            [("output_mode", args.out)],
        )
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

    _emit_confirmation(
        "encode",
        "payload_encoded",
        [
            ("anchor_length", len(args.anchor)),
            ("payload_length", len(args.payload)),
            ("output_mode", args.out),
            ("stdout_result", "emitted"),
        ],
        "Use the stdout result exactly as printed, or pass it into 'blindtag decode' to verify recovery.",
    )
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
        _emit_handled_error(
            "decode",
            "decode_failed",
            exc,
            "Inspect the input for corrupted tag characters, or rerun 'blindtag strip' to remove Plane 14 markers.",
            [("output_mode", args.out)],
        )
        return 1

    if args.out == "json":
        if payload is None:
            print(json.dumps({"found": False, "message": None}))
        else:
            print(json.dumps({"found": True, "message": payload}))
    else:
        if payload is not None:
            print(payload)

    if payload is None:
        _emit_confirmation(
            "decode",
            "no_payload_found",
            [
                ("output_mode", args.out),
                ("stdout_result", "empty_by_contract" if args.out == "text" else "json_emitted"),
            ],
            "Verify that the input contains BlindTag text, or run 'blindtag encode' first to create a tagged sample.",
        )
    else:
        _emit_confirmation(
            "decode",
            "payload_found",
            [
                ("payload_length", len(payload)),
                ("output_mode", args.out),
                ("stdout_result", "emitted"),
            ],
            "Use the recovered payload from stdout, or rerun with '--out json' for a machine-readable result.",
        )
    return 0


def _handle_strip(args: argparse.Namespace) -> int:
    text = _read_text_or_stdin(args.text)
    result = strip_plane14(text)

    if args.out == "json":
        print(json.dumps({"result": result}))
    else:
        print(result)

    _emit_confirmation(
        "strip",
        "text_stripped",
        [
            ("input_length", len(text)),
            ("output_length", len(result)),
            ("output_mode", args.out),
            ("stdout_result", "emitted"),
        ],
        "Use the cleaned stdout result directly, or rerun with '--out json' if another tool will parse it.",
    )
    return 0


def _handle_api(args: argparse.Namespace) -> int:
    try:
        from blindtag.api import run_server  # lazy import
    except ImportError as exc:
        _emit_handled_error(
            "api",
            "startup_blocked",
            f"could not import server dependencies - {exc}",
            "Install the API dependencies, then rerun 'blindtag api'.",
            [("host", args.host), ("port", args.port)],
        )
        return 1

    _emit_confirmation(
        "api",
        "server_start_requested",
        [
            ("host", args.host),
            ("port", args.port),
            ("reload", "yes" if args.reload else "no"),
            ("log_level", args.log_level),
        ],
        "Wait for the server startup lines, then open /health or press Ctrl+C to stop the server.",
    )

    try:
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except Exception as exc:
        _emit_handled_error(
            "api",
            "startup_failed",
            exc,
            "Check whether the port is already in use, or rerun with a different '--port' value.",
            [("host", args.host), ("port", args.port)],
        )
        return 1
    return 0


def _resolve_widget_launcher() -> Optional[str]:
    executable_dir = os.path.dirname(sys.executable)
    for launcher_name in ("blindtag-widget.exe", "blindtag-widget"):
        candidate = os.path.join(executable_dir, launcher_name)
        if os.path.isfile(candidate):
            return candidate

    return shutil.which("blindtag-widget")


def _launch_widget_process() -> int:
    launcher = _resolve_widget_launcher()
    if launcher is None:
        try:
            from blindtag.widget import run_widget  # lazy import
        except ImportError as exc:
            _emit_handled_error(
                "widget",
                "launch_blocked",
                f"could not import widget dependencies - {exc}",
                "Install the widget dependencies, then rerun 'blindtag widget'.",
            )
            return 1

        _emit_confirmation(
            "widget",
            "widget_launch_started",
            [
                ("launch_mode", "module_fallback"),
                ("detached", "no"),
                ("widget_surface", "in_process"),
            ],
            "Use the BlindTag window to continue. Close the widget when finished.",
        )
        try:
            run_widget()
        except Exception as exc:
            _emit_handled_error(
                "widget",
                "launch_failed",
                exc,
                "Confirm that a desktop session is available, then rerun 'blindtag widget'.",
                [("launch_mode", "module_fallback")],
            )
            return 1
        return 0

    try:
        subprocess.Popen([launcher])
    except OSError as exc:
        _emit_handled_error(
            "widget",
            "launch_failed",
            f"could not launch widget - {exc}",
            "Confirm that the dedicated widget launcher exists and can be started, then rerun 'blindtag widget'.",
            [("launcher", launcher)],
        )
        return 1

    _emit_confirmation(
        "widget",
        "widget_handoff_started",
        [
            ("launcher", launcher),
            ("launch_mode", "dedicated_launcher"),
            ("detached", "yes"),
        ],
        "Use the BlindTag window to continue. If no window appears, rerun the command and review the launcher path above.",
    )

    return 0


def _handle_widget(args: argparse.Namespace) -> int:
    del args
    return _launch_widget_process()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_HANDLERS = {
    "encode": _handle_encode,
    "decode": _handle_decode,
    "strip": _handle_strip,
    "api": _handle_api,
    "widget": _handle_widget,
}


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for the `blindtag` CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args)
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
        _emit_handled_error(
            "widget",
            "usage_rejected",
            "no arguments are supported by the dedicated widget launcher",
            "Launch 'blindtag-widget' with no arguments, or use 'blindtag widget' from the root CLI.",
        )
        raise SystemExit(2)

    try:
        from blindtag.widget import run_widget  # lazy import
    except ImportError as exc:
        _emit_handled_error(
            "widget",
            "launch_blocked",
            f"could not import widget dependencies - {exc}",
            "Install the widget dependencies, then rerun 'blindtag-widget'.",
        )
        raise SystemExit(1)

    run_widget()
