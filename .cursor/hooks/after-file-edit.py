"""Run a cheap, non-mutating formatting check after project edits."""

from __future__ import annotations

import json
import os
import subprocess
import sys


def main() -> int:
    formatted = subprocess.run(
        [sys.executable, "tools/imp.py", "format"],
        cwd=os.getcwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    linted = subprocess.run(
        [sys.executable, "tools/imp.py", "lint"],
        cwd=os.getcwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if formatted.returncode == 0 and linted.returncode == 0:
        print(json.dumps({"additional_context": "IMP format and cheap lint checks passed after edit."}))
        return 0
    print(
        json.dumps(
            {
                "additional_context": (
                    "IMP post-edit checks found diagnostics; inspect `git diff --check` and `imp lint`."
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
