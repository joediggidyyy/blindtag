"""
test_cli.py — Contract tests for the blindtag unified CLI.

All tests invoke the CLI via subprocess.run(["python", "-m", "blindtag", ...])
to validate entry point routing and exit-code contracts simultaneously.
No test imports main() directly.
"""
import json
import os
import subprocess
import sys

import pytest

from blindtag import __version__

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_UTF8 = {**os.environ, "PYTHONUTF8": "1"}


def _run(*args, input_text=None):
    """Run `python -m blindtag <args>` and return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "blindtag", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=input_text,
        env=_ENV_UTF8,
    )


def _run_shim(shim_fn_name, *args):
    """
    Invoke a named shim function via subprocess to simulate the console-script
    entry point, without requiring the package to be pip-installed.
    """
    argv_repr = repr(list(args))
    script = (
        f"from blindtag.cli import {shim_fn_name}; "
        f"import sys; sys.argv = ['{shim_fn_name}'] + {argv_repr}; "
        f"{shim_fn_name}()"
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_ENV_UTF8,
    )


# ---------------------------------------------------------------------------
# TestVersion
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_flag_exits_zero(self):
        result = _run("--version")
        assert result.returncode == 0

    def test_version_flag_prints_version_string(self):
        result = _run("--version")
        assert f"blindtag {__version__}" in result.stdout


# ---------------------------------------------------------------------------
# TestEncodeSubcommand
# ---------------------------------------------------------------------------

class TestEncodeSubcommand:
    def test_encode_basic_roundtrip_via_decode(self):
        anchor = "Hello World"
        payload = "secret"
        enc = _run("encode", anchor, payload)
        assert enc.returncode == 0
        tagged = enc.stdout.strip()
        dec = _run("decode", tagged)
        assert dec.returncode == 0
        assert dec.stdout.strip() == payload

    def test_encode_json_output_fields(self):
        enc = _run("encode", "Hello World", "secret", "--out", "json")
        assert enc.returncode == 0
        data = json.loads(enc.stdout)
        assert isinstance(data["result"], str)
        assert isinstance(data["anchor_length"], int)
        assert isinstance(data["payload_length"], int)
        assert isinstance(data["total_length"], int)

    def test_encode_invalid_payload_exits_1(self):
        # Non-ASCII payload (caf\xe9) must be rejected at the codec level
        result = _run("encode", "Hello World", "caf\u00e9")
        assert result.returncode == 1
        assert result.stderr.strip() != ""

    def test_encode_usage_error_exits_2(self):
        # Missing second positional arg -> argparse usage error
        result = _run("encode", "Hello World")
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# TestDecodeSubcommand
# ---------------------------------------------------------------------------

class TestDecodeSubcommand:
    def test_decode_found_prints_payload(self):
        payload = "mysecret"
        enc = _run("encode", "anchor text", payload)
        assert enc.returncode == 0
        dec = _run("decode", enc.stdout.strip())
        assert dec.returncode == 0
        assert dec.stdout.strip() == payload

    def test_decode_not_found_prints_nothing_exits_0(self):
        result = _run("decode", "plain text no payload")
        assert result.returncode == 0
        assert result.stdout == ""

    def test_decode_stdin_pipe(self):
        payload = "piped"
        enc = _run("encode", "anchor", payload)
        assert enc.returncode == 0
        dec = _run("decode", "-", input_text=enc.stdout.strip())
        assert dec.returncode == 0
        assert dec.stdout.strip() == payload

    def test_decode_json_output_found(self):
        enc = _run("encode", "anchor", "hello")
        assert enc.returncode == 0
        dec = _run("decode", enc.stdout.strip(), "--out", "json")
        assert dec.returncode == 0
        data = json.loads(dec.stdout)
        assert data["found"] is True
        assert data["message"] == "hello"

    def test_decode_json_output_not_found(self):
        result = _run("decode", "plain text", "--out", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["found"] is False
        assert data["message"] is None

    def test_decode_invalid_plane14_exits_1(self):
        # U+E0001 is a language tag character outside the printable mirror range
        bad = "hello\U000E0001world"
        result = _run("decode", bad)
        assert result.returncode == 1
        assert result.stderr.strip() != ""


# ---------------------------------------------------------------------------
# TestStripSubcommand
# ---------------------------------------------------------------------------

class TestStripSubcommand:
    def test_strip_removes_plane14_chars(self):
        anchor = "clean anchor"
        enc = _run("encode", anchor, "hidden")
        assert enc.returncode == 0
        strip = _run("strip", enc.stdout.strip())
        assert strip.returncode == 0
        assert strip.stdout.strip() == anchor

    def test_strip_stdin_pipe(self):
        anchor = "stdin anchor"
        enc = _run("encode", anchor, "hidden")
        assert enc.returncode == 0
        strip = _run("strip", "-", input_text=enc.stdout.strip())
        assert strip.returncode == 0
        assert strip.stdout.strip() == anchor

    def test_strip_json_output_field(self):
        enc = _run("encode", "anchor", "payload")
        assert enc.returncode == 0
        strip = _run("strip", enc.stdout.strip(), "--out", "json")
        assert strip.returncode == 0
        data = json.loads(strip.stdout)
        assert "result" in data
        assert isinstance(data["result"], str)

    def test_strip_clean_string_passthrough(self):
        clean = "no plane14 here"
        result = _run("strip", clean)
        assert result.returncode == 0
        assert result.stdout.strip() == clean


# ---------------------------------------------------------------------------
# TestApiShim
# ---------------------------------------------------------------------------

class TestApiShim:
    def test_api_shim_delegates_to_cli(self):
        result = _run_shim("_api_shim", "--help")
        assert result.returncode == 0
        assert "api" in result.stdout.lower()

    def test_api_shim_passes_flags_through(self):
        result = _run_shim("_api_shim", "--help")
        assert "--host" in result.stdout or "--port" in result.stdout


# ---------------------------------------------------------------------------
# TestWidgetShim
# ---------------------------------------------------------------------------

class TestWidgetShim:
    def test_widget_subcommand_launches_compat_launcher(self):
        script = (
            "import blindtag.cli; "
            "blindtag.cli._launch_widget_process = lambda: (print('WIDGET_SUBCOMMAND_OK') or 0); "
            "blindtag.cli.main(['widget'])"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_ENV_UTF8,
        )
        assert result.returncode == 0
        assert "WIDGET_SUBCOMMAND_OK" in result.stdout

    def test_widget_shim_launches_widget_directly(self):
        script = (
            "import blindtag.widget; "
            "blindtag.widget.run_widget = lambda: print('WIDGET_SHIM_OK'); "
            "from blindtag.cli import _widget_shim; "
            "_widget_shim()"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_ENV_UTF8,
        )
        assert result.returncode == 0
        assert "WIDGET_SHIM_OK" in result.stdout

    def test_widget_shim_rejects_arguments(self):
        result = _run_shim("_widget_shim", "--help")
        assert result.returncode == 2
        assert "no arguments are supported" in result.stderr.lower()


# ---------------------------------------------------------------------------
# TestHelpPages
# ---------------------------------------------------------------------------

class TestHelpPages:
    def test_root_help_exits_zero(self):
        result = _run("--help")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_encode_help_exits_zero(self):
        result = _run("encode", "--help")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_decode_help_exits_zero(self):
        result = _run("decode", "--help")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_strip_help_exits_zero(self):
        result = _run("strip", "--help")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_api_help_exits_zero(self):
        result = _run("api", "--help")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_widget_help_exits_zero(self):
        result = _run("widget", "--help")
        assert result.returncode == 0
        assert result.stdout.strip() != ""

    def test_root_help_lists_widget_subcommand(self):
        result = _run("--help")
        assert result.returncode == 0
        assert "{encode,decode,strip,api,widget}" in result.stdout
