"""One-off smoke test: run backtest_main2_csv against synthetic bundled-style CSV."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytz

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "src_client" / "workspace" / "historical data" / "backtest_main2_csv.py"
SMOKE_DIR = ROOT / ".smoke_data"


def build_synthetic_csv(path: Path) -> None:
    rows = []
    base = datetime(2025, 6, 2, 9, 45, tzinfo=pytz.timezone("America/New_York"))
    for i in range(30):
        ts = int((base + timedelta(minutes=i)).timestamp())
        bids = ";".join(f"{6000 + j * 0.25}:{50 + j * 10}" for j in range(10))
        asks = ";".join(f"{6002 + j * 0.25}:{10 + j}" for j in range(10))
        rows.append({"timestamp": ts, "bids": bids, "asks": asks})
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> int:
    csv_path = SMOKE_DIR / "es_level2_data.csv"
    build_synthetic_csv(csv_path)
    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    result = subprocess.run(
        [sys.executable, str(BACKTEST)],
        cwd=SMOKE_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout[-2000:])
    if result.stderr:
        print(result.stderr[-1000:], file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
