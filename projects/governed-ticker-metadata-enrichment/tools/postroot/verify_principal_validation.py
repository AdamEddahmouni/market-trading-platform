"""Run all principal-validation hash checks in one pass."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = (
    ROOT / "tools/postroot/verify_postreview_hashes.py",
    ROOT / "tools/postroot/verify_governed_subject_hashes.py",
)


def main() -> int:
    failed = False
    for script in SCRIPTS:
        print(f"\n>>> {script.name}")
        result = subprocess.run([sys.executable, str(script)], cwd=ROOT, check=False)
        if result.returncode != 0:
            failed = True
    if failed:
        print("\n=== Principal validation: FAILURES DETECTED ===")
        return 1
    print("\n=== Principal validation: ALL AUTOMATED CHECKS PASS ===")
    print("Principal must still confirm approval records reflect actual intent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
