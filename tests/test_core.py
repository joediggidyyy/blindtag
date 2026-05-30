"""
tests/test_core.py
==================
Comprehensive unit tests for the BlindTag core codec engine.

Test Coverage
-------------
1. Round-trip integrity under normal and adversarial anchor conditions
2. Hidden message survival through whitespace/newline anchor modifications
3. Multi-byte emoji and alphanumeric anchor edge cases
4. Full printable ASCII payload round-trip
5. Strict boundary validation — InvalidPayloadError for out-of-range chars
6. Crash immunity when fed corrupted or synthetic Plane 14 structures
7. Normalization resistance (NFC / NFD / NFKC / NFKD)
8. TAG_CANCEL termination semantics
9. strip_plane14 sanitization utility
10. Multiple sequential payload handling

Run with:
    pytest tests/test_core.py -v
"""

import unicodedata

import pytest

from blindtag.core import (
    ASCII_MAX,
    ASCII_MIN,
    PLANE14_OFFSET,
    TAG_CANCEL,
    decode,
    encode,
    strip_plane14,
)
from blindtag.exceptions import BlindTagError, DecodingError, InvalidPayloadError


# =============================================================================
# 1. Round-trip integrity
# =============================================================================

class TestRoundTrip:
    """Verify that encoded payloads survive a full encode→decode cycle."""

    def test_basic_string(self) -> None:
        assert decode(encode("Hello, World!", "secret")) == "secret"

    def test_single_char_payload(self) -> None:
        assert decode(encode("A", "X")) == "X"

    def test_full_printable_ascii_payload(self) -> None:
        """All 95 printable ASCII characters survive the round-trip."""
        payload = "".join(chr(c) for c in range(ASCII_MIN, ASCII_MAX + 1))
        assert decode(encode("cover", payload)) == payload

    def test_anchor_preserved_at_string_start(self) -> None:
        anchor = "Visible anchor text."
        result = encode(anchor, "hidden")
        assert result.startswith(anchor)

    def test_anchor_appears_verbatim_in_output(self) -> None:
        """strip_plane14 must recover the anchor exactly."""
        anchor = "Exact anchor string."
        result = encode(anchor, "payload")
        assert strip_plane14(result) == anchor

    def test_tag_cancel_present_in_output(self) -> None:
        result = encode("anchor", "msg")
        assert TAG_CANCEL in result

    def test_output_longer_than_anchor(self) -> None:
        anchor = "short"
        result = encode(anchor, "p")
        assert len(result) > len(anchor)

    def test_spaces_in_payload(self) -> None:
        payload = "hello world 42"
        assert decode(encode("cover", payload)) == payload

    def test_symbols_in_payload(self) -> None:
        payload = r"!@#$%^&*()-_=+[]{};:',.<>?/~`|\\"
        assert decode(encode("cover", payload)) == payload


# =============================================================================
# 2. Whitespace / newline anchor modifications
# =============================================================================

class TestAnchorModification:
    """
    Plane 14 tag characters are non-whitespace; they are appended AFTER
    the anchor text. Modifications to the anchor (newline insertion, space
    collapse, leading/trailing strip) should not disturb payload recovery
    because the tag chars remain at the tail of the composite string.
    """

    def test_payload_survives_newline_in_anchor(self) -> None:
        anchor = "Line one\nLine two\n\nLine three"
        payload = "integrity_check"
        assert decode(encode(anchor, payload)) == payload

    def test_payload_survives_double_spaces_in_anchor(self) -> None:
        anchor = "Word   with   many   spaces"
        payload = "spaceproof"
        assert decode(encode(anchor, payload)) == payload

    def test_payload_survives_mixed_whitespace_anchor(self) -> None:
        anchor = "Tab\there\r\nand\r\nnewlines"
        payload = "whitespace_safe"
        assert decode(encode(anchor, payload)) == payload

    def test_payload_intact_after_anchor_rstrip(self) -> None:
        """
        Simulate the case where a consumer right-strips the string but
        Plane 14 chars are not considered whitespace by str.rstrip().
        """
        encoded = encode("trailing spaces   ", "checksum")
        # rstrip removes regular trailing spaces; tag chars are NOT whitespace
        stripped = encoded.rstrip(" ")
        assert decode(stripped) == "checksum"

    def test_payload_intact_after_anchor_lstrip(self) -> None:
        encoded = encode("   leading spaces", "lstrip_ok")
        # lstrip on the result: tag chars appear after anchor, not at start
        assert decode(encoded.lstrip(" ")) == "lstrip_ok"


# =============================================================================
# 3. Multi-byte emoji and mixed-script anchor edge cases
# =============================================================================

class TestAnchorEdgeCases:
    """Ensure multi-codepoint anchor content doesn't affect codec behaviour."""

    def test_emoji_anchor(self) -> None:
        """Multi-byte emoji in anchor must not corrupt payload recovery."""
        anchor = "🔐 Secure transmission 🌐"
        assert decode(encode(anchor, "emoji_safe")) == "emoji_safe"

    def test_emoji_only_anchor(self) -> None:
        anchor = "🎉🚀🛡️🔑"
        assert decode(encode(anchor, "emoji_only")) == "emoji_only"

    def test_cjk_anchor(self) -> None:
        anchor = "机密信息传输协议"
        assert decode(encode(anchor, "cjk_anchor")) == "cjk_anchor"

    def test_rtl_anchor(self) -> None:
        anchor = "بروتوكول نقل البيانات"
        assert decode(encode(anchor, "rtl_anchor")) == "rtl_anchor"

    def test_alphanumeric_anchor(self) -> None:
        anchor = "AnchorText123ABC"
        assert decode(encode(anchor, "alpha_num_42")) == "alpha_num_42"

    def test_punctuation_heavy_anchor(self) -> None:
        anchor = "!!!... Hello --- World ???"
        assert decode(encode(anchor, "punctuation")) == "punctuation"

    def test_combined_emoji_and_unicode_anchor(self) -> None:
        anchor = "日本 🗾 Tokyo 🔐 ¥1000"
        assert decode(encode(anchor, "combo")) == "combo"


# =============================================================================
# 4. Payload validation — InvalidPayloadError boundary enforcement
# =============================================================================

class TestValidationBoundaries:
    """Strict ASCII enforcement: every violation must raise InvalidPayloadError."""

    def test_non_ascii_latin_char_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "café")  # é = U+00E9

    def test_chinese_char_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "机密")

    def test_emoji_in_payload_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "secret🔑")

    def test_nul_byte_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "null\x00byte")

    def test_newline_in_payload_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "line\nbreak")  # LF = 0x0A

    def test_carriage_return_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "line\rreturn")  # CR = 0x0D

    def test_tab_in_payload_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "has\ttab")  # HT = 0x09

    def test_del_char_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "del\x7f")  # DEL = 0x7F (excluded; above TILDE)

    def test_control_char_raises(self) -> None:
        with pytest.raises(InvalidPayloadError):
            encode("anchor", "\x01\x02\x03")

    def test_empty_hidden_message_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            encode("anchor", "")

    def test_empty_anchor_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            encode("", "payload")

    def test_error_message_includes_index_and_codepoint(self) -> None:
        """The exception message must identify the offending character's position."""
        with pytest.raises(InvalidPayloadError, match=r"index 3"):
            encode("cover", "ABC\x00DEF")  # NUL at index 3


# =============================================================================
# 5. Decode — no payload scenarios
# =============================================================================

class TestDecodeNoPayload:
    """decode() must return None (not raise, not return empty str) on clean text."""

    def test_plain_ascii_returns_none(self) -> None:
        assert decode("Regular plain text string!") is None

    def test_empty_string_returns_none(self) -> None:
        assert decode("") is None

    def test_emoji_only_returns_none(self) -> None:
        assert decode("🔥🎉🚀") is None

    def test_unicode_non_plane14_returns_none(self) -> None:
        assert decode("日本語テスト مرحبا") is None

    def test_only_tag_cancel_yields_none(self) -> None:
        """
        TAG_CANCEL with no preceding data characters:
        found_any remains False → None expected.
        The break fires before any codepoint sets found_any=True.
        """
        result = decode("anchor" + TAG_CANCEL)
        assert result is None


# =============================================================================
# 6. Crash immunity — corrupted / adversarial Plane 14 input
# =============================================================================

class TestCrashImmunity:
    """
    Requirement 3: The decoder must never crash on arbitrary input,
    even synthetic Plane 14 structures that encode out-of-range bytes.
    """

    def test_decode_does_not_crash_on_random_unicode(self) -> None:
        samples = [
            "日本語テスト",
            "مرحبا بالعالم",
            "Ø∑≈ç√∫˜µ≤≥÷",
            "\U0001F600\U0001F4A5\U0001F308",
            "\x00\x01\x02\x7F\xFF",
        ]
        for s in samples:
            result = decode(s)
            assert result is None or isinstance(result, str)

    def test_corrupted_plane14_below_min_raises(self) -> None:
        """
        U+E0001 maps to ASCII 0x01 (SOH) — a control char below ASCII_MIN.
        The decoder must raise InvalidPayloadError, not crash silently.
        """
        corrupted = "prefix" + chr(0xE0001) + TAG_CANCEL
        with pytest.raises(InvalidPayloadError):
            decode(corrupted)

    def test_plane14_at_exact_ascii_min_boundary(self) -> None:
        """U+E0020 = SPACE (0x20 = ASCII_MIN) — must decode cleanly."""
        text = "a" + chr(PLANE14_OFFSET + ASCII_MIN) + TAG_CANCEL
        assert decode(text) == " "

    def test_plane14_at_exact_ascii_max_boundary(self) -> None:
        """U+E007E = TILDE (0x7E = ASCII_MAX) — must decode cleanly."""
        text = "a" + chr(PLANE14_OFFSET + ASCII_MAX) + TAG_CANCEL
        assert decode(text) == "~"

    def test_tag_cancel_as_only_plane14_char_no_crash(self) -> None:
        """TAG_CANCEL alone must not crash."""
        assert decode(TAG_CANCEL) is None or decode(TAG_CANCEL) == ""

    def test_interspersed_garbage_and_tags_no_crash(self) -> None:
        """Interleaved non-tag Unicode with tag chars must not crash."""
        mixed = "abc" + chr(PLANE14_OFFSET + 0x41) + "中文" + TAG_CANCEL
        result = decode(mixed)
        assert isinstance(result, (str, type(None)))

    def test_very_long_clean_string_no_crash(self) -> None:
        """10 000-char clean string must not crash or time out."""
        result = decode("A" * 10_000)
        assert result is None

    def test_very_long_encoded_payload_no_crash(self) -> None:
        """512-char payload round-trip must complete without error."""
        payload = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" * 10
        result = decode(encode("cover", payload[:512]))
        assert result == payload[:512]


# =============================================================================
# 7. Normalization resistance (NFC / NFD / NFKC / NFKD)
# =============================================================================

class TestNormalizationResistance:
    """
    Unicode §23.9 explicitly excludes the Tags block (U+E0000–U+E007F)
    from NFC, NFD, NFKC, and NFKD normalization. These tests verify the
    property holds in the Python unicodedata module implementation.
    """

    def test_nfc_preserves_payload(self) -> None:
        encoded = encode("café meeting notes", "nfc_safe")
        assert decode(unicodedata.normalize("NFC", encoded)) == "nfc_safe"

    def test_nfd_preserves_payload(self) -> None:
        encoded = encode("résumé template", "nfd_safe")
        assert decode(unicodedata.normalize("NFD", encoded)) == "nfd_safe"

    def test_nfkc_preserves_payload(self) -> None:
        # ﬁ (U+FB01) is a ligature that NFKC expands to 'fi'
        encoded = encode("ﬁle system access log", "nfkc_test")
        normalized = unicodedata.normalize("NFKC", encoded)
        assert decode(normalized) == "nfkc_test"

    def test_nfkd_preserves_payload(self) -> None:
        encoded = encode("Ångström measurement", "nfkd_test")
        normalized = unicodedata.normalize("NFKD", encoded)
        assert decode(normalized) == "nfkd_test"

    def test_double_nfc_pass_preserves_payload(self) -> None:
        """Two sequential NFC passes must still preserve the payload."""
        encoded = encode("double pass", "idempotent")
        twice = unicodedata.normalize("NFC", unicodedata.normalize("NFC", encoded))
        assert decode(twice) == "idempotent"


# =============================================================================
# 8. TAG_CANCEL termination semantics
# =============================================================================

class TestTagCancelSemantics:
    """TAG_CANCEL (U+E007F) must act as a hard stop for the decoder."""

    def test_content_after_tag_cancel_ignored(self) -> None:
        """
        Characters following the TAG_CANCEL sentinel — even valid
        Plane 14 tags — must not be decoded.
        """
        first = encode("anchor", "first")
        # Manually append a second payload block after the first TAG_CANCEL
        extra = chr(PLANE14_OFFSET + ord("Z")) * 5 + TAG_CANCEL
        result = decode(first + extra)
        assert result == "first"

    def test_sequential_encodes_only_first_decoded(self) -> None:
        """encode(encode(...)) → only the FIRST payload survives decode."""
        double = encode(encode("anchor", "alpha"), "beta")
        assert decode(double) == "alpha"


# =============================================================================
# 9. strip_plane14 utility
# =============================================================================

class TestStripPlane14:
    """The sanitization utility must cleanly remove all tag characters."""

    def test_strip_restores_anchor_exactly(self) -> None:
        anchor = "This is the visible text. 🌐"
        assert strip_plane14(encode(anchor, "payload")) == anchor

    def test_strip_removes_tag_cancel(self) -> None:
        assert TAG_CANCEL not in strip_plane14("text" + TAG_CANCEL)

    def test_strip_passthrough_on_clean_text(self) -> None:
        clean = "No tags here whatsoever. 🎉 中文"
        assert strip_plane14(clean) == clean

    def test_strip_removes_all_plane14_range(self) -> None:
        """Every codepoint in [U+E0000..U+E007F] must be stripped."""
        plane14_chars = "".join(chr(c) for c in range(0xE0000, 0xE0080))
        result = strip_plane14("prefix" + plane14_chars + "suffix")
        assert result == "prefixsuffix"

    def test_strip_empty_string(self) -> None:
        assert strip_plane14("") == ""

    def test_strip_only_tags_yields_empty(self) -> None:
        tags_only = "".join(chr(PLANE14_OFFSET + c) for c in range(5)) + TAG_CANCEL
        assert strip_plane14(tags_only) == ""


# =============================================================================
# 10. DecodingError exception hierarchy
# =============================================================================

class TestDecodingError:
    """DecodingError is defined in the exception hierarchy for future use."""

    def test_decoding_error_is_blindtag_error_subclass(self) -> None:
        assert issubclass(DecodingError, BlindTagError)

    def test_decoding_error_is_exception_subclass(self) -> None:
        assert issubclass(DecodingError, Exception)

    def test_decoding_error_can_be_raised_and_caught(self) -> None:
        with pytest.raises(DecodingError):
            raise DecodingError("synthetic decoder failure")

    def test_decoding_error_caught_as_blindtag_error(self) -> None:
        """BlindTagError is a valid catch-all for all codec exceptions."""
        with pytest.raises(BlindTagError):
            raise DecodingError("caught via base class")

    def test_invalid_payload_error_is_blindtag_error_subclass(self) -> None:
        """Confirm the full hierarchy is consistent."""
        assert issubclass(InvalidPayloadError, BlindTagError)


# =============================================================================
# 11. Long payload integrity
# =============================================================================

class TestLongPayloads:
    """Stress tests with payloads approaching practical limits."""

    def test_128_char_payload(self) -> None:
        payload = "A" * 64 + "z0" * 32
        assert decode(encode("anchor", payload)) == payload

    def test_512_char_mixed_payload(self) -> None:
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@"
        payload = (chars * 8)[:512]
        assert decode(encode("anchor", payload)) == payload

    def test_payload_with_only_spaces(self) -> None:
        payload = " " * 20
        assert decode(encode("anchor", payload)) == payload

    def test_payload_with_only_tildes(self) -> None:
        payload = "~" * 20
        assert decode(encode("anchor", payload)) == payload
