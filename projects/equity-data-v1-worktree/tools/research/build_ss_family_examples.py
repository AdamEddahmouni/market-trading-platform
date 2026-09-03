"""Write the committed deterministic SS-family decision-example fixture.

Usage:
    python tools/research/build_ss_family_examples.py [--output path]

Reproducible: the builder reads only pinned admitted fixture slices and uses
no RNG, so identical inputs always produce identical output (bytes + root
hash). Byte-for-byte parity is asserted by
tests/research/test_decision_research_examples.py. Fails closed on any PIT or
Finviz-scope violation raised by the builder.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.research.decision_research.examples import (
    build_ss_family_examples,
    examples_root_hash,
)

DEFAULT_OUTPUT = ROOT / "tests" / "fixtures" / "research" / "ss_family_examples.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    examples = build_ss_family_examples()
    write_canonical_json(Path(args.output), examples)
    from collections import Counter

    by = Counter(
        tuple(sorted(f["evidence_family"] for f in e["features"])) for e in examples
    )
    print(f"wrote {args.output} ({len(examples)} examples, root={examples_root_hash(examples)})")
    for families, count in sorted(by.items()):
        print(f"  {families}: {count}")
    diagnostics = Counter()
    for e in examples:
        for f in e["features"]:
            diagnostics[f["evidence_family"]] += 1
    print("  per-family feature occurrences:", dict(diagnostics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
