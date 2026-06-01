from __future__ import annotations

import json
from pathlib import Path

from installer_app.sandbox_validation import write_sandbox_validation_report


def main() -> int:
    paths = write_sandbox_validation_report()
    payload = {
        "json_report": str(Path(paths["json"]).resolve()),
        "markdown_report": str(Path(paths["markdown"]).resolve()),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
