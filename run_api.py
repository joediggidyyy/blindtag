#!/usr/bin/env python3
"""
run_api.py
==========
Convenience launcher for the BlindTag FastAPI server.

Usage
-----
  python run_api.py                    # localhost:8000, info logging
  python run_api.py --port 9000        # custom port
  python run_api.py --reload           # hot-reload for development
  python run_api.py --log-level debug  # verbose logging

The server always binds to 127.0.0.1 (loopback) by default.
Pass --host 0.0.0.0 only in deliberately controlled environments.

API documentation (once running):
  http://127.0.0.1:8000/docs     ← Swagger UI
  http://127.0.0.1:8000/redoc    ← ReDoc
  http://127.0.0.1:8000/health   ← Liveness probe
"""

import argparse
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BlindTag FastAPI server launcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (loopback by default; use 0.0.0.0 with caution).",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="TCP port to listen on.",
    )
    parser.add_argument(
        "--reload", action="store_true",
        help="Enable Uvicorn hot-reload (development mode).",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Uvicorn logging verbosity.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print(
        f"\n  ⬡  BlindTag API  ·  v1.0.0\n"
        f"  ─────────────────────────────────────────\n"
        f"  Listening  :  http://{args.host}:{args.port}\n"
        f"  Swagger UI :  http://{args.host}:{args.port}/docs\n"
        f"  ReDoc      :  http://{args.host}:{args.port}/redoc\n"
        f"  Hot-reload :  {'enabled' if args.reload else 'disabled'}\n"
        f"  Log level  :  {args.log_level}\n"
        f"  ─────────────────────────────────────────\n"
        f"  Press Ctrl+C to stop.\n"
    )

    try:
        from blindtag.api import run_server
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except ImportError as exc:
        print(f"\n  ✕  Import error: {exc}")
        print("  Run `pip install -e .` or `pip install -r requirements.txt` first.\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  ·  BlindTag API server stopped.\n")


if __name__ == "__main__":
    main()
