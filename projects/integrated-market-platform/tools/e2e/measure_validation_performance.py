"""G15 BL-0801 — validation performance measurement artifact."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts" / "g15-validation-performance.json"


def _run_imp(mode: str) -> dict[str, object]:
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    executable = python if python.is_file() else Path(sys.executable)
    started = time.perf_counter()
    completed = subprocess.run(
        [str(executable), str(ROOT / "tools" / "imp.py"), "validate", mode, "--json", str(ROOT / f".local/g15-{mode}.json")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    wall_seconds = time.perf_counter() - started
    summary_path = ROOT / f".local/g15-{mode}.json"
    summary: dict[str, object] = {}
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "mode": mode,
        "exit_code": completed.returncode,
        "wall_seconds": round(wall_seconds, 3),
        "summary": summary,
    }


def main() -> int:
    modes = ("fast", "changed", "e2e")
    timings = {mode: _run_imp(mode) for mode in modes}
    payload = {
        "schema_version": "1.0",
        "report_type": "g15_validation_performance",
        "classification": "G15_VALIDATION_PERFORMANCE_MEASURED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": timings,
        "optimization_attempted": [
            "E2E isolated to e2e tier (excluded from FAST and FULL)",
            "product_acceptance suite SERIAL_REQUIRED to avoid port collisions",
        ],
        "notes": "FULL duration recorded separately at closure; run imp.py validate full for authoritative count.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
