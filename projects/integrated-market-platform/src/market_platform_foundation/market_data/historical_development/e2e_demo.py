"""Lane D: bounded historical development end-to-end demonstration (not calibrated)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...replay.feature_lifecycle import run_feature_replay, run_feature_root_hash
from ...risk_simulation.evaluation import risk_simulation_root_hash, run_risk_simulation_evaluation
from .builder import HistoricalDevelopmentBuildResult

DEMO_EVIDENCE_CLASS = "HISTORICAL_DEVELOPMENT_ONLY"
DEMO_PURPOSE = "HISTORICAL_DEVELOPMENT"
NORMALIZATION_VERSION = "historical_development/e2e-demo/1.0.0"
INGEST_RUN_PREFIX = "HIST-DEV-E2E"


def default_demo_artifact_root(repository_root: Path) -> Path:
    return repository_root / "artifacts" / "historical-development"


def historical_development_governance_lines() -> tuple[str, ...]:
    return (
        f"AUTHORITY: {CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT}",
        "PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED",
        "CALIBRATION_STATE_CHANGED: NO",
        "FTEP_STATE_CHANGED: NO",
    )


def enrich_normalized_bar_for_replay(
    bar: Mapping[str, Any],
    *,
    ingest_run_id: str,
    provenance_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach replay/simulator envelope fields to a Lane B normalized bar."""

    available = int(bar["available_time"])
    event_time = int(bar.get("event_time") or available)
    instrument_id = str(bar.get("instrument_id") or "")
    normalized_event_id = str(bar.get("normalized_event_id") or "")
    prov = dict(provenance_ref or bar.get("historical_provenance_ref") or {})
    raw_reference = (
        f"historical-development:{prov.get('dataset_id', 'unknown')}:"
        f"{prov.get('raw_payload_sha256', '')[:16]}"
    )
    event = {
        "available_time": available,
        "bar_payload": dict(bar.get("bar_payload") or {}),
        "channel_id": str(bar.get("channel_id") or instrument_id),
        "event_time": event_time,
        "event_type": str(bar.get("event_type") or "BAR_OHLCV_1M"),
        "historical_ingested_time": available,
        "ingest_run_id": ingest_run_id,
        "instrument_id": instrument_id,
        "normalization_version": NORMALIZATION_VERSION,
        "normalized_event_id": normalized_event_id,
        "operation": "UPSERT",
        "publisher_id": str(bar.get("publisher_id") or "historical_development"),
        "quality_observation_refs": [],
        "raw_reference": raw_reference,
        "schema_version": "1.0.0",
        "source_instance_id": str(bar.get("source_instance_id") or "HISTORICAL_DEVELOPMENT_RTH"),
        "source_record_id": str(bar.get("source_record_id") or ""),
        "source_revision_id": "1",
        "venue_id": "US",
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    }
    return event


def normalized_bars_to_replay_events(
    bars: Sequence[Mapping[str, Any]],
    *,
    ingest_run_id: str,
) -> list[dict[str, Any]]:
    events = [enrich_normalized_bar_for_replay(row, ingest_run_id=ingest_run_id) for row in bars]
    events.sort(key=lambda row: (int(row["available_time"]), str(row["normalized_event_id"])))
    return events


@dataclass(frozen=True, slots=True)
class HistoricalDevelopmentE2eResult:
    ok: bool
    run_id: str
    artifact_path: Path
    body: dict[str, Any]
    reason_code: str | None = None


def run_historical_development_e2e_demo(
    *,
    repository_root: Path,
    build: HistoricalDevelopmentBuildResult,
    demo_artifact_root: Path | None = None,
) -> HistoricalDevelopmentE2eResult:
    """Feature replay + risk simulation on a Lane B build (development only)."""

    if not build.ok or not build.normalized_fingerprint:
        return HistoricalDevelopmentE2eResult(
            ok=False,
            run_id=build.run_id,
            artifact_path=Path(),
            body={},
            reason_code=build.reason_code or "BUILD_NOT_OK",
        )
    normalized_path = build.paths.normalized_dir
    json_files = sorted(normalized_path.glob("*_normalized.json"))
    if not json_files:
        return HistoricalDevelopmentE2eResult(
            ok=False,
            run_id=build.run_id,
            artifact_path=Path(),
            body={},
            reason_code="NORMALIZED_ARTIFACT_MISSING",
        )
    bars = json.loads(json_files[0].read_text(encoding="utf-8"))
    if not isinstance(bars, list) or not bars:
        return HistoricalDevelopmentE2eResult(
            ok=False,
            run_id=build.run_id,
            artifact_path=Path(),
            body={},
            reason_code="NORMALIZED_BARS_EMPTY",
        )
    ingest_run_id = f"{INGEST_RUN_PREFIX}-{build.normalized_fingerprint[:12]}"
    events = normalized_bars_to_replay_events(bars, ingest_run_id=ingest_run_id)
    clocks = sorted({int(event["available_time"]) for event in events})
    decision_time = clocks[-1]
    feature_state = run_feature_replay(
        events,
        clocks=clocks,
        decision_times=[decision_time],
        prediction_cutoff=decision_time,
    )
    feature_root = run_feature_root_hash(feature_state)
    risk_result = run_risk_simulation_evaluation(events, enable_squeeze_replay=True)
    risk_root = risk_simulation_root_hash(risk_result)
    code_sha = resolve_runtime_git_sha(start=repository_root)
    demo_root = demo_artifact_root or default_demo_artifact_root(repository_root)
    out_dir = demo_root / "demo-runs" / build.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / "e2e_result.json"
    body: dict[str, Any] = {
        "artifact_kind": "historical_development_e2e_demo_v1",
        "evidence_class": DEMO_EVIDENCE_CLASS,
        "purpose": DEMO_PURPOSE,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "governance": {
            "authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "prospective_item9_admission": "NOT_ALLOWED",
            "calibration_state_changed": "NO",
            "calibrated": False,
            "prospective": False,
        },
        "lane_b_run_id": build.run_id,
        "dataset_fingerprint": build.manifest.get("dataset_fingerprint"),
        "normalized_fingerprint": build.normalized_fingerprint,
        "quality_fingerprint": build.quality.get("quality_fingerprint"),
        "manifest_path": str(build.paths.manifests_dir / "dataset_manifest.json"),
        "quality_report_path": str(build.paths.quality_dir / "quality_report.json"),
        "bar_event_count": len(events),
        "decision_time_ns": decision_time,
        "feature_replay": {
            "feature_root_hash": feature_root,
            "snapshot_count": len(feature_state.feature_snapshots),
            "rejected_future_inputs": feature_state.rejected_future_inputs,
        },
        "risk_simulation": {
            "risk_simulation_root_hash": risk_root,
            "fill_audit_status": risk_result.get("fill_audit", {}).get("status"),
            "order_count": len(risk_result.get("orders", [])),
            "intent_count": len(risk_result.get("intents", [])),
        },
        "code_sha": code_sha,
        "ingest_run_id": ingest_run_id,
    }
    body["result_fingerprint"] = sha256_bytes(canonical_bytes(body))
    artifact_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return HistoricalDevelopmentE2eResult(
        ok=True,
        run_id=build.run_id,
        artifact_path=artifact_path,
        body=body,
    )


__all__ = [
    "DEMO_EVIDENCE_CLASS",
    "DEMO_PURPOSE",
    "HistoricalDevelopmentE2eResult",
    "default_demo_artifact_root",
    "enrich_normalized_bar_for_replay",
    "historical_development_governance_lines",
    "normalized_bars_to_replay_events",
    "run_historical_development_e2e_demo",
]
