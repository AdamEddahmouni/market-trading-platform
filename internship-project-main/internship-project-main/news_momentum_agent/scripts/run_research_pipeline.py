#!/usr/bin/env python3
"""End-to-end research pipeline: panel → N>=30 miner → OOS → proposals (no live edits).

CLI
---
``python scripts/run_research_pipeline.py [--replay PATH] [--min-n N]
[--discovery-frac F] [--skip-enrichment]``

Builds SPY/QQQ research panel, runs pattern miner + OOS split, writes proposals.

When to run
-----------
Offline research sessions after replay records exist; not on the trading critical path.

Safe vs live agent
------------------
**Safe / offline:** Never edits ``settings.json`` or live agent state automatically.
Outputs under ``state/learning/`` and proposal files only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.pattern_miner import DEFAULT_MIN_N, run_pattern_pipeline  # noqa: E402
from evaluation.proposals import build_proposals, write_proposals  # noqa: E402
from evaluation.enrich_research_panel import enrich_and_save_panel  # noqa: E402
from evaluation.research_panel import (  # noqa: E402
    PANEL_PATH,
    build_spy_qqq_research_panel,
    save_research_panel,
)
from evaluation.spy_qqq_replay import PATH_A_EXCLUSION_NOTE  # noqa: E402


def main() -> int:
    """CLI entry: build research panel, run miner/OOS, write proposals (no live edits)."""
    parser = argparse.ArgumentParser(description="SPY/QQQ research pattern pipeline")
    parser.add_argument(
        "--replay",
        default=str(PROJECT_ROOT / "state" / "learning" / "spy_qqq_replay_records.json"),
    )
    parser.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    parser.add_argument("--discovery-frac", type=float, default=0.70)
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Skip macro calendar + VIX join (use raw panel features only)",
    )
    args = parser.parse_args()

    print(PATH_A_EXCLUSION_NOTE)
    replay_path = Path(args.replay)
    panel = build_spy_qqq_research_panel(replay_path=replay_path if replay_path.exists() else None)
    save_research_panel(panel, PANEL_PATH)
    print(f"[research] panel n={panel['n_rows']} by_source={panel['by_source']} → {PANEL_PATH}")

    rows = panel.get("rows") or []
    if not args.skip_enrichment:
        enriched = enrich_and_save_panel(panel, fetch_vix=True)
        rows = enriched.get("rows") or rows
        print(f"[research] enrichment={enriched.get('enrichment')}")

    miner = run_pattern_pipeline(
        rows,
        min_n=max(1, int(args.min_n)),
        discovery_frac=float(args.discovery_frac),
    )
    miner_path = PROJECT_ROOT / "state" / "learning" / "spy_qqq_miner_result.json"
    miner_path.write_text(json.dumps(miner, indent=2, default=str), encoding="utf-8")
    print(
        f"[research] discovery_patterns={len(miner.get('discovery_patterns_passing_n') or [])} "
        f"survivors={len(miner.get('survivors') or [])} "
        f"failed_oos={len(miner.get('found_but_did_not_replicate') or [])}"
    )
    # Highlight catalyst/VIX patterns in discovery for quick scan.
    cat_pats = [
        p
        for p in (miner.get("discovery_patterns_passing_n") or [])
        if str(p.get("feature") or "").startswith(("is_scheduled", "hours_", "vix_"))
    ]
    if cat_pats:
        print(f"[research] catalyst/vix discovery candidates={len(cat_pats)}")
        for p in cat_pats[:8]:
            print(
                f"  - {p.get('feature')}={p.get('value')} n={p.get('n')} "
                f"wr={p.get('win_rate')} lift={p.get('lift')} "
                f"avg_R={p.get('avg_r_multiple')} E={p.get('expectancy_pnl_pct')}"
            )

    proposals = build_proposals(miner)
    paths = write_proposals(proposals)
    print(f"[research] proposals → {paths['md']}")
    print("(auto_apply=false — adopt/reject via scripts/update_proposal_status.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
