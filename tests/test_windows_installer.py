from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from installer_app.windows_installer import (
    DEFAULT_INSTALL_DIR,
    INSTALLER_MODES,
    INSTALLER_OPTION_SPECS,
    INSTALL_MODE_ADVANCED,
    INSTALL_MODE_DEFAULT,
    SECURITY_MANIFEST_FILENAME,
    _verify_payload_integrity,
    _verify_bootstrap_installer_signature,
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
        assert plan.security_manifest_path.endswith(SECURITY_MANIFEST_FILENAME)
        assert plan.auto_install_python is True
        assert plan.automatic_elevation is True
        assert plan.verify_payload_hashes is True

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
        assert summary["security"]["payload_hash_verification"] is True
        assert summary["security"]["python_bootstrap_signature_validation"] is True
        assert summary["bootstrap"]["auto_python_install"] is True
        assert summary["bootstrap"]["automatic_elevation"] is True

    def test_verify_payload_integrity_accepts_matching_hashes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        wheel = tmp_path / "blindtag.whl"
        wheel.write_bytes(b"wheel")
        readme = tmp_path / "README.md"
        readme.write_text("hello", encoding="utf-8")
        monkeypatch.setattr("installer_app.windows_installer.SHORTCUT_ICON_SOURCE", tmp_path / "missing-icon.png")
        manifest = tmp_path / SECURITY_MANIFEST_FILENAME
        manifest.write_text(
            json.dumps(
                {
                    "manifest_version": 1,
                    "payload_hashes": {
                        "wheel": {"sha256": hashlib.sha256(b"wheel").hexdigest()},
                        "readme": {"sha256": hashlib.sha256(readme.read_bytes()).hexdigest()},
                    },
                }
            ),
            encoding="utf-8",
        )
        plan = build_install_plan(wheel_path=wheel, readme_path=readme)
        plan = type(plan)(**{**plan.__dict__, "security_manifest_path": str(manifest)})

        result = _verify_payload_integrity(plan)

        assert result["verified"] is True
        assert result["verified_items"]["wheel"]["sha256"]

    def test_verify_payload_integrity_rejects_hash_mismatch(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        wheel = tmp_path / "blindtag.whl"
        wheel.write_bytes(b"wheel")
        readme = tmp_path / "README.md"
        readme.write_text("hello", encoding="utf-8")
        monkeypatch.setattr("installer_app.windows_installer.SHORTCUT_ICON_SOURCE", tmp_path / "missing-icon.png")
        manifest = tmp_path / SECURITY_MANIFEST_FILENAME
        manifest.write_text(
            json.dumps(
                {
                    "manifest_version": 1,
                    "payload_hashes": {
                        "wheel": {"sha256": "0" * 64},
                        "readme": {"sha256": hashlib.sha256(readme.read_bytes()).hexdigest()},
                    },
                }
            ),
            encoding="utf-8",
        )
        plan = build_install_plan(wheel_path=wheel, readme_path=readme)
        plan = type(plan)(**{**plan.__dict__, "security_manifest_path": str(manifest)})

        with pytest.raises(RuntimeError, match="Wheel hash verification failed"):
            _verify_payload_integrity(plan)

    def test_verify_bootstrap_installer_signature_accepts_valid_python_org_signature(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        installer = tmp_path / "python-installer.exe"
        installer.write_bytes(b"bootstrap")
        payload = json.dumps(
            {
                "Status": "Valid",
                "Subject": "CN=Python Software Foundation, O=Python Software Foundation, L=Beaverton, S=Oregon, C=US",
                "Issuer": "CN=Trusted CA",
            }
        )
        monkeypatch.setattr(
            "installer_app.windows_installer._run_command_result",
            lambda command: subprocess.CompletedProcess(command, 0, stdout=payload, stderr=""),
        )

        result = _verify_bootstrap_installer_signature(installer)

        assert result["status"] == "Valid"
        assert "Python Software Foundation" in result["subject"]

    def test_verify_bootstrap_installer_signature_rejects_untrusted_signer(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        installer = tmp_path / "python-installer.exe"
        installer.write_bytes(b"bootstrap")
        payload = json.dumps(
            {
                "Status": "Valid",
                "Subject": "CN=Unexpected Signer",
                "Issuer": "CN=Trusted CA",
            }
        )
        monkeypatch.setattr(
            "installer_app.windows_installer._run_command_result",
            lambda command: subprocess.CompletedProcess(command, 0, stdout=payload, stderr=""),
        )

        with pytest.raises(RuntimeError, match="signer is not trusted"):
            _verify_bootstrap_installer_signature(installer)

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
