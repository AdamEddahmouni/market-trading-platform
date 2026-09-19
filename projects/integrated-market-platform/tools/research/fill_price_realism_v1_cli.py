"""Lane F: bounded fill-price realism v1 execution (read-only v3 schedules)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (  # noqa: E402
    verify_frozen_experiment_definition,
)
from market_platform_foundation.intelligence.historical_research_harness.fill_price_realism_harness import (  # noqa: E402
    CANONICAL_FILL_PRICE_REALISM_EVIDENCE_REL,
    run_frozen_fill_price_realism_v1,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v3 import (  # noqa: E402
    load_pinned_opend_build_v3,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frozen-definition",
        type=Path,
        default=ROOT / CANONICAL_FILL_PRICE_REALISM_EVIDENCE_REL / "frozen_experiment_definition.json",
    )
    parser.add_argument("--verify-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    frozen_path = args.frozen_definition
    if not frozen_path.is_file():
        print(json.dumps({"ok": False, "reason_code": "FROZEN_DEFINITION_MISSING", "path": str(frozen_path)}))
        return 2
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    verify = verify_frozen_experiment_definition(frozen)
    if not verify.get("ok"):
        print(json.dumps({"ok": False, "verify": verify}))
        return 2
    if args.verify_only:
        print(json.dumps({"ok": True, "verify": verify}))
        return 0
    build = load_pinned_opend_build_v3(ROOT)
    result = run_frozen_fill_price_realism_v1(
        repository_root=ROOT,
        frozen_definition=frozen,
        build=build,
    )
    payload = {
        "ok": result.ok,
        "pack_run_id": result.pack_run_id,
        "experiment_definition_hash": result.experiment_definition_hash,
        "reason_code": result.reason_code,
        "artifact_dir": str(result.artifact_dir),
    }
    print(json.dumps(payload, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
