"""Build the Screener's local 13F holdings index from SEC Form 13F data-set ZIPs.

Download the two newest data sets (one per filing window, ~100 MB each) from
https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets with a
User-Agent that names you and a contact email (SEC Fair Access), then:

    python tools/sec_edgar/thirteen_f_index.py --zip A_form13f.zip --zip B_form13f.zip --out <path>.sqlite

and start the UI API with ``IMP_13F_INDEX_PATH=<path>.sqlite``. Keep the ZIPs and the
index outside the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.sec_edgar.thirteen_f_index import build_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the local 13F holdings index")
    parser.add_argument("--zip", action="append", required=True, type=Path, help="Form 13F data-set ZIP (repeatable)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if any(ROOT in path.resolve().parents for path in (*args.zip, args.out)):
        parser.error("keep the data sets and the index outside the repository")
    print(json.dumps(build_index(args.zip, args.out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
