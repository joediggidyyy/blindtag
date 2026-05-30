"""
BlindTag — Unicode Plane 14 Steganographic Toolkit
====================================================
Bidirectional encoder/decoder for invisible Plane 14 tag character payloads.

Quick start::

    from blindtag import encode, decode, strip_plane14

    tagged = encode("Meeting notes from Q3 review.", "CONFIDENTIAL:REF-7821")
    print(decode(tagged))    # → 'CONFIDENTIAL:REF-7821'
    print(strip_plane14(tagged))  # → 'Meeting notes from Q3 review.'

Modules
-------
blindtag.core       — Codec engine (encode / decode / strip_plane14)
blindtag.api        — FastAPI local transport layer
blindtag.widget     — Desktop observer widget (customtkinter)
blindtag.exceptions — Domain exception hierarchy
"""

from .core import decode, encode, strip_plane14
from .exceptions import BlindTagError, DecodingError, InvalidPayloadError

__version__ = "1.0.0"
__author__ = "BlindTag Engineering"

__all__ = [
    "encode",
    "decode",
    "strip_plane14",
    "BlindTagError",
    "InvalidPayloadError",
    "DecodingError",
]
