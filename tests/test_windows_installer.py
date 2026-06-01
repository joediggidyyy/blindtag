from __future__ import annotations

import os
from pathlib import Path

import pytest

from installer_app.windows_installer import (
    DEFAULT_INSTALL_DIR,
    INSTALLER_MODES,
    INSTALLER_OPTION_SPECS,
    INSTALL_MODE_ADVANCED,
    INSTALL_MODE_DEFAULT,
    ensure_python_runtime,
    build_contract_summary,
    build_install_plan,
    find_latest_wheel,
    validate_install_plan,
)


class TestWindowsInstallerContract:
    def test_default_mode_is_recommended(self) -> None:
        assert INSTALLER_MODES[INSTALL_MODE_DEFAULT]["recommended"] is True
        assert "Recommended" in INSTALLER_MODES[INSTALL_MODE_DEFAULT]["label"]

    def test_advanced_mode_carries_warning_language(self) -> None:
        warning = INSTALLER_MODES[INSTALL_MODE_ADVANCED]["warning"]
        assert warning
        assert "custom" in warning.lower() or "advanced" in warning.lower()

    def test_required_option_labels_are_present(self) -> None:
        labels = {spec["label"] for spec in INSTALLER_OPTION_SPECS}
        assert "Create shortcut" in labels
        assert "Enable quick launch" in labels
        assert "Display README.md after install" in labels

    def test_build_install_plan_exposes_widget_launcher(self) -> None:
        plan = build_install_plan()
        assert plan.mode == INSTALL_MODE_DEFAULT
        assert plan.recommended is True
        assert plan.install_dir == str(DEFAULT_INSTALL_DIR)
        assert plan.widget_launcher.endswith("blindtag-widget.exe")
        assert plan.auto_install_python is True
        assert plan.automatic_elevation is True

    def test_validate_install_plan_flags_missing_wheel(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text("hello", encoding="utf-8")
        plan = build_install_plan(wheel_path=tmp_path / "missing.whl", readme_path=readme)
        errors = validate_install_plan(plan)
        assert any("wheel not found" in error for error in errors)

    def test_find_latest_wheel_prefers_newest_candidate(self, tmp_path: Path) -> None:
        older = tmp_path / "blindtag-0.9.0-py3-none-any.whl"
        newer = tmp_path / "blindtag-1.0.0-py3-none-any.whl"
        older.write_text("older", encoding="utf-8")
        newer.write_text("newer", encoding="utf-8")
        os.utime(older, (1, 1))
        os.utime(newer, (2, 2))
        found = find_latest_wheel([tmp_path])
        assert found == newer

    def test_contract_summary_reports_modes_and_options(self) -> None:
        summary = build_contract_summary()
        assert INSTALL_MODE_DEFAULT in summary["modes"]
        assert INSTALL_MODE_ADVANCED in summary["modes"]
        assert len(summary["options"]) == 3
        assert summary["bootstrap"]["auto_python_install"] is True
        assert summary["bootstrap"]["automatic_elevation"] is True

    def test_ensure_python_runtime_bootstraps_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        discoveries = iter([None, ["C:/Python312/python.exe"]])
        monkeypatch.setattr("installer_app.windows_installer._try_discover_python_command", lambda: next(discoveries))
        monkeypatch.setattr("installer_app.windows_installer._is_windows", lambda: True)
        monkeypatch.setattr(
            "installer_app.windows_installer._install_python_with_winget",
            lambda: True,
        )
        monkeypatch.setattr(
            "installer_app.windows_installer._install_python_from_bootstrap_installer",
            lambda: False,
        )

        command, status = ensure_python_runtime()

        assert command == ["C:/Python312/python.exe"]
        assert status["method"] == "winget"

    def test_ensure_python_runtime_raises_without_windows_bootstrap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("installer_app.windows_installer._try_discover_python_command", lambda: None)
        monkeypatch.setattr("installer_app.windows_installer._is_windows", lambda: False)

        with pytest.raises(RuntimeError, match="only supported on Windows"):
            ensure_python_runtime()
