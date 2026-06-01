from __future__ import annotations

import json
from pathlib import Path

from installer_app.sandbox_validation import generate_sandbox_validation_report, write_sandbox_validation_report


class TestWindowsInstallerSandboxValidation:
    def test_generate_sandbox_validation_report_passes_all_scenarios(self, tmp_path: Path) -> None:
        report = generate_sandbox_validation_report(tmp_path)

        assert report["scenario_count"] == 4
        assert report["passed_scenarios"] == 4
        assert report["all_scenarios_passed"] is True
        assert report["handoff_summary"]["default_mode_ready"] is True
        assert report["handoff_summary"]["bootstrap_ready"] is True
        assert report["handoff_summary"]["fail_closed_confirmed"] is True

    def test_write_sandbox_validation_report_emits_json_and_markdown(self, tmp_path: Path) -> None:
        paths = write_sandbox_validation_report(tmp_path)

        json_report = Path(paths["json"])
        markdown_report = Path(paths["markdown"])

        assert json_report.exists()
        assert markdown_report.exists()

        payload = json.loads(json_report.read_text(encoding="utf-8"))
        markdown = markdown_report.read_text(encoding="utf-8")

        assert payload["all_scenarios_passed"] is True
        assert markdown.startswith("TL;DR:")
        assert "default_existing_python" in markdown
        assert "next-actions:" in markdown
