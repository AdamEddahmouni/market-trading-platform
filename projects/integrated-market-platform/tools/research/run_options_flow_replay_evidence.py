"""CLI: build options-flow replay EvidenceArtifact on admitted NVDA slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from market_platform_foundation.research.options_flow_replay.pipeline import (  # noqa: E402
    run_options_flow_replay_pipeline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write artifact JSON to path (default: stdout)",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="ISO timestamp for artifact.generated_at",
    )
    args = parser.parse_args()
    artifact = run_options_flow_replay_pipeline(generated_at=args.generated_at)
    payload = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
