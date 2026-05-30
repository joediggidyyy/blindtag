#!/usr/bin/env python3
"""
run_widget.py
=============
Convenience launcher for the BlindTag desktop observer widget.

Usage
-----
  python run_widget.py

Requirements
------------
  PySide6 >= 6.8  (installed with: pip install -e .)

Platform notes
--------------
  Windows  — Works natively. DPI handling managed by Qt.
  macOS    — Works natively. Grant Accessibility permissions if prompted.
  Linux    — Requires a running display server (X11 or Wayland via XWayland).
"""

import sys


def main() -> None:
    print(
        "\n  ⬡  BlindTag Widget  ·  v1.0.0\n"
        "  ─────────────────────────────────────────\n"
        "  Launching observer widget…\n"
        "  ─────────────────────────────────────────\n"
        "  Hotkeys:\n"
        "    Ctrl+E       →  Encode panel\n"
        "    Ctrl+D       →  Decode panel\n"
        "    Ctrl+W       →  Toggle Clipboard Watcher\n"
        "    Ctrl+Return  →  Execute active panel action\n"
        "    Escape       →  Close widget\n"
        "  ─────────────────────────────────────────\n"
    )

    try:
        from blindtag.widget import run_widget
        run_widget()
    except ImportError as exc:
        print(f"\n  Import error: {exc}")
        print(
            "  Ensure GUI dependencies are installed:\n"
            "    pip install -e .\n"
        )
        sys.exit(1)
    except Exception as exc:
        print(f"\n  ✕  Widget error: {exc}")
        print(
            "  On Linux, ensure a display server is available (DISPLAY env var).\n"
            "  On macOS, grant Accessibility permissions if clipboard fails.\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
