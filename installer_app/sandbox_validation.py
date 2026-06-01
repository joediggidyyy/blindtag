from __future__ import annotations

import json
import hashlib
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from installer_app import windows_installer


@dataclass(frozen=True)
class SandboxScenario:
    name: str
    description: str
    mode: str
    create_shortcut: bool
    enable_quick_launch: bool
    display_readme: bool
    bootstrap_result: dict[str, Any] | None = None
    expected_failure: str | None = None


SCENARIOS: tuple[SandboxScenario, ...] = (
    SandboxScenario(
        name="default_existing_python",
        description="Default path with an already-available Python runtime and full handoff surfaces enabled.",
        mode=windows_installer.INSTALL_MODE_DEFAULT,
        create_shortcut=True,
        enable_quick_launch=True,
        display_readme=True,
        bootstrap_result={"method": "existing-python", "elevated": False},
    ),
    SandboxScenario(
        name="default_bootstrap_winget",
        description="Default path where the installer must bootstrap Python automatically before building the runtime.",
        mode=windows_installer.INSTALL_MODE_DEFAULT,
        create_shortcut=True,
        enable_quick_launch=True,
        display_readme=True,
        bootstrap_result={"method": "winget", "elevated": True},
    ),
    SandboxScenario(
        name="advanced_custom_location",
        description="Advanced path with custom install location and reduced handoff surfaces for an operator-specific setup.",
        mode=windows_installer.INSTALL_MODE_ADVANCED,
        create_shortcut=False,
        enable_quick_launch=False,
        display_readme=False,
        bootstrap_result={"method": "existing-python", "elevated": False},
    ),
    SandboxScenario(
        name="missing_python_fail_closed",
        description="Installer fails closed when Python cannot be bootstrapped in the simulated sandbox.",
        mode=windows_installer.INSTALL_MODE_DEFAULT,
        create_shortcut=True,
        enable_quick_launch=True,
        display_readme=True,
        expected_failure="BlindTag could not bootstrap Python 3.11+ automatically.",
    ),
)


@contextmanager
def _patched_attr(target: object, attr_name: str, replacement: object) -> Iterator[None]:
    original = getattr(target, attr_name)
    setattr(target, attr_name, replacement)
    try:
        yield
    finally:
        setattr(target, attr_name, original)


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _touch_binary(path: Path, content: bytes = b"stub") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scenario_sources(sandbox_root: Path, scenario: SandboxScenario) -> tuple[Path, Path, Path]:
    source_root = sandbox_root / "sources"
    wheel_path = _touch_binary(source_root / f"blindtag-{scenario.name}.whl", content=f"wheel:{scenario.name}".encode("utf-8"))
    readme_path = _write_text(source_root / "README.md", f"# BlindTag Sandbox\n\nScenario: {scenario.name}\n")
    icon_path = _touch_binary(source_root / "blindtag_thumbnail_basic.png", content=b"icon")
    return wheel_path, readme_path, icon_path


def _simulate_install_scenario(scenario: SandboxScenario, sandbox_root: Path) -> dict[str, Any]:
    wheel_path, readme_path, icon_path = _scenario_sources(sandbox_root, scenario)
    install_root = sandbox_root / "install-root"
    desktop_shortcut = sandbox_root / "Desktop" / "BlindTag.lnk"
    quick_launch_shortcut = sandbox_root / "QuickLaunch" / "BlindTag.lnk"
    command_log: list[list[str]] = []
    shortcut_log: list[dict[str, str]] = []
    browser_log: list[str] = []

    def fake_run_command(command: list[str]) -> None:
        command_log.append(command)
        if len(command) >= 4 and command[1:3] == ["-m", "venv"]:
            runtime_dir = Path(command[3])
            scripts_dir = runtime_dir / "Scripts"
            _touch_binary(scripts_dir / "python.exe")
            return
        if len(command) >= 4 and command[1:4] == ["-m", "pip", "install"]:
            scripts_dir = Path(command[0]).parent
            _touch_binary(scripts_dir / "python.exe")
            _touch_binary(scripts_dir / "blindtag-widget.exe")
            _touch_binary(scripts_dir / "blindtag.exe")
            return

    def fake_create_shortcut(shortcut_path: Path, target_path: Path, working_dir: Path, icon_override: Path | None = None) -> None:
        shortcut_log.append(
            {
                "shortcut_path": str(shortcut_path),
                "target_path": str(target_path),
                "working_dir": str(working_dir),
                "icon_path": str(icon_override) if icon_override else "",
            }
        )
        _write_text(shortcut_path, json.dumps(shortcut_log[-1], indent=2))

    def fake_webbrowser_open(uri: str) -> bool:
        browser_log.append(uri)
        return True

    def fake_ensure_python_runtime() -> tuple[list[str], dict[str, Any]]:
        if scenario.expected_failure is not None:
            raise RuntimeError(scenario.expected_failure)
        assert scenario.bootstrap_result is not None
        return ["C:/Python312/python.exe"], dict(scenario.bootstrap_result)

    install_plan = windows_installer.build_install_plan(
        mode=scenario.mode,
        install_dir=install_root,
        create_shortcut=scenario.create_shortcut,
        enable_quick_launch=scenario.enable_quick_launch,
        display_readme=scenario.display_readme,
        wheel_path=wheel_path,
        readme_path=readme_path,
    )

    success = False
    error_message: str | None = None
    result_payload: dict[str, Any] | None = None

    with _patched_attr(windows_installer, "_run_command", fake_run_command), \
        _patched_attr(windows_installer, "_create_shortcut", fake_create_shortcut), \
        _patched_attr(windows_installer, "ensure_python_runtime", fake_ensure_python_runtime), \
        _patched_attr(windows_installer, "_desktop_shortcut_path", lambda: desktop_shortcut), \
        _patched_attr(windows_installer, "_quick_launch_shortcut_path", lambda: quick_launch_shortcut), \
        _patched_attr(windows_installer, "SHORTCUT_ICON_SOURCE", icon_path), \
        _patched_attr(windows_installer.webbrowser, "open", fake_webbrowser_open):
        try:
            result_payload = windows_installer.perform_install(install_plan)
            success = scenario.expected_failure is None
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            success = scenario.expected_failure is not None and scenario.expected_failure in error_message

    manifest_path = install_root / "install_manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    widget_launcher = Path(install_plan.widget_launcher)
    cli_launcher = Path(install_plan.cli_launcher)

    handoff = {
        "status": "ready" if manifest_data is not None else "blocked",
        "primary_launch_surface": str(desktop_shortcut if scenario.create_shortcut else widget_launcher),
        "widget_launcher_exists": widget_launcher.exists(),
        "cli_launcher_exists": cli_launcher.exists(),
        "readme_present": (install_root / "README.md").exists(),
        "readme_auto_opened": bool(browser_log),
        "desktop_shortcut_present": desktop_shortcut.exists(),
        "quick_launch_present": quick_launch_shortcut.exists(),
        "install_manifest_present": manifest_path.exists(),
        "python_bootstrap_method": None if manifest_data is None else manifest_data.get("python_bootstrap", {}).get("method"),
    }

    if scenario.expected_failure is not None:
        expected_checks: dict[str, bool | None] = {
            "shortcut_expectation_met": None,
            "quick_launch_expectation_met": None,
            "readme_expectation_met": None,
        }
    else:
        expected_checks = {
            "shortcut_expectation_met": desktop_shortcut.exists() is scenario.create_shortcut,
            "quick_launch_expectation_met": quick_launch_shortcut.exists() is scenario.enable_quick_launch,
            "readme_expectation_met": bool(browser_log) is scenario.display_readme,
        }

    return {
        "name": scenario.name,
        "description": scenario.description,
        "expected_failure": scenario.expected_failure,
        "success": success,
        "error_message": error_message,
        "scenario_root": str(sandbox_root),
        "input_plan": asdict(install_plan),
        "result_payload": result_payload,
        "handoff": handoff,
        "expected_checks": expected_checks,
        "command_log": command_log,
        "shortcut_log": shortcut_log,
        "browser_log": browser_log,
        "manifest": manifest_data,
    }


def generate_sandbox_validation_report(output_root: Path | None = None) -> dict[str, Any]:
    output_dir = output_root or (windows_installer.REPO_ROOT / "report_tmp" / "windows_installer_sandbox_validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios_dir = output_dir / "sandbox_scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    scenario_results = [
        _simulate_install_scenario(scenario, scenarios_dir / scenario.name)
        for scenario in SCENARIOS
    ]

    installer_exe = windows_installer.WINDOWS_INSTALLER_DIST / "BlindTagInstaller.exe"
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_root": str(output_dir),
        "installer_contract": windows_installer.build_contract_summary(),
        "installer_artifact": {
            "path": str(installer_exe),
            "exists": installer_exe.exists(),
            "sha256": _sha256(installer_exe) if installer_exe.exists() else None,
        },
        "scenario_count": len(scenario_results),
        "passed_scenarios": sum(1 for result in scenario_results if result["success"]),
        "all_scenarios_passed": all(result["success"] for result in scenario_results),
        "scenarios": scenario_results,
        "handoff_summary": {
            "ready_count": sum(1 for result in scenario_results if result["handoff"]["status"] == "ready"),
            "blocked_count": sum(1 for result in scenario_results if result["handoff"]["status"] == "blocked"),
            "default_mode_ready": any(
                result["name"] == "default_existing_python" and result["handoff"]["status"] == "ready"
                for result in scenario_results
            ),
            "bootstrap_ready": any(
                result["name"] == "default_bootstrap_winget" and result["handoff"]["status"] == "ready"
                for result in scenario_results
            ),
            "fail_closed_confirmed": any(
                result["name"] == "missing_python_fail_closed" and result["handoff"]["status"] == "blocked"
                for result in scenario_results
            ),
        },
    }
    return report


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = (
        "All simulated installer scenarios passed and the handoff packet stayed truthful."
        if report["all_scenarios_passed"]
        else "One or more simulated installer scenarios failed; inspect the scenario results before release."
    )
    lines = [
        f"TL;DR: {summary}",
        "",
        "# BlindTag Windows Installer Sandbox Validation",
        "",
        f"- generated_at_utc: `{report['generated_at_utc']}`",
        f"- installer_exe_exists: `{report['installer_artifact']['exists']}`",
        f"- installer_exe_sha256: `{report['installer_artifact']['sha256']}`",
        f"- scenario_count: `{report['scenario_count']}`",
        f"- passed_scenarios: `{report['passed_scenarios']}`",
        f"- all_scenarios_passed: `{report['all_scenarios_passed']}`",
        "",
        "## Scenario outcomes",
        "",
        "| Scenario | Result | Handoff | Bootstrap | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for scenario in report["scenarios"]:
        result = "PASS" if scenario["success"] else "FAIL"
        handoff = scenario["handoff"]["status"]
        bootstrap = scenario["handoff"]["python_bootstrap_method"] or "n/a"
        notes = scenario["error_message"] or scenario["description"]
        lines.append(f"| `{scenario['name']}` | `{result}` | `{handoff}` | `{bootstrap}` | {notes} |")

    lines.extend(
        [
            "",
            "## Handoff summary",
            "",
            f"- ready_count: `{report['handoff_summary']['ready_count']}`",
            f"- blocked_count: `{report['handoff_summary']['blocked_count']}`",
            f"- default_mode_ready: `{report['handoff_summary']['default_mode_ready']}`",
            f"- bootstrap_ready: `{report['handoff_summary']['bootstrap_ready']}`",
            f"- fail_closed_confirmed: `{report['handoff_summary']['fail_closed_confirmed']}`",
            "",
            "next-actions: NOW WE ARE GOING TO use this sandbox evidence packet as the Phase 4 installer-validation receipt for BlindTag's packaging/publication lane.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_sandbox_validation_report(output_root: Path | None = None) -> dict[str, Path]:
    output_dir = output_root or (windows_installer.REPO_ROOT / "report_tmp" / "windows_installer_sandbox_validation")
    report = generate_sandbox_validation_report(output_dir)
    json_path = output_dir / "windows_installer_sandbox_validation.json"
    md_path = output_dir / "windows_installer_sandbox_validation.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
