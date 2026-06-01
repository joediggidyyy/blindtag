from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

INSTALL_MODE_DEFAULT = "default"
INSTALL_MODE_ADVANCED = "advanced"
INSTALL_MODE_CHOICES = (INSTALL_MODE_DEFAULT, INSTALL_MODE_ADVANCED)

INSTALLER_MODES: dict[str, dict[str, Any]] = {
    INSTALL_MODE_DEFAULT: {
        "label": "Default (Recommended)",
        "recommended": True,
        "description": "Best for recreational and everyday BlindTag use.",
        "warning": "",
    },
    INSTALL_MODE_ADVANCED: {
        "label": "Advanced",
        "recommended": False,
        "description": "Custom setup path for operators who specifically need non-default behavior.",
        "warning": "Use Advanced only when you need custom installation behavior.",
    },
}

INSTALLER_OPTION_SPECS: list[dict[str, Any]] = [
    {"key": "create_shortcut", "label": "Create shortcut", "default": True},
    {"key": "enable_quick_launch", "label": "Enable quick launch", "default": True},
    {"key": "display_readme", "label": "Display README.md after install", "default": True},
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT = REPO_ROOT / "dist"
REPORT_TMP_DIST_ROOT = REPO_ROOT / "report_tmp" / "pass_s_dist"
WINDOWS_INSTALLER_DIST = DIST_ROOT / "windows-installer"
DEFAULT_INSTALL_DIR = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "BlindTag"
PYTHON_MIN_VERSION = "3.11"
PYTHON_BOOTSTRAP_VERSION = "3.12.10"
PYTHON_BOOTSTRAP_WINGET_ID = "Python.Python.3.12"
PYTHON_BOOTSTRAP_URL = f"https://www.python.org/ftp/python/{PYTHON_BOOTSTRAP_VERSION}/python-{PYTHON_BOOTSTRAP_VERSION}-amd64.exe"
PYTHON_BOOTSTRAP_SIGNER_SUBSTRING = "Python Software Foundation"
SECURITY_MANIFEST_FILENAME = "installer_security_manifest.json"


def _payload_root() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "payload"
    return None


def _resolve_payload_file(name: str, fallback: Path) -> Path:
    payload_root = _payload_root()
    if payload_root is not None:
        candidate = payload_root / name
        if candidate.exists():
            return candidate
    return fallback


README_SOURCE = _resolve_payload_file("README.md", REPO_ROOT / "README.md")
SHORTCUT_ICON_SOURCE = _resolve_payload_file(
    "blindtag_thumbnail_basic.png",
    REPO_ROOT / "assets" / "images" / "blindtag_thumbnail_basic.png",
)
SECURITY_MANIFEST_SOURCE = _resolve_payload_file(
    SECURITY_MANIFEST_FILENAME,
    REPO_ROOT / "report_tmp" / "windows_installer_build" / SECURITY_MANIFEST_FILENAME,
)


@dataclass(frozen=True)
class InstallerPlan:
    mode: str
    install_dir: str
    wheel_path: str
    readme_path: str
    create_shortcut: bool
    enable_quick_launch: bool
    display_readme: bool
    recommended: bool
    mode_label: str
    mode_warning: str
    widget_launcher: str
    cli_launcher: str
    install_manifest_path: str
    security_manifest_path: str
    auto_install_python: bool
    automatic_elevation: bool
    python_bootstrap_strategy: str
    verify_payload_hashes: bool


def find_latest_wheel(search_roots: list[Path] | None = None) -> Path | None:
    payload_root = _payload_root()
    roots = search_roots or ([payload_root] if payload_root is not None else []) + [DIST_ROOT, REPORT_TMP_DIST_ROOT]
    wheels: list[Path] = []
    for root in roots:
        if root is None:
            continue
        if not root.exists():
            continue
        wheels.extend(sorted(root.rglob("blindtag-*.whl")))
    if not wheels:
        return None
    return max(wheels, key=lambda path: path.stat().st_mtime)


def _default_option_map() -> dict[str, bool]:
    return {spec["key"]: bool(spec["default"]) for spec in INSTALLER_OPTION_SPECS}


def build_install_plan(
    mode: str = INSTALL_MODE_DEFAULT,
    install_dir: str | Path | None = None,
    *,
    create_shortcut: bool | None = None,
    enable_quick_launch: bool | None = None,
    display_readme: bool | None = None,
    wheel_path: str | Path | None = None,
    readme_path: str | Path | None = None,
) -> InstallerPlan:
    option_defaults = _default_option_map()
    install_root = Path(install_dir) if install_dir else DEFAULT_INSTALL_DIR
    wheel = Path(wheel_path) if wheel_path else find_latest_wheel()
    readme = Path(readme_path) if readme_path else README_SOURCE

    if mode not in INSTALL_MODE_CHOICES:
        raise ValueError(f"Unsupported installer mode: {mode}")
    if wheel is None:
        raise FileNotFoundError("No BlindTag wheel was found under dist/ or report_tmp/pass_s_dist/.")

    runtime_dir = install_root / "runtime"
    widget_launcher = runtime_dir / "Scripts" / "blindtag-widget.exe"
    cli_launcher = runtime_dir / "Scripts" / "blindtag.exe"
    manifest_path = install_root / "install_manifest.json"
    mode_meta = INSTALLER_MODES[mode]

    return InstallerPlan(
        mode=mode,
        install_dir=str(install_root),
        wheel_path=str(wheel),
        readme_path=str(readme),
        create_shortcut=option_defaults["create_shortcut"] if create_shortcut is None else create_shortcut,
        enable_quick_launch=option_defaults["enable_quick_launch"] if enable_quick_launch is None else enable_quick_launch,
        display_readme=option_defaults["display_readme"] if display_readme is None else display_readme,
        recommended=bool(mode_meta["recommended"]),
        mode_label=str(mode_meta["label"]),
        mode_warning=str(mode_meta["warning"]),
        widget_launcher=str(widget_launcher),
        cli_launcher=str(cli_launcher),
        install_manifest_path=str(manifest_path),
        security_manifest_path=str(SECURITY_MANIFEST_SOURCE),
        auto_install_python=True,
        automatic_elevation=True,
        python_bootstrap_strategy="automatic-python-bootstrap",
        verify_payload_hashes=True,
    )


def validate_install_plan(plan: InstallerPlan) -> list[str]:
    errors: list[str] = []
    if plan.mode not in INSTALL_MODE_CHOICES:
        errors.append(f"unsupported mode: {plan.mode}")
    if not Path(plan.wheel_path).exists():
        errors.append(f"wheel not found: {plan.wheel_path}")
    if not Path(plan.readme_path).exists():
        errors.append(f"README not found: {plan.readme_path}")
    if not plan.install_dir:
        errors.append("install_dir is required")
    if not all(spec["key"] in plan.__dict__ for spec in INSTALLER_OPTION_SPECS):
        errors.append("installer options are incomplete")
    return errors


def build_contract_summary() -> dict[str, Any]:
    return {
        "modes": INSTALLER_MODES,
        "options": INSTALLER_OPTION_SPECS,
        "default_install_dir": str(DEFAULT_INSTALL_DIR),
        "wheel_found": str(find_latest_wheel()) if find_latest_wheel() else None,
        "security": {
            "payload_hash_verification": True,
            "security_manifest_path": str(SECURITY_MANIFEST_SOURCE),
            "python_bootstrap_signature_validation": True,
            "fail_closed_on_integrity_mismatch": True,
        },
        "bootstrap": {
            "auto_python_install": True,
            "python_min_version": PYTHON_MIN_VERSION,
            "preferred_python_version": PYTHON_BOOTSTRAP_VERSION,
            "automatic_elevation": True,
            "behavior": "Installer resolves Python/runtime dependencies automatically and requests Windows elevation only when required.",
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_security_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_payload_integrity(plan: InstallerPlan) -> dict[str, Any]:
    manifest_path = Path(plan.security_manifest_path)
    if not manifest_path.exists():
        raise RuntimeError(f"Installer security manifest not found: {manifest_path}")

    manifest = _load_security_manifest(manifest_path)
    manifest_hashes = manifest.get("payload_hashes")
    if not isinstance(manifest_hashes, dict):
        raise RuntimeError("Installer security manifest is missing payload_hashes.")

    payload_map: dict[str, Path] = {
        "wheel": Path(plan.wheel_path),
        "readme": Path(plan.readme_path),
    }
    if SHORTCUT_ICON_SOURCE.exists():
        payload_map["icon"] = SHORTCUT_ICON_SOURCE

    verified_items: dict[str, dict[str, str]] = {}
    for key, path in payload_map.items():
        expected_entry = manifest_hashes.get(key)
        if not isinstance(expected_entry, dict):
            raise RuntimeError(f"Installer security manifest is missing the {key} payload entry.")
        expected_hash = str(expected_entry.get("sha256") or "").strip().lower()
        if not expected_hash:
            raise RuntimeError(f"Installer security manifest is missing the {key} sha256 value.")
        actual_hash = _sha256(path)
        if actual_hash.lower() != expected_hash:
            raise RuntimeError(
                f"{key.capitalize()} hash verification failed for {path.name}. Expected {expected_hash}, received {actual_hash}."
            )
        verified_items[key] = {
            "path": str(path),
            "sha256": actual_hash,
        }

    return {
        "manifest_path": str(manifest_path),
        "verified": True,
        "manifest_version": manifest.get("manifest_version"),
        "verified_items": verified_items,
    }


def _run_command(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "command failed")


def _run_command_result(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def _supports_python_version(version_text: str) -> bool:
    normalized = version_text.strip()
    return any(f"Python {major_minor}" in normalized for major_minor in ("3.11", "3.12", "3.13"))


def _command_available(command: list[str]) -> bool:
    try:
        completed = _run_command_result(command)
    except OSError:
        return False
    return completed.returncode == 0


def _is_windows() -> bool:
    return os.name == "nt"


def _common_python_install_locations() -> list[Path]:
    versions = ("313", "312", "311")
    env_roots = [
        os.getenv("ProgramFiles"),
        os.getenv("LocalAppData"),
    ]
    base_roots = [Path(root) for root in env_roots if root]
    candidates: list[Path] = []
    for root in base_roots:
        candidates.extend(
            [
                root / "Python" / f"Python{version}" / "python.exe"
                for version in versions
            ]
        )
        candidates.extend(
            [
                root / "Programs" / "Python" / f"Python{version}" / "python.exe"
                for version in versions
            ]
        )
    return candidates


def _is_running_as_admin() -> bool:
    if not _is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_elevated_process(command: list[str]) -> None:
    if not _is_windows():
        raise RuntimeError("Elevation helper is only available on Windows.")
    file_path = command[0].replace("'", "''")
    args = ", ".join(f"'{argument.replace("'", "''")}'" for argument in command[1:])
    command_text = (
        f"$process = Start-Process -FilePath '{file_path}' -ArgumentList @({args}) -Verb RunAs -Wait -PassThru; "
        "if ($null -eq $process) { exit 1 }; exit $process.ExitCode"
    )
    completed = _run_command_result(["powershell", "-NoProfile", "-Command", command_text])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Elevated process failed")


def _try_discover_python_command() -> list[str] | None:
    try:
        return _discover_python_command()
    except RuntimeError:
        return None


def _discover_python_command() -> list[str]:
    candidates = []
    if not getattr(sys, "frozen", False):
        candidates.append([sys.executable])
    candidates.extend([
        ["py", "-3.11"],
        ["py", "-3.12"],
        ["py", "-3.13"],
        ["py", "-3"],
        ["python"],
        ["python3"],
    ])
    candidates.extend([[str(path)] for path in _common_python_install_locations() if path.exists()])
    for candidate in candidates:
        try:
            completed = subprocess.run(
                [*candidate, "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if completed.returncode != 0:
            continue
        version_text = (completed.stdout or completed.stderr).strip()
        if _supports_python_version(version_text):
            return candidate
    raise RuntimeError("Python 3.11+ was not found. Install Python 3.11 or later, then rerun the installer.")


def _download_python_bootstrap_installer() -> Path:
    target = Path(tempfile.gettempdir()) / f"python-{PYTHON_BOOTSTRAP_VERSION}-amd64.exe"
    urllib.request.urlretrieve(PYTHON_BOOTSTRAP_URL, target)
    return target


def _verify_bootstrap_installer_signature(installer_path: Path) -> dict[str, str]:
    command_text = (
        "$sig = Get-AuthenticodeSignature -FilePath '"
        + str(installer_path).replace("'", "''")
        + "'; "
        + "[pscustomobject]@{Status=[string]$sig.Status; Subject=[string]$sig.SignerCertificate.Subject; Issuer=[string]$sig.SignerCertificate.Issuer} | ConvertTo-Json -Compress"
    )
    completed = _run_command_result(["powershell", "-NoProfile", "-Command", command_text])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Bootstrap signature validation failed")
    payload = json.loads((completed.stdout or "{}").strip() or "{}")
    status = str(payload.get("Status") or "")
    subject = str(payload.get("Subject") or "")
    if status != "Valid":
        raise RuntimeError(f"Bootstrap installer signature is not valid. Status: {status or 'unknown'}")
    if PYTHON_BOOTSTRAP_SIGNER_SUBSTRING.lower() not in subject.lower():
        raise RuntimeError(
            "Bootstrap installer signer is not trusted. "
            f"Expected signer containing '{PYTHON_BOOTSTRAP_SIGNER_SUBSTRING}', received '{subject or 'unknown'}'."
        )
    return {
        "status": status,
        "subject": subject,
        "issuer": str(payload.get("Issuer") or ""),
    }


def _install_python_with_winget() -> bool:
    if not _command_available(["winget", "--version"]):
        return False
    user_command = [
        "winget",
        "install",
        "--exact",
        "--id",
        PYTHON_BOOTSTRAP_WINGET_ID,
        "--accept-package-agreements",
        "--accept-source-agreements",
        "--disable-interactivity",
        "--scope",
        "user",
    ]
    first_attempt = _run_command_result(user_command)
    if first_attempt.returncode == 0:
        return True
    machine_command = [*user_command[:-2], "machine"]
    _run_elevated_process(machine_command)
    return True


def _install_python_from_bootstrap_installer() -> bool:
    installer_path = _download_python_bootstrap_installer()
    _verify_bootstrap_installer_signature(installer_path)
    user_command = [
        str(installer_path),
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_pip=1",
        "Include_launcher=1",
        "Shortcuts=0",
        "SimpleInstall=1",
    ]
    first_attempt = _run_command_result(user_command)
    if first_attempt.returncode == 0:
        return True
    machine_command = [
        str(installer_path),
        "/quiet",
        "InstallAllUsers=1",
        "PrependPath=1",
        "Include_pip=1",
        "Include_launcher=1",
        "Shortcuts=0",
        "SimpleInstall=1",
    ]
    _run_elevated_process(machine_command)
    return True


def ensure_python_runtime() -> tuple[list[str], dict[str, Any]]:
    discovered = _try_discover_python_command()
    if discovered is not None:
        return discovered, {"method": "existing-python", "elevated": False}
    if not _is_windows():
        raise RuntimeError("Python 3.11+ was not found and automatic bootstrap is only supported on Windows.")
    if _install_python_with_winget():
        discovered = _try_discover_python_command()
        if discovered is not None:
            return discovered, {"method": "winget", "elevated": False if _is_running_as_admin() else True}
    if _install_python_from_bootstrap_installer():
        discovered = _try_discover_python_command()
        if discovered is not None:
            return discovered, {"method": "python-bootstrap-installer", "elevated": False if _is_running_as_admin() else True}
    raise RuntimeError("BlindTag could not bootstrap Python 3.11+ automatically.")


def _desktop_shortcut_path() -> Path:
    return Path.home() / "Desktop" / "BlindTag.lnk"


def _quick_launch_shortcut_path() -> Path:
    return Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Internet Explorer" / "Quick Launch" / "BlindTag.lnk"


def _create_shortcut(shortcut_path: Path, target_path: Path, working_dir: Path, icon_path: Path | None = None) -> None:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    target_text = str(target_path).replace("'", "''")
    working_text = str(working_dir).replace("'", "''")
    shortcut_text = str(shortcut_path).replace("'", "''")
    icon_line = ""
    if icon_path is not None and icon_path.exists():
        icon_text = str(icon_path).replace("'", "''")
        icon_line = f"$shortcut.IconLocation = '{icon_text}';"
    command = (
        "$wsh = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $wsh.CreateShortcut('{shortcut_text}'); "
        f"$shortcut.TargetPath = '{target_text}'; "
        f"$shortcut.WorkingDirectory = '{working_text}'; "
        f"{icon_line} "
        "$shortcut.Save()"
    )
    _run_command(["powershell", "-NoProfile", "-Command", command])


def perform_install(plan: InstallerPlan, *, dry_run: bool = False) -> dict[str, Any]:
    errors = validate_install_plan(plan)
    if errors:
        raise ValueError("; ".join(errors))

    install_root = Path(plan.install_dir)
    runtime_dir = install_root / "runtime"
    readme_target = install_root / "README.md"
    widget_launcher = Path(plan.widget_launcher)
    icon_path = SHORTCUT_ICON_SOURCE

    actions = {
        "install_dir": str(install_root),
        "runtime_dir": str(runtime_dir),
        "wheel_path": plan.wheel_path,
        "readme_source": plan.readme_path,
        "security_manifest_path": plan.security_manifest_path,
        "widget_launcher": plan.widget_launcher,
        "create_shortcut": plan.create_shortcut,
        "enable_quick_launch": plan.enable_quick_launch,
        "display_readme": plan.display_readme,
        "auto_install_python": plan.auto_install_python,
        "automatic_elevation": plan.automatic_elevation,
        "python_bootstrap_strategy": plan.python_bootstrap_strategy,
        "verify_payload_hashes": plan.verify_payload_hashes,
    }
    if dry_run:
        return {"status": "dry-run", "actions": actions}

    integrity_result = _verify_payload_integrity(plan)
    python_cmd, bootstrap_result = ensure_python_runtime()
    install_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan.readme_path, readme_target)

    _run_command([*python_cmd, "-m", "venv", str(runtime_dir)])
    venv_python = runtime_dir / "Scripts" / "python.exe"
    _run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    _run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "--force-reinstall", plan.wheel_path])

    if plan.create_shortcut:
        _create_shortcut(_desktop_shortcut_path(), widget_launcher, install_root, icon_path)
    if plan.enable_quick_launch:
        _create_shortcut(_quick_launch_shortcut_path(), widget_launcher, install_root, icon_path)

    manifest = {
        "mode": plan.mode,
        "mode_label": plan.mode_label,
        "recommended": plan.recommended,
        "widget_launcher": plan.widget_launcher,
        "cli_launcher": plan.cli_launcher,
        "options": {
            "create_shortcut": plan.create_shortcut,
            "enable_quick_launch": plan.enable_quick_launch,
            "display_readme": plan.display_readme,
        },
        "wheel_path": plan.wheel_path,
        "readme_path": str(readme_target),
        "security_manifest_path": plan.security_manifest_path,
        "payload_integrity": integrity_result,
        "python_bootstrap": bootstrap_result,
    }
    Path(plan.install_manifest_path).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if plan.display_readme:
        try:
            webbrowser.open(readme_target.resolve().as_uri())
        except Exception:
            pass

    return {"status": "installed", "actions": actions, "manifest_path": plan.install_manifest_path}


def _run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("BlindTag Installer")
    root.resizable(False, False)
    root.configure(padx=14, pady=14)

    mode_var = tk.StringVar(value=INSTALL_MODE_DEFAULT)
    install_dir_var = tk.StringVar(value=str(DEFAULT_INSTALL_DIR))
    option_vars = {
        spec["key"]: tk.BooleanVar(value=bool(spec["default"])) for spec in INSTALLER_OPTION_SPECS
    }
    warning_var = tk.StringVar(value="")

    def _refresh_mode() -> None:
        mode = mode_var.get()
        warning_var.set(INSTALLER_MODES[mode]["warning"])
        state = tk.NORMAL if mode == INSTALL_MODE_ADVANCED else tk.DISABLED
        install_dir_entry.configure(state=state)
        browse_button.configure(state=state)

    tk.Label(root, text="Choose installation type", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
    tk.Label(
        root,
        text="BlindTag will automatically install Python and required runtime pieces if they are missing. Most users should choose Default and click Install.",
        wraplength=460,
        justify="left",
        anchor="w",
    ).grid(row=1, column=0, sticky="w", pady=(4, 10))
    tk.Radiobutton(
        root,
        text=INSTALLER_MODES[INSTALL_MODE_DEFAULT]["label"],
        variable=mode_var,
        value=INSTALL_MODE_DEFAULT,
        command=_refresh_mode,
    ).grid(row=2, column=0, sticky="w")
    tk.Label(root, text=INSTALLER_MODES[INSTALL_MODE_DEFAULT]["description"], anchor="w").grid(row=3, column=0, sticky="w")
    tk.Radiobutton(
        root,
        text=INSTALLER_MODES[INSTALL_MODE_ADVANCED]["label"],
        variable=mode_var,
        value=INSTALL_MODE_ADVANCED,
        command=_refresh_mode,
    ).grid(row=4, column=0, sticky="w", pady=(8, 0))
    tk.Label(root, text=INSTALLER_MODES[INSTALL_MODE_ADVANCED]["description"], anchor="w").grid(row=5, column=0, sticky="w")
    tk.Label(root, textvariable=warning_var, fg="#a85d00", anchor="w").grid(row=6, column=0, sticky="w", pady=(4, 8))

    options_frame = tk.LabelFrame(root, text="Options", padx=10, pady=8)
    options_frame.grid(row=7, column=0, sticky="we")
    for idx, spec in enumerate(INSTALLER_OPTION_SPECS):
        tk.Checkbutton(options_frame, text=spec["label"], variable=option_vars[spec["key"]]).grid(row=idx, column=0, sticky="w")

    install_frame = tk.LabelFrame(root, text="Install location", padx=10, pady=8)
    install_frame.grid(row=8, column=0, sticky="we", pady=(8, 0))
    install_dir_entry = tk.Entry(install_frame, textvariable=install_dir_var, width=52)
    install_dir_entry.grid(row=0, column=0, padx=(0, 6))

    def _browse() -> None:
        path = filedialog.askdirectory(initialdir=install_dir_var.get() or str(DEFAULT_INSTALL_DIR))
        if path:
            install_dir_var.set(path)

    browse_button = tk.Button(install_frame, text="Browse", command=_browse)
    browse_button.grid(row=0, column=1)

    def _install() -> None:
        try:
            plan = build_install_plan(
                mode=mode_var.get(),
                install_dir=install_dir_var.get(),
                create_shortcut=option_vars["create_shortcut"].get(),
                enable_quick_launch=option_vars["enable_quick_launch"].get(),
                display_readme=option_vars["display_readme"].get(),
            )
            result = perform_install(plan)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("BlindTag Installer", str(exc))
            return
        messagebox.showinfo(
            "BlindTag Installer",
            f"Installation complete. Widget launcher: {result['actions']['widget_launcher']}",
        )
        root.destroy()

    button_row = tk.Frame(root)
    button_row.grid(row=9, column=0, sticky="e", pady=(12, 0))
    tk.Button(button_row, text="Install", command=_install, width=12).grid(row=0, column=0, padx=(0, 6))
    tk.Button(button_row, text="Cancel", command=root.destroy, width=12).grid(row=0, column=1)

    _refresh_mode()
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BlindTag Windows installer")
    parser.add_argument("--validate-contract", action="store_true", help="Print the installer contract as JSON.")
    parser.add_argument("--print-plan", action="store_true", help="Print the resolved installer plan as JSON.")
    parser.add_argument("--dry-run-install", action="store_true", help="Resolve and print install actions without making changes.")
    parser.add_argument("--mode", choices=INSTALL_MODE_CHOICES, default=INSTALL_MODE_DEFAULT)
    parser.add_argument("--install-dir")
    parser.add_argument("--no-create-shortcut", action="store_true")
    parser.add_argument("--no-enable-quick-launch", action="store_true")
    parser.add_argument("--no-display-readme", action="store_true")
    parser.add_argument("--install", action="store_true", help="Run the installer non-interactively using the resolved options.")
    args = parser.parse_args(argv)

    if args.validate_contract:
        print(json.dumps(build_contract_summary(), indent=2))
        return 0

    if args.print_plan or args.dry_run_install:
        plan = build_install_plan(
            mode=args.mode,
            install_dir=args.install_dir,
            create_shortcut=not args.no_create_shortcut,
            enable_quick_launch=not args.no_enable_quick_launch,
            display_readme=not args.no_display_readme,
        )
        if args.dry_run_install:
            print(json.dumps(perform_install(plan, dry_run=True), indent=2))
        else:
            print(json.dumps(asdict(plan), indent=2))
        return 0

    if args.install:
        plan = build_install_plan(
            mode=args.mode,
            install_dir=args.install_dir,
            create_shortcut=not args.no_create_shortcut,
            enable_quick_launch=not args.no_enable_quick_launch,
            display_readme=not args.no_display_readme,
        )
        print(json.dumps(perform_install(plan), indent=2))
        return 0

    _run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
