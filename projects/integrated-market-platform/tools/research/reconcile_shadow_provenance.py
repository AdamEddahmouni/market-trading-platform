"""Reconcile immutable pre-fix shadow decisions against sealed capture files.

Does not mutate experiment-store rows. Emits an auditable artifact mapping
legacy decision buckets to capture event/available times for P6-AC-005.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

_NS = 1_000_000_000
_BUCKET_SECONDS = 60


def _bucket_bounds(bucket: int) -> tuple[int, int]:
    start = int(bucket) * _BUCKET_SECONDS * _NS
    return start, start + _BUCKET_SECONDS * _NS - 1


def _load_capture_events(path: Path) -> list[dict]:
    events: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                events.append(payload)
    return events


def reconcile_run(
    *,
    run_id: str,
    store_root: Path,
    capture_id: str | None = None,
) -> dict:
    from market_platform_foundation.shadow.experiment import ShadowExperimentStore

    capture_root = store_root / "captures"
    exp = ShadowExperimentStore(store_root / "experiment.sqlite3")
    try:
        contract = exp.manifest(run_id)
        if contract is None:
            raise ValueError(f"RUN_NOT_FOUND:{run_id}")
        cfg = contract["manifest"].get("config") or {}
        resolved_capture_id = capture_id or str(cfg.get("capture_id") or "")
        capture_path = capture_root / f"{resolved_capture_id}.jsonl"
        if not capture_path.is_file():
            raise ValueError(f"CAPTURE_NOT_FOUND:{capture_path}")

        events = _load_capture_events(capture_path)
        by_bucket: dict[int, list[dict]] = {}
        for event in events:
            clocks = event.get("clocks") or {}
            event_ns = clocks.get("event_time_ns")
            if not isinstance(event_ns, int) or event_ns <= 0:
                continue
            bucket = event_ns // (_BUCKET_SECONDS * _NS)
            by_bucket.setdefault(bucket, []).append(event)

        reconciled: list[dict] = []
        unreconciled: list[int] = []
        for decision in exp.iter_decisions(run_id):
            detail = decision.get("detail") or {}
            if detail.get("decision_time_ns") and detail.get("available_time_ns"):
                continue
            bucket = int(decision["decision_bucket"])
            bucket_events = by_bucket.get(bucket) or []
            if not bucket_events:
                unreconciled.append(int(decision["id"]))
                continue
            event_times = [
                int((e.get("clocks") or {})["event_time_ns"])
                for e in bucket_events
                if isinstance((e.get("clocks") or {}).get("event_time_ns"), int)
            ]
            available_times = [
                int((e.get("clocks") or {})["received_time_ns"])
                for e in bucket_events
                if isinstance((e.get("clocks") or {}).get("received_time_ns"), int)
            ]
            if not event_times or not available_times:
                unreconciled.append(int(decision["id"]))
                continue
            decision_time_ns = min(event_times)
            reconciled.append(
                {
                    "decision_id": int(decision["id"]),
                    "instrument_id": decision["instrument_id"],
                    "decision_bucket": bucket,
                    "outcome": decision["outcome"],
                    "capture_id": resolved_capture_id,
                    "capture_path": str(capture_path),
                    "decision_time_ns": decision_time_ns,
                    "available_time_ns": min(available_times),
                    "capture_events_in_bucket": len(bucket_events),
                    "method": "sealed_capture_bucket_replay_v1",
                }
            )
    finally:
        exp.close()

    return {
        "schema_version": "platform/shadow-run-1-provenance-reconciliation/1.0.0",
        "run_id": run_id,
        "capture_id": resolved_capture_id,
        "capture_path": str(capture_path),
        "reconciled_decisions": reconciled,
        "unreconciled_decision_ids": unreconciled,
        "summary": {
            "reconciled": len(reconciled),
            "unreconciled": len(unreconciled),
        },
    }


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "tools" / "research"))
    import run_shadow_run as shadow_cli  # noqa: E402

    parser = argparse.ArgumentParser(description="Reconcile legacy shadow decision provenance from captures")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store-root", default=str(shadow_cli.store_root_default()))
    parser.add_argument("--capture-id", default="")
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "shadow-run-1" / "LEGACY_PROVENANCE_RECONCILIATION.json"))
    args = parser.parse_args(argv)

    report = reconcile_run(
        run_id=args.run_id,
        store_root=Path(args.store_root),
        capture_id=args.capture_id or None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 1 if report["summary"]["unreconciled"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
