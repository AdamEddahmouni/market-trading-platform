"""Generate the refreshed P2 parallel-safety map from the canonical manifest."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools.validation_manifest import load_manifest
    from tools.validate import scheduling_policy
except ModuleNotFoundError:  # pragma: no cover
    from validation_manifest import load_manifest  # type: ignore[no-redef]

    def scheduling_policy(suite):  # type: ignore[no-redef]
        safety = suite.parallel_safety
        if safety == "LIVE_EXCLUSIVE":
            return "LIVE_EXCLUSIVE"
        if safety == "SERIAL_REQUIRED":
            return "SERIAL_REQUIRED"
        if safety == "RESOURCE_HEAVY":
            return "RESOURCE_HEAVY"
        if safety == "PARALLEL_SAFE":
            return "PARALLEL_SAFE"
        if safety == "GLOBAL_STATE_MUTATION":
            return "SERIAL_REQUIRED"
        return "UNKNOWN_FAIL_SAFE"


P0_REFERENCE = {
    "PARALLEL_SAFE": 45,
    "GLOBAL_STATE_MUTATION": 11,
    "RESOURCE_HEAVY": 5,
    "SERIAL_REQUIRED": 5,
    "LIVE_EXCLUSIVE": 12,
}


def build_map(repository_root: Path) -> dict[str, object]:
    manifest_path = repository_root / "tools" / "validation_manifest.json"
    manifest = load_manifest(manifest_path, repository_root=repository_root)
    suites: list[dict[str, object]] = []
    counts = Counter()
    for suite in manifest.suites:
        if suite.classification == "intentionally_absent":
            continue
        policy = scheduling_policy(suite) if hasattr(suite, "parallel_safety") else suite.parallel_safety
        counts[suite.parallel_safety] += 1
        suites.append(
            {
                "id": suite.id,
                "parallel_safety": suite.parallel_safety,
                "scheduling_policy": policy,
                "resource_class": suite.resource_class,
                "resource_weight": suite.resource_weight,
                "exclusive_group": suite.exclusive_group,
                "max_concurrency": suite.max_concurrency,
                "concurrency_reason": suite.concurrency_reason,
                "external_shared_state": _external_state_note(suite),
                "final_policy": policy,
            }
        )
    return {
        "schema_version": "1.0",
        "report_type": "parallel_safety_map",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(manifest_path),
        "p0_reference_counts": P0_REFERENCE,
        "current_counts": dict(sorted(counts.items())),
        "suites_moved_from_p0": _moved_suites(suites),
        "summary": dict(sorted(counts.items())),
        "suites": suites,
    }


def _external_state_note(suite) -> str:
    if suite.parallel_safety == "SERIAL_REQUIRED":
        return suite.concurrency_reason or "shared validation/control-plane artifacts"
    if suite.parallel_safety == "LIVE_EXCLUSIVE":
        return "live provider/network boundary"
    if suite.parallel_safety == "RESOURCE_HEAVY":
        return "bounded CPU/memory; process-isolated"
    if suite.concurrency_reason:
        return "none cross-process; " + suite.concurrency_reason
    return "none identified; process-isolated worker"


def _moved_suites(suites: list[dict[str, object]]) -> list[dict[str, str]]:
    moved: list[dict[str, str]] = []
    reclassified = {
        "phase0",
        "phase0a",
        "phase1",
        "platform",
        "phase8",
        "gridiq",
        "ui1",
        "ui2",
        "mra001",
        "mra002",
        "trading_correctness",
    }
    for row in suites:
        suite_id = str(row["id"])
        if suite_id in reclassified and row["parallel_safety"] == "PARALLEL_SAFE":
            moved.append(
                {
                    "id": suite_id,
                    "previous": "GLOBAL_STATE_MUTATION",
                    "current": "PARALLEL_SAFE",
                    "reason": str(row.get("concurrency_reason") or "process-local globals only"),
                }
            )
    return moved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="write JSON map (default: stdout)",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args(argv)
    payload = build_map(args.repository_root.resolve())
    encoded = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
