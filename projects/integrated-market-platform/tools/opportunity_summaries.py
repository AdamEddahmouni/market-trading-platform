"""Read-only ranked opportunity summaries (fixture/sample rows)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Deterministic sample rows for operator dry-runs (not live market data).
SAMPLE_ATTENTION_ROWS: tuple[dict[str, object], ...] = (
    {
        "attention_id": "att-catalyst-aapl",
        "symbol": "AAPL",
        "headline": "AAPL catalyst signal",
        "tier": 2,
        "catalyst_ids": ("earnings",),
    },
    {
        "attention_id": "att-catalyst-nvda",
        "symbol": "NVDA",
        "headline": "NVIDIA reports stronger than expected quarterly earnings outlook",
        "tier": 1,
        "catalyst_ids": ("earnings", "guidance", "analyst"),
    },
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-slug",
        default="FTEP-V1-002",
        help="Campaign slug stamped on summaries (default: FTEP-V1-002)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use built-in fixture attention rows (default when no --input)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file with a list of attention-candidate objects",
    )
    args = parser.parse_args(argv)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.opportunity.read_model import (
        ftep_attention_candidate_to_summary,
        rank_opportunity_summaries,
    )

    rows: list[dict[str, object]]
    if args.input is not None:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit("--input must contain a JSON array of attention rows")
        rows = [item for item in raw if isinstance(item, dict)]
    else:
        rows = [dict(item) for item in SAMPLE_ATTENTION_ROWS]

    summaries = tuple(
        ftep_attention_candidate_to_summary(row, campaign_slug=args.campaign_slug) for row in rows
    )
    ranked = rank_opportunity_summaries(summaries)
    payload = {
        "schema_version": "1.0.0",
        "artifact_kind": "opportunity_summary_list",
        "campaign_slug": args.campaign_slug,
        "source": "sample" if args.sample or args.input is None else str(args.input),
        "count": len(ranked),
        "summaries": [item.to_dict() for item in ranked],
        "secrets_included": False,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in ranked:
            print(
                f"#{item.rank_order} score={item.rank_score:.3f} "
                f"{item.instrument_id} {item.headline[:60]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
