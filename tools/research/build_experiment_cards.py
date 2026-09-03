"""Write the committed fixed-hash SS-family experiment-card fixture.

Usage:
    python tools/research/build_experiment_cards.py [--output path]

Reproducible: identical card bodies always produce identical fixtures and
hashes (cards.py canonical bytes + uuid5). Byte-for-byte parity is asserted by
tests/research/test_decision_research_fixtures.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.research.decision_research.ss_cards import build_ss_family_cards

DEFAULT_OUTPUT = ROOT / "tests" / "fixtures" / "research" / "experiment_cards.json"


def cards_payload() -> list[dict]:
    cards = build_ss_family_cards()
    return [cards[eid].to_dict() for eid in sorted(cards)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    destination = Path(args.output)
    write_canonical_json(destination, cards_payload())
    print(f"wrote {destination} ({len(cards_payload())} cards)")
    for eid in sorted(c["experiment_id"] for c in cards_payload()):
        card = build_ss_family_cards()[eid]
        print(f"  {eid:10s} hash={card.card_hash} id={card.card_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
