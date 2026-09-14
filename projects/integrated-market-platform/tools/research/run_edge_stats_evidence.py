"""CLI: build edge-stats EvidenceArtifact on admitted BIYA bars."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.research.edge_stats import run_edge_stats_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build edge-stats evidence artifact")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "edge_stats" / "latest.json",
        help="Output path (default: evidence/edge_stats/latest.json)",
    )
    parser.add_argument(
        "--generated-at",
        dest="generated_at",
        default=None,
        help="ISO-8601 UTC stamp (default: now)",
    )
    args = parser.parse_args(argv)
    artifact = run_edge_stats_pipeline(generated_at=args.generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json(args.output, artifact)
    print(json.dumps({"n": artifact["n"], "content_sha256": artifact["content_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
