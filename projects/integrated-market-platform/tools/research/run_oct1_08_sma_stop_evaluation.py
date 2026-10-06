"""OCT1-08: freeze, then run, the SMA trailing-stop replay comparison.

--freeze writes the pre-execution definition and refuses to change one that
already exists. --run requires that committed definition, evaluates the pinned
corpus twice, and writes the receipt only if both runs hash identically.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.research.sma_stop_evaluation import (  # noqa: E402
    DEFINITION_REL,
    RECEIPT_REL,
    definition_hash,
    frozen_definition,
    run_frozen_evaluation,
)


def _dump(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true", help="Write the pre-execution frozen definition.")
    group.add_argument("--run", action="store_true", help="Run the frozen comparison and write the receipt.")
    args = parser.parse_args()
    definition_path = ROOT / DEFINITION_REL
    if args.freeze:
        definition = json.loads(json.dumps(frozen_definition()))
        if definition_path.is_file() and json.loads(definition_path.read_text(encoding="utf-8")) != definition:
            print("FROZEN_DEFINITION_ALREADY_EXISTS_AND_DIFFERS", file=sys.stderr)
            return 2
        definition_path.parent.mkdir(parents=True, exist_ok=True)
        definition_path.write_text(_dump(definition), encoding="utf-8", newline="\n")
        print(json.dumps({"definition": DEFINITION_REL.as_posix(), "definition_hash": definition_hash()}))
        return 0
    started = time.perf_counter()
    first = run_frozen_evaluation(ROOT)
    elapsed = time.perf_counter() - started
    second = run_frozen_evaluation(ROOT)
    if first["result_hash"] != second["result_hash"] or not (first["corpus_unchanged"] and second["corpus_unchanged"]):
        print("EVALUATION_NOT_REPRODUCIBLE", file=sys.stderr)
        return 3
    receipt_path = ROOT / RECEIPT_REL
    receipt_path.write_text(_dump(first), encoding="utf-8", newline="\n")
    episodes = first["counts"]["episodes"]
    print(json.dumps({
        "receipt": RECEIPT_REL.as_posix(), "result_hash": first["result_hash"], "definition_hash": first["definition_hash"],
        "episodes": episodes, "evaluable": first["counts"]["evaluable"], "conclusion": first["conclusion"]["conclusion"],
        "reproduced": True, "seconds": round(elapsed, 3), "episodes_per_second": round(episodes / elapsed, 1) if elapsed else None,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
