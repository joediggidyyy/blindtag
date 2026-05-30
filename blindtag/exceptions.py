"""
blindtag.exceptions
===================
Structured exception hierarchy for the BlindTag codec pipeline.

All exceptions are surfaced with descriptive messages that guide
the caller toward the exact boundary violation that triggered them.
"""


class BlindTagError(Exception):
    """Base class for all BlindTag domain exceptions."""


class InvalidPayloadError(BlindTagError):
    """
    Raised when a proposed hidden_message payload cannot be encoded into
    Unicode Plane 14 tag space.

    Plane 14 tag characters mirror printable ASCII (U+0020–U+007E shifted
    by 0xE0000). Characters outside this window — control bytes, multi-byte
    Unicode scalars, or surrogate pairs — have no valid tag representation
    and will always trigger this exception.

    Attributes:
        message: Human-readable description of the offending character
                 and its position in the input string.
    """


class DecodingError(BlindTagError):
    """
    Raised when a Plane 14 tag sequence resolves to an out-of-range byte,
    indicating the payload buffer is corrupted, truncated, or synthetically
    crafted to probe decoder behaviour.
    """
