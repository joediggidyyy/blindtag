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
  pip install customtkinter pyperclip

Platform notes
--------------
  Windows  — Works natively. DPI-awareness is handled by customtkinter.
  macOS    — Works natively. Grant Accessibility permissions if clipboard
             watcher encounters permission errors.
  Linux    — Requires a running display server (X11 or Wayland via XWayland).
             Install xclip or xsel for pyperclip clipboard support:
               sudo apt install xclip     # Debian / Ubuntu
               sudo dnf install xclip     # Fedora
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
        print(f"\n  ✕  Import error: {exc}")
        print(
            "  Ensure GUI dependencies are installed:\n"
            "    pip install customtkinter pyperclip\n"
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
