from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer_app.windows_installer import README_SOURCE, WINDOWS_INSTALLER_DIST, find_latest_wheel

BUILD_ROOT = REPO_ROOT / "report_tmp" / "windows_installer_build"
SCRIPT_PATH = REPO_ROOT / "installer_app" / "windows_installer.py"
ICON_PATH = REPO_ROOT / "assets" / "images" / "blindtag_thumbnail_basic.png"


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "command failed")


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
