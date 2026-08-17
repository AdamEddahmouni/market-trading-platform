"""Availability-aware replay with feature snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..features.bar_features import BAR_FEATURE_IDS, SUPPORTED_CAPABILITY, derive_bar_features
from ..features.institutional import LARGE_TRANSACTIONS_FAMILY, NO_ENTITLED_SOURCE, OPTIONS_FAMILY, ORDER_FLOW_FAMILY, REGULATORY_DISCLOSURE_FAMILY, query_all_institutional
from ..features.snapshot import build_feature_snapshot
from .quality_lifecycle import QualityReplayState, run_quality_replay


@dataclass
class FeatureReplayState:
    quality_state: QualityReplayState
    feature_snapshots: list[dict[str, Any]] = field(default_factory=list)
    rejected_future_inputs: list[dict[str, str]] = field(default_factory=list)


def run_feature_replay(
    events: list[dict[str, Any]],
    *,
    clocks: list[int],
    decision_times: list[int],
    prediction_cutoff: int,
) -> FeatureReplayState:
    quality_state = run_quality_replay(events, clocks=clocks, decision_times=decision_times)
    state = FeatureReplayState(quality_state=quality_state)
    for decision_time in decision_times:
        cutoff = min(prediction_cutoff, decision_time)
        bar_features, pit_reasons = derive_bar_features(
            quality_state.bar_book.bars_by_instrument,
            prediction_cutoff=cutoff,
        )
        for reason in pit_reasons:
            state.rejected_future_inputs.append(
                {"decision_time": str(decision_time), "reason_code": reason}
            )
        institutional = query_all_institutional(prediction_cutoff=cutoff)
        snapshot = build_feature_snapshot(
            prediction_cutoff=cutoff,
            bar_features=bar_features,
            institutional_evidence=institutional,
        )
        state.feature_snapshots.append(snapshot)
    return state


def run_feature_root_hash(state: FeatureReplayState) -> str:
    body = {
        "feature_snapshot_hashes": [row["snapshot_hash"] for row in state.feature_snapshots],
        "quality_root": sha256_bytes(
            canonical_bytes(
                {
                    "artifact_manifest": state.quality_state.artifact_manifest,
                    "decisions": state.quality_state.decisions,
                }
            )
        ),
        "rejected_future_inputs": state.rejected_future_inputs,
    }
    return sha256_bytes(canonical_bytes(body))


def verify_capability_surface(snapshot: dict[str, object]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    bar_features = snapshot.get("bar_features", [])
    if not isinstance(bar_features, list):
        return "FAIL", ["CAP001_INVALID_SNAPSHOT"]
    for row in bar_features:
        if not isinstance(row, dict):
            reasons.append("CAP001_INVALID_FEATURE_ROW")
            continue
        if str(row.get("capability")) != SUPPORTED_CAPABILITY:
            reasons.append("CAP001_UNSUPPORTED_CAPABILITY")
        if str(row.get("feature_id")) not in BAR_FEATURE_IDS:
            reasons.append("CAP001_UNSUPPORTED_FEATURE_ID")
    institutional = snapshot.get("institutional_evidence", [])
    if not isinstance(institutional, list):
        return "FAIL", ["CAP001_INVALID_INSTITUTIONAL"]
    for row in institutional:
        if not isinstance(row, dict):
            reasons.append("CAP001_INVALID_INSTITUTIONAL_ROW")
            continue
        family = str(row.get("family", ""))
        status = str(row.get("status", ""))
        reason = str(row.get("reason_code", ""))
        if family == REGULATORY_DISCLOSURE_FAMILY and status == "available":
            from ..providers.whale_ledger import WHALE_ENTITLED_DISCLOSURE

            if reason != WHALE_ENTITLED_DISCLOSURE:
                reasons.append("CAP001_INSTITUTIONAL_REASON_MISMATCH")
            continue
        if family == ORDER_FLOW_FAMILY and status == "available":
            from ..providers.whale_ledger import WHALE_ENTITLED_ORDER_FLOW

            if reason != WHALE_ENTITLED_ORDER_FLOW:
                reasons.append("CAP001_INSTITUTIONAL_REASON_MISMATCH")
            continue
        if family == OPTIONS_FAMILY and status == "available":
            from ..providers.whale_ledger import WHALE_ENTITLED_OPTIONS

            if reason != WHALE_ENTITLED_OPTIONS:
                reasons.append("CAP001_INSTITUTIONAL_REASON_MISMATCH")
            continue
        if family == LARGE_TRANSACTIONS_FAMILY and status == "available":
            from ..providers.whale_ledger import WHALE_ENTITLED_LARGE_TRANSACTIONS

            if reason != WHALE_ENTITLED_LARGE_TRANSACTIONS:
                reasons.append("CAP001_INSTITUTIONAL_REASON_MISMATCH")
            continue
        if status != "unavailable":
            reasons.append("CAP001_INSTITUTIONAL_OVERCLAIM")
        elif reason != NO_ENTITLED_SOURCE:
            reasons.append("CAP001_INSTITUTIONAL_REASON_MISMATCH")
    status = "PASS" if not reasons else "FAIL"
    return status, sorted(set(reasons))


def verify_pit_surface(snapshot: dict[str, object]) -> tuple[str, list[str]]:
    cutoff = int(snapshot["prediction_cutoff"])
    reasons: list[str] = []
    bar_features = snapshot.get("bar_features", [])
    if isinstance(bar_features, list):
        for row in bar_features:
            if isinstance(row, dict) and int(row.get("available_time", 0)) > cutoff:
                reasons.append("PIT_FEATURE_FUTURE_INPUT")
    status = "PASS" if not reasons else "FAIL"
    return status, sorted(set(reasons))
