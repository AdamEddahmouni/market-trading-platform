"""Build, score and (optionally) activate the live Paper Path A forecast from the recorded feature corpus.

    python tools/paper_forecast_build.py --corpus-dir <dir> --models-dir <dir> [--symbols AAPL,NVDA] [--activate]

Per instrument: time-ordered train / calibration / holdout with a horizon embargo, the governed
``build_path_a_production_artifacts`` build, then one scoring of the untouched holdout against the
preregistered eligibility rule in ``live_training``. ``--activate`` writes the strategy preregistration
(once; it is never re-stamped) and then ``ACTIVE.json`` naming only the instruments that passed. The serving
hook reads ``ACTIVE.json`` at startup. Nothing here calls a model service, the canonical store or a broker.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.production.live_training import build_from_corpus  # noqa: E402
from market_platform_foundation.strategy.path_a_live_forecast import (  # noqa: E402
    live_strategy_definition,
    preregistration_valid,
)
from market_platform_foundation.strategy.preregistration import build_preregistration  # noqa: E402
from market_platform_foundation.ui_api.paper_live_forecast import (  # noqa: E402
    ACTIVE_FILE,
    ACTIVE_SCHEMA,
    PREREGISTRATION_FILE,
)


def _write(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus-dir", required=True, type=Path)
    parser.add_argument("--models-dir", required=True, type=Path)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args(argv)
    paths = sorted(args.corpus_dir.glob("feature-corpus-*.jsonl"))
    if not paths:
        print(json.dumps(dict(status="BLOCKED", reason="NO_CORPUS_FILES")))
        return 2
    args.models_dir.mkdir(parents=True, exist_ok=True)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None
    now_ns = time.time_ns()
    summary = build_from_corpus(paths, output_root=args.models_dir, decision_time_ns=now_ns, instruments=symbols)
    result = dict(build=summary, activated=False)
    if args.activate:
        prereg_path = args.models_dir / PREREGISTRATION_FILE
        if prereg_path.exists():
            preregistration = json.loads(prereg_path.read_text(encoding="utf-8"))
            if not preregistration_valid(preregistration):
                print(json.dumps(dict(result, status="BLOCKED", reason="EXISTING_PREREGISTRATION_INVALID")))
                return 3
        else:
            preregistration = build_preregistration(live_strategy_definition(),
                                                    registered_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
            _write(prereg_path, preregistration)
        active = dict(schema_version=ACTIVE_SCHEMA, build_id=summary["build_id"], instruments=summary["eligible"],
                      activated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                      eligibility_rule=summary["eligibility_rule"],
                      strategy_identity_hash=preregistration["strategy_identity_hash"])
        _write(args.models_dir / ACTIVE_FILE, active)
        result.update(activated=True, active=active, preregistration=preregistration)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
