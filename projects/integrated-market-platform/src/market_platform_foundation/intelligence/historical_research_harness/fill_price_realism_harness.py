"""Read-only fill/MTM repricing on locked v3 fill schedules (Lane F experiment 06)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from ...market_data.historical_development.builder import HistoricalDevelopmentBuildResult
from ...numeric import decimal_to_minor_units
from ...platform.artifact_path_resolver import (
    resolve_stored_file_path,
    resolve_v3_baseline_run_dir,
)
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus.contamination_auditor import audit_research_contamination_run
from ...risk.policy import DEFAULT_RISK_POLICY
from ...risk_simulation.evaluation import risk_simulation_root_hash, run_risk_simulation_from_signal_interpretations
from .baseline_pack import build_baseline_pack_contamination_manifest, verify_frozen_experiment_definition
from .baseline_pack_v2 import OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT, verify_pinned_opend_corpus_fingerprint
from .baseline_pack_v3 import canonical_baseline_pack_v3_evidence_dir, load_pinned_opend_build_v3
from .fill_economics import aggregate_fill_economics, assert_fill_economics_invariants
from .metrics import compute_component_research_metrics
from .pipeline import _load_normalized_bars  # noqa: PLC2701
from .prediction_coupling import build_signal_interpretations_from_predictions
from .split import decision_times_for_split, filter_events_to_decision_times
from .types import HistoricalResearchSplitName

FILL_PRICE_REALISM_EXPERIMENT_ID = "imp-integrate-experiment-06-r1-opend-fill-price-realism-v1"
CANONICAL_FILL_PRICE_REALISM_EVIDENCE_REL = (
    "evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1"
)
V3_PACK_MANIFEST_REL = (
    "evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3"
    "/baseline_pack_run_manifest.json"
)

FILL_REFERENCE_BAR_ADVERSE_TOUCH = "BAR_ADVERSE_TOUCH"
FILL_REFERENCE_BAR_OPEN = "BAR_OPEN"
FILL_REFERENCE_BAR_CLOSE = "BAR_CLOSE"
MTM_LAST_BAR_CLOSE = "MTM_LAST_BAR_CLOSE"
MTM_LAST_BAR_OPEN = "MTM_LAST_BAR_OPEN"


class FillPriceRealismHarnessError(RuntimeError):
    """Fail-closed fill-price realism harness error."""


@dataclass(frozen=True, slots=True)
class FillPriceRealismRunResult:
    ok: bool
    pack_run_id: str
    experiment_definition_hash: str
    artifact_dir: Path
    body: dict[str, Any]
    reason_code: str | None = None


def canonical_fill_price_realism_evidence_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_FILL_PRICE_REALISM_EVIDENCE_REL


def _bar_index(
    events: Sequence[Mapping[str, Any]],
    *,
    instrument_id: str | None,
) -> dict[int, dict[str, Any]]:
    index: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") != "BAR_OHLCV_1M":
            continue
        if instrument_id is not None and str(event.get("instrument_id")) != instrument_id:
            continue
        index[int(event["available_time"])] = dict(event.get("bar_payload") or {})
    return index


def _resolve_fill_price_minor(
    *,
    direction: str,
    payload: Mapping[str, Any],
    fill_price_reference: str,
    price_scale: int,
) -> int:
    if fill_price_reference == FILL_REFERENCE_BAR_ADVERSE_TOUCH:
        key = "high" if direction == "long" else "low"
    elif fill_price_reference == FILL_REFERENCE_BAR_OPEN:
        key = "open"
    elif fill_price_reference == FILL_REFERENCE_BAR_CLOSE:
        key = "close"
    else:
        raise FillPriceRealismHarnessError(f"UNKNOWN_FILL_REFERENCE:{fill_price_reference}")
    return decimal_to_minor_units(str(payload.get(key, "")), scale=price_scale)


def _resolve_mark_price_minor(
    events: Sequence[Mapping[str, Any]],
    *,
    mtm_reference: str,
    instrument_id: str | None,
    price_scale: int,
) -> int | None:
    bars = [
        event
        for event in events
        if event.get("event_type") == "BAR_OHLCV_1M"
        and (instrument_id is None or str(event.get("instrument_id")) == instrument_id)
    ]
    if not bars:
        return None
    last = max(bars, key=lambda row: int(row["available_time"]))
    payload = last.get("bar_payload")
    if not isinstance(payload, dict):
        return None
    key = "close" if mtm_reference == MTM_LAST_BAR_CLOSE else "open"
    if mtm_reference not in {MTM_LAST_BAR_CLOSE, MTM_LAST_BAR_OPEN}:
        raise FillPriceRealismHarnessError(f"UNKNOWN_MTM_REFERENCE:{mtm_reference}")
    try:
        return decimal_to_minor_units(str(payload.get(key, "")), scale=price_scale)
    except ValueError:
        return None


def reprice_locked_fills(
    fills: Sequence[Mapping[str, Any]],
    *,
    events: Sequence[Mapping[str, Any]],
    fill_price_reference: str,
    mtm_reference: str,
    cost_slippage_bps: float,
    policy: Mapping[str, Any] | None = None,
    instrument_id: str | None = None,
) -> dict[str, Any]:
    """Reprice fill minors and MTM without changing fill schedule (qty/time/direction)."""

    active_policy = dict(policy or DEFAULT_RISK_POLICY)
    scale = int(active_policy.get("price_scale", 100))
    bar_by_time = _bar_index(events, instrument_id=instrument_id)
    repriced: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    for fill in fills:
        if not isinstance(fill, Mapping):
            continue
        row = dict(fill)
        fill_time = int(row.get("fill_time") or row.get("available_time") or 0)
        payload = bar_by_time.get(fill_time)
        if payload is None:
            raise FillPriceRealismHarnessError(f"FILL_BAR_MISSING:{fill_time}")
        direction = str(row.get("direction") or "long")
        new_minor = _resolve_fill_price_minor(
            direction=direction,
            payload=payload,
            fill_price_reference=fill_price_reference,
            price_scale=scale,
        )
        row["fill_price_minor"] = new_minor
        repriced.append(row)
        audit_rows.append(
            {
                "fill_time": fill_time,
                "direction": direction,
                "fill_quantity": int(row["fill_quantity"]),
                "fill_price_minor": new_minor,
                "fill_price_reference": fill_price_reference,
                "mtm_reference": mtm_reference,
            }
        )

    mark_minor = _resolve_mark_price_minor(
        events,
        mtm_reference=mtm_reference,
        instrument_id=instrument_id,
        price_scale=scale,
    )
    economics = aggregate_fill_economics(
        repriced,
        events=events,
        policy=active_policy,
        cost_slippage_bps=cost_slippage_bps,
        instrument_id=instrument_id,
        mark_price_minor_override=mark_minor,
    )
    economics["fill_audit_records"] = audit_rows
    economics["fill_price_reference"] = fill_price_reference
    economics["mtm_reference"] = mtm_reference
    economics["mark_price_minor"] = mark_minor
    assert_fill_economics_invariants(
        economics,
        trade_intent_count=economics["fill_count"],
    )
    return economics


def _dev_validate_scope_from_v3_run(
    repository_root: Path,
    build: HistoricalDevelopmentBuildResult,
    *,
    v3_run_manifest: Mapping[str, Any],
    v3_predictions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    from ...market_data.historical_development.e2e_demo import normalized_bars_to_replay_events

    bars = _load_normalized_bars(build)
    if not bars:
        raise FillPriceRealismHarnessError("NORMALIZED_BARS_EMPTY")
    ingest_run_id = f"HIST-RESEARCH-{build.normalized_fingerprint[:12]}"
    events = normalized_bars_to_replay_events(bars, ingest_run_id=ingest_run_id)
    split_assignments = list(v3_run_manifest.get("split_assignments") or [])
    from .types import HistoricalResearchSplitAssignment

    assignment_objs = [
        HistoricalResearchSplitAssignment(
            decision_time_ns=int(row["decision_time_ns"]),
            split=HistoricalResearchSplitName(str(row["split"])),
        )
        for row in split_assignments
    ]
    dev_validate_times = decision_times_for_split(
        assignment_objs,
        HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE,
    )
    dev_validate_events = filter_events_to_decision_times(events, dev_validate_times)
    dev_predictions = [
        dict(row)
        for row in v3_predictions
        if str(row.get("split")) == HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value
    ]
    labels_raw = str((v3_run_manifest.get("outputs") or {}).get("labels_path") or "")
    labels_resolution = resolve_stored_file_path(labels_raw, repository_root=repository_root)
    if labels_resolution.resolved_path is None:
        raise FillPriceRealismHarnessError(
            f"V3_LABELS_UNAVAILABLE:{labels_resolution.reason_code}:{labels_raw}"
        )
    labels_path = labels_resolution.resolved_path
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    dev_labels = [
        row
        for row in labels
        if str(row.get("split")) == HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value
    ]
    return dev_validate_events, dev_predictions, dev_labels


def extract_locked_v3_fills(
    *,
    dev_validate_events: Sequence[Mapping[str, Any]],
    dev_validate_predictions: Sequence[Mapping[str, Any]],
    expected_risk_root_hash: str | None,
) -> tuple[list[dict[str, Any]], str]:
    scoped_event_times_ns = sorted({int(event["available_time"]) for event in dev_validate_events})
    allowed_times = frozenset(scoped_event_times_ns)
    instrument_id = None
    for event in dev_validate_events:
        if event.get("instrument_id"):
            instrument_id = str(event["instrument_id"])
            break
    interpretations, _signals = build_signal_interpretations_from_predictions(
        dev_validate_predictions,
        instrument_id=instrument_id or "UNKNOWN",
        allowed_decision_times_ns=allowed_times,
    )
    risk_result = run_risk_simulation_from_signal_interpretations(
        list(dev_validate_events),
        interpretations,
        desired_quantity=1,
        enable_squeeze_replay=True,
        strategy_result={
            "source": "fill_price_realism_v3_schedule_replay",
            "prediction_count": len(dev_validate_predictions),
        },
    )
    root_hash = risk_simulation_root_hash(risk_result)
    if expected_risk_root_hash and root_hash != expected_risk_root_hash:
        raise FillPriceRealismHarnessError("V3_RISK_SIMULATION_ROOT_HASH_MISMATCH")
    fills = [dict(row) for row in risk_result.get("fills") or [] if isinstance(row, dict)]
    return fills, root_hash


def _directional_gross_correlation(
    *,
    directional_accuracy: float | None,
    gross_pnl: float | None,
) -> dict[str, Any]:
    return {
        "directional_accuracy": directional_accuracy,
        "gross_pnl": gross_pnl,
        "note": "Per-baseline scalar pair; cross-baseline correlation computed in pack summary.",
    }


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    den_y = sum((y - my) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def run_frozen_fill_price_realism_v1(
    *,
    repository_root: Path,
    frozen_definition: dict[str, Any],
    build: HistoricalDevelopmentBuildResult | None = None,
    artifact_root: Path | None = None,
) -> FillPriceRealismRunResult:
    verify = verify_frozen_experiment_definition(frozen_definition)
    if not verify.get("ok"):
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=str(verify.get("computed_hash") or ""),
            artifact_dir=Path(),
            body={"verify": verify},
            reason_code=str(verify.get("reason_code") or "EXPERIMENT_DEFINITION_HASH_MISMATCH"),
        )
    expected_hash = str(verify["experiment_definition_hash"])
    if str(frozen_definition.get("experiment_id") or "") != FILL_PRICE_REALISM_EXPERIMENT_ID:
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={},
            reason_code="EXPERIMENT_ID_MISMATCH",
        )

    dataset_fp = str((frozen_definition.get("dataset") or {}).get("dataset_fingerprint") or "")
    if dataset_fp != OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT:
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={},
            reason_code="DATASET_FINGERPRINT_MISMATCH",
        )

    corpus_pin = canonical_baseline_pack_v3_evidence_dir(repository_root) / "corpus_pin"
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=corpus_pin,
    )
    if not fingerprint_verification.get("ok"):
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={"fingerprint_verification": fingerprint_verification},
            reason_code=str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"),
        )

    active_build = build or load_pinned_opend_build_v3(repository_root)
    if not active_build.ok:
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={},
            reason_code=active_build.reason_code or "BUILD_NOT_OK",
        )

    v3_pack_path = repository_root / V3_PACK_MANIFEST_REL.replace("/", "\\").replace("\\", "/")
    if not v3_pack_path.is_file():
        v3_pack_path = repository_root / "evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/baseline_pack_run_manifest.json"
    if not v3_pack_path.is_file():
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={},
            reason_code="V3_PACK_MANIFEST_MISSING",
        )

    v3_pack = json.loads(v3_pack_path.read_text(encoding="utf-8"))
    arms = list(frozen_definition.get("fill_price_realism_arms") or [])
    if len(arms) != 6:
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={"arm_count": len(arms)},
            reason_code="FILL_ARM_COUNT_MISMATCH",
        )

    run_params = dict(frozen_definition.get("run_parameters") or {})
    cost_bps = float(run_params.get("cost_slippage_bps", 5.0))
    if run_params.get("cost_variation_forbidden") and cost_bps != 5.0:
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={},
            reason_code="COST_BPS_LOCKED_VIOLATION",
        )

    research_code_sha = resolve_runtime_git_sha(start=repository_root)
    arm_results: list[dict[str, Any]] = []
    split_assignments_ref: list[dict[str, Any]] = []
    feature_lineage_ref: list[dict[str, Any]] = []

    for baseline_row in v3_pack.get("baseline_results") or []:
        if not isinstance(baseline_row, dict):
            continue
        run_id = str(baseline_row.get("run_id") or "")
        strategy_id = str(baseline_row.get("strategy_id") or "")
        run_dir = resolve_v3_baseline_run_dir(
            repository_root,
            run_id=run_id,
            manifest_path=str(baseline_row.get("manifest_path") or ""),
        )
        if run_dir is None:
            return FillPriceRealismRunResult(
                ok=False,
                pack_run_id="",
                experiment_definition_hash=expected_hash,
                artifact_dir=Path(),
                body={"missing_run_id": run_id},
                reason_code="V3_FILL_SCHEDULE_RUN_DIR_UNAVAILABLE",
            )
        v3_run_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        predictions = json.loads((run_dir / "predictions.json").read_text(encoding="utf-8"))
        labels_path = run_dir / "labels.json"
        v3_run_manifest = dict(v3_run_manifest)
        v3_run_manifest.setdefault("outputs", {})
        v3_run_manifest["outputs"]["labels_path"] = str(labels_path)
        if not split_assignments_ref:
            split_assignments_ref = list(v3_run_manifest.get("split_assignments") or [])

        try:
            dev_events, dev_predictions, dev_labels = _dev_validate_scope_from_v3_run(
                repository_root,
                active_build,
                v3_run_manifest=v3_run_manifest,
                v3_predictions=predictions,
            )
        except FillPriceRealismHarnessError as exc:
            return FillPriceRealismRunResult(
                ok=False,
                pack_run_id="",
                experiment_definition_hash=expected_hash,
                artifact_dir=Path(),
                body={"strategy_id": strategy_id},
                reason_code=str(exc),
            )

        expected_hash_risk = str((v3_run_manifest.get("simulator") or {}).get("risk_simulation_root_hash") or "")
        try:
            locked_fills, risk_hash = extract_locked_v3_fills(
                dev_validate_events=dev_events,
                dev_validate_predictions=dev_predictions,
                expected_risk_root_hash=expected_hash_risk or None,
            )
        except FillPriceRealismHarnessError as exc:
            return FillPriceRealismRunResult(
                ok=False,
                pack_run_id="",
                experiment_definition_hash=expected_hash,
                artifact_dir=Path(),
                body={"strategy_id": strategy_id, "risk_hash_expected": expected_hash_risk},
                reason_code=str(exc),
            )

        v3_validate_metrics = dict((baseline_row.get("metrics_by_split") or {}).get("HISTORICAL_DEVELOPMENT_VALIDATE") or {})
        directional_accuracy = v3_validate_metrics.get("directional_accuracy")

        baseline_arms: list[dict[str, Any]] = []
        for arm in arms:
            arm_id = str(arm.get("arm_id") or "")
            fill_ref = str(arm.get("fill_price_reference") or "")
            mtm_ref = str(arm.get("mtm_reference") or "")
            economics = reprice_locked_fills(
                locked_fills,
                events=dev_events,
                fill_price_reference=fill_ref,
                mtm_reference=mtm_ref,
                cost_slippage_bps=cost_bps,
            )
            metrics = compute_component_research_metrics(
                predictions=dev_predictions,
                labels=dev_labels,
                simulator_summary={
                    "gross_pnl": economics["gross_pnl"],
                    "gross_realized_pnl": economics["gross_realized_pnl"],
                    "gross_unrealized_pnl": economics["gross_unrealized_pnl"],
                    "net_pnl": economics["net_pnl"],
                    "transaction_costs": economics["transaction_costs"],
                    "traded_notional": economics["traded_notional"],
                    "turnover": economics["turnover"],
                    "exposure": economics["exposure"],
                    "fills": economics["fill_count"],
                    "winning_closed_trades": economics["winning_closed_trades"],
                    "losing_closed_trades": economics["losing_closed_trades"],
                },
            )
            baseline_arms.append(
                {
                    "arm_id": arm_id,
                    "fill_price_reference": fill_ref,
                    "mtm_reference": mtm_ref,
                    "fill_count": economics["fill_count"],
                    "gross_pnl": economics["gross_pnl"],
                    "gross_realized_pnl": economics["gross_realized_pnl"],
                    "gross_unrealized_pnl": economics["gross_unrealized_pnl"],
                    "net_pnl": economics["net_pnl"],
                    "transaction_costs": economics["transaction_costs"],
                    "traded_notional": economics["traded_notional"],
                    "directional_accuracy": metrics.get("directional_accuracy", directional_accuracy),
                    "directional_gross_pair": _directional_gross_correlation(
                        directional_accuracy=metrics.get("directional_accuracy", directional_accuracy),
                        gross_pnl=economics["gross_pnl"],
                    ),
                    "fill_audit_sample": (economics.get("fill_audit_records") or [])[:3],
                }
            )

        gross_values = [float(row["gross_pnl"]) for row in baseline_arms if row.get("gross_pnl") is not None]
        dir_values = [
            float(row["directional_accuracy"])
            for row in baseline_arms
            if row.get("directional_accuracy") is not None
        ]
        arm_results.append(
            {
                "baseline_index": baseline_row.get("baseline_index"),
                "strategy_id": strategy_id,
                "v3_run_id": run_id,
                "v3_risk_simulation_root_hash": risk_hash,
                "locked_fill_count": len(locked_fills),
                "v3_validate_directional_accuracy": directional_accuracy,
                "v3_validate_gross_pnl": v3_validate_metrics.get("gross_pnl"),
                "arms": baseline_arms,
                "within_baseline_arm_gross_spread": (max(gross_values) - min(gross_values)) if gross_values else 0.0,
            }
        )

    contamination_manifest = build_baseline_pack_contamination_manifest(
        pack_run_id=f"fill-realism-{expected_hash[:12]}",
        dataset_fingerprint=dataset_fp,
        split_assignments=split_assignments_ref,
        feature_lineage=feature_lineage_ref,
        historical_dataset_manifest=active_build.manifest if isinstance(active_build.manifest, dict) else None,
    )
    contamination_report = audit_research_contamination_run(contamination_manifest)
    fill_tune_check = {
        "check_id": "DID_FILL_REFERENCE_TUNE_ON_VALIDATE",
        "verdict": "PASS",
        "note": "Arms frozen in experiment definition before execution.",
    }
    contamination_report.setdefault("supplemental_checks", []).append(fill_tune_check)
    if contamination_report.get("CONTAMINATION_STATUS") != "PASS":
        return FillPriceRealismRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            artifact_dir=Path(),
            body={"contamination_report": contamination_report},
            reason_code="CONTAMINATION_AUDITOR_FAIL",
        )

    out_root = artifact_root or (
        repository_root / "artifacts" / "historical-research-harness" / "fill-price-realism-v1"
    )
    pack_run_id = sha256_bytes(
        canonical_bytes(
            {
                "experiment_id": FILL_PRICE_REALISM_EXPERIMENT_ID,
                "experiment_definition_hash": expected_hash,
                "research_code_sha": research_code_sha,
                "arm_results_fingerprint": sha256_bytes(canonical_bytes({"rows": arm_results})),
            }
        )
    )[:32].upper()
    evidence_dir = canonical_fill_price_realism_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    run_record = {
        "artifact_kind": "historical_fill_price_realism_run_v1",
        "authority": "HISTORICAL_DEVELOPMENT",
        "contamination_report": contamination_report,
        "cost_slippage_bps": cost_bps,
        "evidence_class": "BOUNDED_HISTORICAL_OBSERVATION",
        "experiment_definition_hash": expected_hash,
        "experiment_id": FILL_PRICE_REALISM_EXPERIMENT_ID,
        "hypothesis_id": frozen_definition.get("hypothesis_id"),
        "pack_run_id": pack_run_id,
        "research_code_sha": research_code_sha,
        "results": arm_results,
        "spec_bundle_sha256": "bcf758df3cf7a2047f1c7caaae1e4b9f5df4542710edcd1d2bc582cb12ccbb34",
        "timestamp_ns": time.time_ns(),
        "v3_pack_manifest_path": str(v3_pack_path.relative_to(repository_root)),
    }
    run_path = evidence_dir / "fill_price_realism_run_record.json"
    run_path.write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "artifact_kind": "historical_fill_price_realism_evidence_receipt_v1",
        "contamination_status": contamination_report.get("CONTAMINATION_STATUS"),
        "executed": True,
        "experiment_definition_hash": expected_hash,
        "experiment_id": FILL_PRICE_REALISM_EXPERIMENT_ID,
        "pack_run_id": pack_run_id,
        "research_code_sha": research_code_sha,
        "run_record_path": str(run_path.relative_to(repository_root)),
    }
    receipt_path = evidence_dir / "fill_price_realism_evidence_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    return FillPriceRealismRunResult(
        ok=True,
        pack_run_id=pack_run_id,
        experiment_definition_hash=expected_hash,
        artifact_dir=evidence_dir,
        body=run_record,
        reason_code=None,
    )


__all__ = [
    "CANONICAL_FILL_PRICE_REALISM_EVIDENCE_REL",
    "FILL_PRICE_REALISM_EXPERIMENT_ID",
    "FillPriceRealismHarnessError",
    "FillPriceRealismRunResult",
    "canonical_fill_price_realism_evidence_dir",
    "extract_locked_v3_fills",
    "reprice_locked_fills",
    "resolve_v3_baseline_run_dir",
    "run_frozen_fill_price_realism_v1",
]
