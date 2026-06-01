from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer_app.windows_installer import README_SOURCE, WINDOWS_INSTALLER_DIST, find_latest_wheel

BUILD_ROOT = REPO_ROOT / "report_tmp" / "windows_installer_build"
SCRIPT_PATH = REPO_ROOT / "installer_app" / "windows_installer.py"
ICON_PATH = REPO_ROOT / "assets" / "images" / "blindtag_thumbnail_basic.png"
SECURITY_MANIFEST_PATH = BUILD_ROOT / "installer_security_manifest.json"


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "command failed")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_security_manifest(wheel_path: Path) -> Path:
    payload_hashes: dict[str, dict[str, str]] = {
        "wheel": {
            "name": wheel_path.name,
            "sha256": _sha256(wheel_path),
        },
        "readme": {
            "name": README_SOURCE.name,
            "sha256": _sha256(README_SOURCE),
        },
    }
    if ICON_PATH.exists():
        payload_hashes["icon"] = {
            "name": ICON_PATH.name,
            "sha256": _sha256(ICON_PATH),
        }
    payload = {
        "manifest_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "payload_hashes": payload_hashes,
    }
    SECURITY_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECURITY_MANIFEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return SECURITY_MANIFEST_PATH


def build_installer() -> Path:
    wheel_path = find_latest_wheel()
    if wheel_path is None:
        raise FileNotFoundError("No BlindTag wheel was found. Build the package first.")

    if shutil.which("pyinstaller") is None:
        probe = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                "PyInstaller is not available. Install it in the build environment, then rerun this builder."
            )

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    WINDOWS_INSTALLER_DIST.mkdir(parents=True, exist_ok=True)
    security_manifest = _write_security_manifest(wheel_path)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "BlindTagInstaller",
        "--distpath",
        str(WINDOWS_INSTALLER_DIST),
        "--workpath",
        str(BUILD_ROOT / "work"),
        "--specpath",
        str(BUILD_ROOT / "spec"),
        "--add-data",
        f"{wheel_path};payload",
        "--add-data",
        f"{README_SOURCE};payload",
        "--add-data",
        f"{security_manifest};payload",
    ]
    if ICON_PATH.exists():
        command.extend(["--add-data", f"{ICON_PATH};payload"])
    if ICON_PATH.exists():
        command.extend(["--icon", str(ICON_PATH)])
    command.append(str(SCRIPT_PATH))

    _run(command)
    return WINDOWS_INSTALLER_DIST / "BlindTagInstaller.exe"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the BlindTag Windows installer executable.")
    parser.parse_args(argv)
    artifact = build_installer()
    print(str(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
