"""
blindtag.core
=============
Bidirectional Unicode Plane 14 steganographic codec engine.

Mathematical Basis
------------------
Unicode's "Tags" block occupies Plane 14 at U+E0000–U+E007F.
Its 128 codepoints mirror the C0 controls and printable ASCII
range (0x00–0x7F) shifted upward by a fixed offset of 0xE0000:

  Encode:  ord(ascii_char)   + 0xE0000  →  Plane 14 tag codepoint
  Decode:  Plane 14_codepoint - 0xE0000 →  ord(ascii_char)

These tag characters share two critical properties that make them
ideal steganographic carriers:

  1. INVISIBLE — No known production font renders Plane 14 tag glyphs
     as visible ink; renderers treat them as zero-width non-glyphs.

  2. NORMALIZATION-SAFE — The Unicode standard explicitly excludes the
     Tags block from NFC, NFD, NFKC, and NFKD composition/decomposition
     rules (Unicode 15.0 §23.9). A normalized copy of a tagged string
     carries the payload intact.

Payload Framing
---------------
Every payload is bookended at its right edge by U+E007F (TAG CANCEL),
the only Plane 14 character that lies outside the printable ASCII mirror.
The decoder treats this sentinel as an unambiguous end-of-stream marker.

  [ anchor text ][ E0020..E007E payload chars ][ E007F TAG_CANCEL ]

Accepted Payload Character Set
--------------------------------
Printable ASCII: U+0020 (SPACE) through U+007E (TILDE) — 95 characters.
This range maps cleanly into U+E0020–U+E007E, avoiding TAG CANCEL (U+E007F).

Normalization Attack Resistance
---------------------------------
Some text pipelines call unicodedata.normalize() before transmission.
Because Plane 14 characters have Canonical_Decomposition_Type=None and
are excluded from canonical equivalence, NFC and NFD passes are no-ops
over tag sequences. NFKC/NFKD similarly preserve them. The test suite
verifies this property explicitly.
"""

from __future__ import annotations

from .exceptions import InvalidPayloadError

__all__ = [
    "PLANE14_OFFSET",
    "TAG_CANCEL",
    "ASCII_MIN",
    "ASCII_MAX",
    "PLANE14_MIN",
    "PLANE14_MAX",
    "encode",
    "decode",
    "strip_plane14",
]

# ─── Module-level constants ────────────────────────────────────────────────────

PLANE14_OFFSET: int = 0xE0000
"""Integer offset that maps printable ASCII → Plane 14 tag space (= 917,504)."""

TAG_CANCEL: str = "\U000E007F"
"""U+E007F TAG CANCEL — appended as payload end-of-stream sentinel."""

# Printable ASCII window ────────────────────────────────────────────────────────
ASCII_MIN: int = 0x20   # SPACE
ASCII_MAX: int = 0x7E   # TILDE (0x7F DEL is non-printable; excluded)

# Derived Plane 14 payload window (TAG_CANCEL at 0xE007F is outside this range)
PLANE14_MIN: int = PLANE14_OFFSET + ASCII_MIN   # 0xE0020
PLANE14_MAX: int = PLANE14_OFFSET + ASCII_MAX   # 0xE007E


# ─── Internal validation ──────────────────────────────────────────────────────

def _validate_payload(message: str) -> None:
    """
    Assert that every character in *message* is printable ASCII.

    Iterates character-by-character and raises on the first violation,
    providing the index, Unicode codepoint, and repr of the offender.

    Args:
        message: Proposed hidden payload string.

    Raises:
        InvalidPayloadError: If any character has ord() < 0x20 or > 0x7E.
    """
    for idx, char in enumerate(message):
        code = ord(char)
        if code < ASCII_MIN or code > ASCII_MAX:
            raise InvalidPayloadError(
                f"Payload character at index {idx} is invalid — "
                f"U+{code:04X} {char!r} lies outside the allowed "
                f"printable ASCII range [U+{ASCII_MIN:04X}..U+{ASCII_MAX:04X}]. "
                "Accepted characters: SPACE (U+0020) through TILDE (U+007E)."
            )


# ─── Public codec interface ───────────────────────────────────────────────────

def encode(anchor: str, hidden_message: str) -> str:
    """
    Embed *hidden_message* invisibly into *anchor* using Plane 14 tag chars.

    Each ASCII character in the payload is shifted into Plane 14 tag space
    via ``chr(ord(c) + 0xE0000)`` and appended after the visible anchor text.
    The sequence is terminated by U+E007F (TAG CANCEL).

    The returned string is visually identical to *anchor* in all standard
    rendering environments. It passes NFC/NFD/NFKC/NFKD normalization
    with the payload intact.

    Args:
        anchor:         Visible cover text. Any valid Unicode string, including
                        multi-byte emoji, CJK, RTL scripts, etc.
        hidden_message: Secret payload. MUST be printable ASCII only
                        (U+0020–U+007E). Tabs, newlines, NUL bytes, and any
                        non-ASCII character will cause an InvalidPayloadError.

    Returns:
        ``anchor + <plane14_payload_chars> + TAG_CANCEL``

    Raises:
        ValueError:          *anchor* or *hidden_message* is an empty string.
        InvalidPayloadError: *hidden_message* contains a non-printable or
                             non-ASCII character.

    Example:
        >>> tagged = encode("Open me", "PAYLOAD:1")
        >>> decode(tagged)
        'PAYLOAD:1'
        >>> tagged.startswith("Open me")
        True
        >>> len(tagged) > len("Open me")
        True
    """
    if not anchor:
        raise ValueError("anchor must be a non-empty string.")
    if not hidden_message:
        raise ValueError("hidden_message must be a non-empty string.")

    _validate_payload(hidden_message)

    # Shift every payload byte into Plane 14 tag space
    tag_buffer = "".join(chr(ord(ch) + PLANE14_OFFSET) for ch in hidden_message)

    # Frame with TAG CANCEL sentinel at right boundary
    return anchor + tag_buffer + TAG_CANCEL


def decode(raw_text: str) -> str | None:
    """
    Extract the first Plane 14 tag payload embedded in *raw_text*.

    Performs a single linear pass, accumulating tag codepoints in the range
    [U+E0020..U+E007E]. Terminates immediately at U+E007F (TAG CANCEL)
    or end of string. Characters outside the Plane 14 tag range are silently
    ignored (they are part of the visible anchor or unrelated Unicode content).

    Args:
        raw_text: Any Unicode string. May or may not contain a payload.

    Returns:
        The decoded payload string if any tag characters were found,
        otherwise ``None`` (explicit signal: no payload detected).

    Raises:
        InvalidPayloadError: A tag codepoint decodes to a value outside
                             the printable ASCII range — indicates a
                             corrupted or adversarially crafted payload.

    Example:
        >>> decode("Some text with no payload")  # returns None
        >>> decode(encode("cover", "secret"))
        'secret'
    """
    collected: list[str] = []
    found_any: bool = False

    for char in raw_text:
        code = ord(char)

        # TAG CANCEL: hard end-of-stream; stop here even if more chars follow.
        if code == 0xE007F:
            break

        # Plane 14 tag data codepoint — the full Tags block U+E0000..U+E007E.
        # We intentionally scan the *entire* block (not just the valid payload
        # sub-range U+E0020..U+E007E) so that synthetically injected codepoints
        # such as U+E0001 (→ 0x01 SOH) are detected and rejected explicitly
        # rather than silently skipped.  This turns a covert normalisation
        # smuggling attempt into a loud InvalidPayloadError.
        if 0xE0000 <= code <= 0xE007E:
            found_any = True
            ascii_val = code - PLANE14_OFFSET

            # Validate the decoded ASCII value against the printable window.
            # Any codepoint mapping to a control character or DEL byte is
            # considered a corrupted / adversarially crafted payload.
            if ascii_val < ASCII_MIN or ascii_val > ASCII_MAX:
                raise InvalidPayloadError(
                    f"Plane 14 codepoint U+{code:05X} decodes to byte value "
                    f"{ascii_val} (0x{ascii_val:02X}), which is outside the "
                    f"printable ASCII range [U+{ASCII_MIN:04X}..U+{ASCII_MAX:04X}]. "
                    "The embedded payload appears corrupted or adversarially crafted."
                )

            collected.append(chr(ascii_val))

    return "".join(collected) if found_any else None


def strip_plane14(text: str) -> str:
    """
    Remove every Plane 14 tag character (U+E0000–U+E007F) from *text*.

    Use this utility to sanitize strings before display, logging, or storage,
    recovering the clean visible anchor without the invisible payload layer.

    Args:
        text: Input string, potentially carrying an embedded payload.

    Returns:
        A copy of *text* with all Plane 14 codepoints (including TAG CANCEL)
        removed. All other characters — including emoji and non-ASCII — are
        preserved exactly.

    Example:
        >>> strip_plane14(encode("visible anchor", "hidden secret"))
        'visible anchor'
        >>> strip_plane14("no tags here 🌐")
        'no tags here 🌐'
    """
    return "".join(ch for ch in text if not (0xE0000 <= ord(ch) <= 0xE007F))
