"""
blindtag.widget
===============
Low-profile desktop observer widget for rapid BlindTag encode/decode workflows.

Visual Identity
---------------
  Background (primary):  #121212  Matte Charcoal
  Surface (secondary):   #1E1E1E  Dark Gray
  Raised surface:        #252525  Card Gray
  Accent:                #4A90D9  Technical Blue
  Accent hover:          #5BA3F0  Blue Highlight
  Text (primary):        #E8E8E8  Near-White
  Text (muted):          #888888  Mid-Gray
  Success:               #4CAF6E  Confirmation Green
  Warning:               #E8A838  Amber Alert
  Error:                 #E85555  Alert Red

Panel Layout
------------
  ┌──────────────────────────────────────────┐
  │ ⬡ BlindTag                       ─   ✕  │  ← draggable title bar
  ├──────────────────────────────────────────┤
  │ [ Encode ] [ Decode ]     □ Clip Watch   │  ← segmented toggle
  ├──────────────────────────────────────────┤
  │                                          │
  │  [ANCHOR TEXT / RAW INPUT textbox]       │  ← main input area
  │  [HIDDEN PAYLOAD textbox]  (encode only) │
  │  [OUTPUT textbox]                        │
  │                                          │
  │  [ Encode ]  [ ⬡ Obfuscate & Copy ]     │  ← action row
  │             [ Clear All ]               │
  ├──────────────────────────────────────────┤
  │ Status message                        ●  │  ← status bar
  └──────────────────────────────────────────┘

Hotkeys
-------
  Ctrl+E       Switch to Encode panel
  Ctrl+D       Switch to Decode panel
  Ctrl+W       Toggle Clipboard Watcher
  Ctrl+Return  Execute primary action for active panel
  Escape       Close widget

Clipboard Watcher
-----------------
When active, a daemon thread polls the system clipboard every 800 ms.
If new content contains a Plane 14 tag payload, the widget surfaces a
notification overlay, switches to the Decode panel, and auto-populates
the output field. No data leaves the local machine.

Dependencies: customtkinter >= 5.2.2, pyperclip >= 1.8.2
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import customtkinter as ctk
import pyperclip

from .core import decode, encode, strip_plane14
from .exceptions import InvalidPayloadError

# ─── Colour palette ───────────────────────────────────────────────────────────

C_BG        = "#121212"   # Matte Charcoal  — window background
C_SECONDARY = "#1E1E1E"   # Dark Gray        — title bar, toggle strip, status bar
C_SURFACE   = "#252525"   # Card Gray        — read-only output fields
C_ACCENT    = "#4A90D9"   # Technical Blue   — primary CTA, watcher indicator
C_ACCENT_H  = "#5BA3F0"   # Blue Highlight   — hover state
C_TEXT      = "#E8E8E8"   # Near-White       — primary text
C_MUTED     = "#888888"   # Mid-Gray         — labels, hints, secondary text
C_SUCCESS   = "#4CAF6E"   # Confirmation Green
C_WARNING   = "#E8A838"   # Amber Alert
C_ERROR     = "#E85555"   # Alert Red

# ─── Typography ───────────────────────────────────────────────────────────────

FONT_MONO  = ("Courier New", 11)
FONT_UI    = ("Segoe UI",     10)
FONT_LABEL = ("Segoe UI",      9)
FONT_TITLE = ("Segoe UI",     12, "bold")
FONT_SMALL = ("Segoe UI",      8)

# ─── Timing ───────────────────────────────────────────────────────────────────

CLIPBOARD_POLL_MS: int = 800   # Clipboard watcher poll interval (milliseconds)
NOTIFY_DURATION_MS: int = 4_500  # Notification overlay auto-dismiss duration


# ─── Main widget ──────────────────────────────────────────────────────────────

class BlindTagWidget(ctk.CTk):
    """
    BlindTag observer widget — the primary user-facing interface.

    Inherits from ``ctk.CTk`` (customtkinter root window).
    Instantiate and call ``.mainloop()`` to run:

        widget = BlindTagWidget()
        widget.mainloop()
    """

    def __init__(self) -> None:
        super().__init__()

        # ── Appearance ──────────────────────────────────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Window configuration ────────────────────────────────────────────
        self.title("BlindTag")
        self.geometry("530x555")
        self.minsize(480, 480)
        self.configure(fg_color=C_BG)
        self.attributes("-alpha", 0.96)
        self.resizable(True, True)

        # ── Runtime state ───────────────────────────────────────────────────
        self._current_panel: str = "encode"
        self._clipboard_active: bool = False
        self._last_clipboard: str = ""
        self._watcher_thread: Optional[threading.Thread] = None
        self._notify_frame: Optional[ctk.CTkFrame] = None

        # Window drag state
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0

        # ── Build UI ────────────────────────────────────────────────────────
        self._build_title_bar()
        self._build_panel_toggle()
        self._build_encode_panel()
        self._build_decode_panel()
        self._build_status_bar()

        self._bind_hotkeys()
        self._show_encode()          # Default panel on launch

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _build_title_bar(self) -> None:
        """Custom draggable title bar with logo and window controls."""
        bar = ctk.CTkFrame(self, fg_color=C_SECONDARY, height=40, corner_radius=0)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        logo = ctk.CTkLabel(
            bar, text="⬡  BlindTag",
            font=FONT_TITLE, text_color=C_ACCENT,
        )
        logo.pack(side="left", padx=14, pady=8)

        # Window controls (right-aligned)
        ctrl = ctk.CTkFrame(bar, fg_color="transparent")
        ctrl.pack(side="right", padx=6)

        ctk.CTkButton(
            ctrl, text="✕", width=30, height=26,
            fg_color="transparent", hover_color=C_ERROR,
            text_color=C_MUTED, font=("Segoe UI", 12),
            corner_radius=4, command=self._on_close,
        ).pack(side="right", padx=2, pady=4)

        ctk.CTkButton(
            ctrl, text="─", width=30, height=26,
            fg_color="transparent", hover_color=C_SURFACE,
            text_color=C_MUTED, font=("Segoe UI", 12),
            corner_radius=4, command=self._minimize,
        ).pack(side="right", padx=2, pady=4)

        # Bind window drag to title bar and logo
        for widget in (bar, logo):
            widget.bind("<ButtonPress-1>",   self._drag_start)
            widget.bind("<B1-Motion>",        self._drag_motion)

    def _build_panel_toggle(self) -> None:
        """Encode/Decode segmented toggle strip with Clipboard Watcher checkbox."""
        strip = ctk.CTkFrame(self, fg_color=C_SECONDARY, height=46, corner_radius=0)
        strip.pack(fill="x")
        strip.pack_propagate(False)

        self._toggle = ctk.CTkSegmentedButton(
            strip,
            values=["  Encode  ", "  Decode  "],
            command=self._on_panel_toggle,
            fg_color=C_SURFACE,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACCENT_H,
            unselected_color=C_SURFACE,
            unselected_hover_color="#2C2C2C",
            text_color=C_TEXT,
            font=FONT_UI,
            height=30,
        )
        self._toggle.set("  Encode  ")
        self._toggle.pack(side="left", padx=14, pady=8)

        # Clipboard watcher toggle (right side)
        self._watcher_var = ctk.BooleanVar(value=False)
        self._watcher_chk = ctk.CTkCheckBox(
            strip,
            text=" Clip Watch",
            variable=self._watcher_var,
            command=self._toggle_watcher,
            font=FONT_LABEL,
            text_color=C_MUTED,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT_H,
            checkmark_color="#FFFFFF",
            border_color=C_MUTED,
            width=16, height=16,
            checkbox_height=16, checkbox_width=16,
        )
        self._watcher_chk.pack(side="right", padx=14)

    def _build_encode_panel(self) -> None:
        """Encode surface panel — anchor + hidden message → tagged output."""
        self._encode_frame = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)

        # ── Anchor text input ──────────────────────────────────────────────
        self._section_label(self._encode_frame, "ANCHOR TEXT  ·  visible cover")
        self._anchor_input = self._textbox(
            self._encode_frame, height=82, readonly=False
        )

        # ── Hidden payload input ───────────────────────────────────────────
        self._section_label(self._encode_frame, "HIDDEN PAYLOAD  ·  printable ASCII only")
        self._hidden_input = self._textbox(
            self._encode_frame, height=68, readonly=False
        )

        # ── Output ────────────────────────────────────────────────────────
        self._section_label(self._encode_frame, "OUTPUT  ·  steganographic composite")
        self._encode_output = self._textbox(
            self._encode_frame, height=82, readonly=True, bg=C_SURFACE
        )

        # ── Action row ────────────────────────────────────────────────────
        row = ctk.CTkFrame(self._encode_frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkButton(
            row, text="Encode",
            fg_color=C_SURFACE, hover_color="#333333",
            text_color=C_TEXT, font=FONT_UI, height=36,
            corner_radius=6, command=self._do_encode,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            row, text="⬡  Obfuscate & Copy",
            fg_color=C_ACCENT, hover_color=C_ACCENT_H,
            text_color="#FFFFFF", font=(FONT_UI[0], FONT_UI[1], "bold"),
            height=36, corner_radius=6, command=self._encode_and_copy,
        ).pack(side="right", expand=True, fill="x")

        # ── Clear ─────────────────────────────────────────────────────────
        ctk.CTkButton(
            self._encode_frame, text="Clear All",
            fg_color="transparent", hover_color=C_SURFACE,
            text_color=C_MUTED, font=FONT_LABEL, height=24,
            command=self._clear_encode,
        ).pack(pady=(2, 8))

    def _build_decode_panel(self) -> None:
        """Decode surface panel — raw input → extracted payload."""
        self._decode_frame = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)

        # ── Raw text input ────────────────────────────────────────────────
        self._section_label(
            self._decode_frame,
            "RAW TEXT INPUT  ·  paste steganographic content here",
        )
        self._raw_input = self._textbox(
            self._decode_frame, height=140, readonly=False
        )

        # ── Extracted payload output ──────────────────────────────────────
        self._section_label(self._decode_frame, "EXTRACTED PAYLOAD")
        self._decode_output = self._textbox(
            self._decode_frame, height=120, readonly=True,
            bg=C_SURFACE, text_color=C_SUCCESS,
        )

        # ── Action row ────────────────────────────────────────────────────
        row = ctk.CTkFrame(self._decode_frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkButton(
            row, text="Decode",
            fg_color=C_SURFACE, hover_color="#333333",
            text_color=C_TEXT, font=FONT_UI, height=36,
            corner_radius=6, command=self._do_decode,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            row, text="⬇  Paste & Decode",
            fg_color=C_ACCENT, hover_color=C_ACCENT_H,
            text_color="#FFFFFF", font=(FONT_UI[0], FONT_UI[1], "bold"),
            height=36, corner_radius=6, command=self._paste_and_decode,
        ).pack(side="right", expand=True, fill="x")

        ctk.CTkButton(
            self._decode_frame, text="Clear All",
            fg_color="transparent", hover_color=C_SURFACE,
            text_color=C_MUTED, font=FONT_LABEL, height=24,
            command=self._clear_decode,
        ).pack(pady=(2, 8))

    def _build_status_bar(self) -> None:
        """Bottom status bar — status text and watcher activity indicator."""
        bar = ctk.CTkFrame(self, fg_color=C_SECONDARY, height=28, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._status_label = ctk.CTkLabel(
            bar,
            text=(
                "Ready  ·  Ctrl+E: Encode  "
                "·  Ctrl+D: Decode  ·  Ctrl+W: Watcher"
            ),
            font=FONT_SMALL, text_color=C_MUTED, anchor="w",
        )
        self._status_label.pack(side="left", padx=12, pady=4)

        # Watcher activity dot (right edge)
        self._indicator = ctk.CTkLabel(
            bar, text="●", font=("Segoe UI", 10), text_color=C_SURFACE,
        )
        self._indicator.pack(side="right", padx=12)

    # =========================================================================
    # Shared UI helpers
    # =========================================================================

    @staticmethod
    def _section_label(parent: ctk.CTkFrame, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=FONT_LABEL, text_color=C_MUTED, anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 3))

    @staticmethod
    def _textbox(
        parent: ctk.CTkFrame,
        height: int,
        readonly: bool = False,
        bg: str = C_SECONDARY,
        text_color: str = C_TEXT,
    ) -> ctk.CTkTextbox:
        tb = ctk.CTkTextbox(
            parent,
            height=height,
            fg_color=bg,
            text_color=text_color,
            font=FONT_MONO,
            border_width=1,
            border_color="#303030",
            corner_radius=6,
            wrap="word",
            state="disabled" if readonly else "normal",
        )
        tb.pack(fill="x", padx=16, pady=(0, 4))
        return tb

    @staticmethod
    def _write_textbox(widget: ctk.CTkTextbox, content: str) -> None:
        """Unlock, replace content, re-lock (safe for read-only textboxes)."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if content:
            widget.insert("1.0", content)
        widget.configure(state="disabled")

    # =========================================================================
    # Panel switching
    # =========================================================================

    def _show_encode(self) -> None:
        self._decode_frame.pack_forget()
        self._encode_frame.pack(fill="both", expand=True)
        self._current_panel = "encode"

    def _show_decode(self) -> None:
        self._encode_frame.pack_forget()
        self._decode_frame.pack(fill="both", expand=True)
        self._current_panel = "decode"

    def _on_panel_toggle(self, value: str) -> None:
        if "Encode" in value:
            self._show_encode()
        else:
            self._show_decode()

    # =========================================================================
    # Core actions
    # =========================================================================

    def _do_encode(self) -> None:
        """Validate inputs and run the codec encoder."""
        anchor = self._anchor_input.get("1.0", "end-1c").strip()
        hidden = self._hidden_input.get("1.0", "end-1c").strip()

        if not anchor:
            self._set_status("⚠  Anchor text is required.", C_WARNING)
            return
        if not hidden:
            self._set_status("⚠  Hidden payload is required.", C_WARNING)
            return

        try:
            result = encode(anchor, hidden)
        except InvalidPayloadError as exc:
            self._set_status(f"✕  {exc}", C_ERROR)
            return
        except ValueError as exc:
            self._set_status(f"✕  {exc}", C_ERROR)
            return

        self._write_textbox(self._encode_output, result)
        self._set_status(
            f"✓  Encoded {len(hidden)} char payload into "
            f"{len(anchor)} char anchor  ({len(result)} total chars).",
            C_SUCCESS,
        )

    def _encode_and_copy(self) -> None:
        """Encode and push result directly to system clipboard."""
        self._do_encode()
        result = self._encode_output.get("1.0", "end-1c")
        if not result:
            return
        try:
            pyperclip.copy(result)
            self._set_status("✓  Obfuscated payload copied to clipboard.", C_SUCCESS)
        except Exception as exc:
            self._set_status(f"✕  Clipboard write failed: {exc}", C_ERROR)

    def _do_decode(self) -> None:
        """Scan raw input for embedded Plane 14 payload and surface result."""
        raw = self._raw_input.get("1.0", "end-1c")
        if not raw.strip():
            self._set_status("⚠  Paste or type raw text to scan.", C_WARNING)
            return

        try:
            message = decode(raw)
        except InvalidPayloadError as exc:
            self._write_textbox(self._decode_output, f"[Corrupted payload: {exc}]")
            self._decode_output.configure(text_color=C_ERROR)
            self._set_status(f"✕  Decode error: {exc}", C_ERROR)
            return

        if message:
            self._write_textbox(self._decode_output, message)
            self._decode_output.configure(text_color=C_SUCCESS)
            self._set_status(
                f"✓  Payload extracted — {len(message)} chars.", C_SUCCESS
            )
        else:
            self._write_textbox(
                self._decode_output, "[No Plane 14 payload detected in this text]"
            )
            self._decode_output.configure(text_color=C_MUTED)
            self._set_status("·  No hidden payload found.", C_MUTED)

    def _paste_and_decode(self) -> None:
        """Pull clipboard content and run decoder immediately."""
        try:
            text = pyperclip.paste()
        except Exception as exc:
            self._set_status(f"✕  Clipboard read failed: {exc}", C_ERROR)
            return

        self._raw_input.configure(state="normal")
        self._raw_input.delete("1.0", "end")
        self._raw_input.insert("1.0", text)
        self._do_decode()

    def _clear_encode(self) -> None:
        for widget in (self._anchor_input, self._hidden_input):
            widget.delete("1.0", "end")
        self._write_textbox(self._encode_output, "")
        self._set_status("Cleared.", C_MUTED)

    def _clear_decode(self) -> None:
        self._raw_input.delete("1.0", "end")
        self._write_textbox(self._decode_output, "")
        self._set_status("Cleared.", C_MUTED)

    # =========================================================================
    # Clipboard Watcher
    # =========================================================================

    def _toggle_watcher(self) -> None:
        if self._watcher_var.get():
            self._start_watcher()
        else:
            self._stop_watcher()

    def _start_watcher(self) -> None:
        """Spin up the background clipboard polling thread."""
        self._clipboard_active = True
        self._last_clipboard = ""
        self._watcher_thread = threading.Thread(
            target=self._watcher_loop,
            daemon=True,         # Thread exits when the main process exits
            name="BlindTag-ClipboardWatcher",
        )
        self._watcher_thread.start()
        self._indicator.configure(text_color=C_ACCENT)
        self._set_status(
            "◉  Clipboard Watcher active — scanning for hidden payloads…",
            C_ACCENT,
        )

    def _stop_watcher(self) -> None:
        """Signal the watcher thread to stop and update the UI."""
        self._clipboard_active = False
        self._indicator.configure(text_color=C_SURFACE)
        self._set_status("Clipboard Watcher stopped.", C_MUTED)

    def _watcher_loop(self) -> None:
        """
        Daemon thread body: poll clipboard every CLIPBOARD_POLL_MS milliseconds.

        On detecting new clipboard content, attempts to decode a Plane 14
        payload. Positive results are dispatched back to the main thread via
        ``widget.after()`` to keep all Tkinter calls on the UI thread.
        """
        while self._clipboard_active:
            try:
                current = pyperclip.paste()
            except Exception:
                current = ""

            if current and current != self._last_clipboard:
                self._last_clipboard = current
                try:
                    message = decode(current)
                    if message:
                        # Schedule UI update on the main thread
                        self.after(0, lambda m=message, t=current: self._notify_payload(m, t))
                except (InvalidPayloadError, Exception):
                    pass  # Malformed input — silently skip

            time.sleep(CLIPBOARD_POLL_MS / 1000.0)

    def _notify_payload(self, message: str, raw: str) -> None:
        """
        Surface a notification overlay and auto-populate the Decode panel.

        Called on the main UI thread (dispatched via self.after()).
        Notification frame auto-dismisses after NOTIFY_DURATION_MS.
        """
        # Dismiss any existing notification
        if self._notify_frame is not None:
            try:
                self._notify_frame.destroy()
            except Exception:
                pass
            self._notify_frame = None

        # Switch to decode panel and populate
        self._toggle.set("  Decode  ")
        self._show_decode()
        self._raw_input.configure(state="normal")
        self._raw_input.delete("1.0", "end")
        self._raw_input.insert("1.0", raw)
        self._write_textbox(self._decode_output, message)
        self._decode_output.configure(text_color=C_SUCCESS)

        preview = message[:48] + ("…" if len(message) > 48 else "")
        self._set_status(f"⬡  PAYLOAD DETECTED  →  \"{preview}\"", C_ACCENT)

        # Build floating notification banner
        notif = ctk.CTkFrame(
            self, fg_color=C_ACCENT,
            corner_radius=8, border_width=0,
        )
        notif.place(relx=0.5, rely=0.88, anchor="center", relwidth=0.88)

        ctk.CTkLabel(
            notif,
            text=f"⬡  PAYLOAD DETECTED  ·  {preview}",
            font=(FONT_UI[0], FONT_UI[1], "bold"),
            text_color="#FFFFFF",
        ).pack(padx=14, pady=9)

        self._notify_frame = notif

        # Auto-dismiss
        self.after(NOTIFY_DURATION_MS, self._dismiss_notify)

        # Bring window to front
        self.lift()
        self.focus_force()
        self.attributes("-alpha", 1.0)
        self.after(1500, lambda: self.attributes("-alpha", 0.96))

    def _dismiss_notify(self) -> None:
        if self._notify_frame is not None:
            try:
                self._notify_frame.destroy()
            except Exception:
                pass
            self._notify_frame = None

    # =========================================================================
    # Status bar
    # =========================================================================

    def _set_status(self, message: str, color: str = C_MUTED) -> None:
        self._status_label.configure(text=message, text_color=color)

    # =========================================================================
    # Hotkeys
    # =========================================================================

    def _bind_hotkeys(self) -> None:
        """Register global keyboard shortcuts."""
        self.bind(
            "<Control-e>",
            lambda _: (self._toggle.set("  Encode  "), self._show_encode()),
        )
        self.bind(
            "<Control-d>",
            lambda _: (self._toggle.set("  Decode  "), self._show_decode()),
        )
        self.bind("<Control-w>", lambda _: self._toggle_watcher_hotkey())
        self.bind(
            "<Control-Return>",
            lambda _: (
                self._encode_and_copy()
                if self._current_panel == "encode"
                else self._paste_and_decode()
            ),
        )
        self.bind("<Escape>", lambda _: self._on_close())

    def _toggle_watcher_hotkey(self) -> None:
        new_state = not self._watcher_var.get()
        self._watcher_var.set(new_state)
        self._toggle_watcher()

    # =========================================================================
    # Window management
    # =========================================================================

    def _drag_start(self, event: "tk.Event") -> None:  # type: ignore[name-defined]
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _drag_motion(self, event: "tk.Event") -> None:  # type: ignore[name-defined]
        new_x = self.winfo_x() + event.x - self._drag_start_x
        new_y = self.winfo_y() + event.y - self._drag_start_y
        self.geometry(f"+{new_x}+{new_y}")

    def _minimize(self) -> None:
        self.iconify()

    def _on_close(self) -> None:
        self._stop_watcher()
        self.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────

def run_widget() -> None:
    """
    Launch the BlindTag observer widget.

    Call this function directly or via the ``blindtag-widget`` console script
    installed by pyproject.toml.
    """
    widget = BlindTagWidget()
    widget.mainloop()


if __name__ == "__main__":
    run_widget()
