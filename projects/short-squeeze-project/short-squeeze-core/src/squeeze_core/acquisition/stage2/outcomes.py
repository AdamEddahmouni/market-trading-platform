"""Forward outcome manifest construction for Phase 3E Stage 2."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from squeeze_core.acquisition.operation_readiness.evidence_inputs import boundary_id_for
from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import load_detection_context_bars
from squeeze_core.acquisition.phase3a_freeze.models import (
    ReceiptModelingPolicy,
    TimestampInterpretation,
)
from squeeze_core.research.models import OutcomeCompleteness, RetrospectiveOutcomeObservation
from squeeze_core.research.outcomes import label_outcome
from squeeze_core.research.policies import load_outcome_policy
from squeeze_core.research.serialization import serialize_research_model
from squeeze_core.serialization import canonical_json_bytes

from .constants import (
    FROZEN_BOUNDARY,
    OUTCOME_LABEL_POLICY_VERSION,
    RETRIEVAL_COMPLETED_AT,
    STAGE2_PLAN_ID,
    STAGE2_PLAN_VERSION,
)


@dataclass(frozen=True)
class OutcomeBuildResult:
    symbol: str
    case_id: str
    observation: RetrospectiveOutcomeObservation
    manifest: dict
    manifest_id: str
    forward_source: str
    forward_bar_count: int


def outcome_manifest_id_for(case_id: str) -> str:
    return f"{case_id}::STAGE2_OUTCOME_MANIFEST"


def _parse_forward_csv(batch05_root: Path, symbol: str) -> tuple[list[dict[str, str]], str]:
    stage2_path = batch05_root / "raw" / f"{symbol}-forward-outcome.csv"
    legacy_path = batch05_root / "raw" / f"{symbol}-frozen-forward-24h.csv"
    if stage2_path.exists():
        path = stage2_path
        source = "stage2_forward_outcome"
    elif legacy_path.exists():
        path = legacy_path
        source = "frozen_forward_24h"
    else:
        raise FileNotFoundError(
            f"no forward window CSV for {symbol}: checked {stage2_path} and {legacy_path}"
        )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty forward window for {symbol}: {path}")
    return rows, source


def _load_detection_bars(batch05_root: Path, symbol: str) -> tuple:
    path = batch05_root / "raw" / f"{symbol}-detection-context.csv"
    loaded = load_detection_context_bars(
        path,
        symbol=symbol,
        boundary=FROZEN_BOUNDARY,
        retrieval_completed_at=RETRIEVAL_COMPLETED_AT,
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        interpretation=TimestampInterpretation.LABEL_IS_INTERVAL_START,
    )
    return loaded.observations


def _reference_price(batch05_root: Path, symbol: str) -> Decimal:
    observations = _load_detection_bars(batch05_root, symbol)
    if not observations:
        raise ValueError(f"no detection-context bars for {symbol}")
    last = max(
        observations,
        key=lambda item: item.provenance.provider_metadata["bar_end"],
    )
    return Decimal(str(last.payload.close))


def _outcome_moves(
    batch05_root: Path, symbol: str, reference: Decimal,
) -> tuple[Decimal, Decimal, int, str]:
    rows, source = _parse_forward_csv(batch05_root, symbol)
    highs = [Decimal(row["high"]) for row in rows]
    lows = [Decimal(row["low"]) for row in rows]
    if reference == 0:
        return Decimal("0"), Decimal("0"), len(rows), source
    maximum = max(((high - reference) / reference) * Decimal("100") for high in highs)
    adverse = min(((low - reference) / reference) * Decimal("100") for low in lows)
    return maximum, adverse, len(rows), source


def _outcome_limitations(*, live: bool, forward_bar_count: int, forward_source: str) -> tuple[str, ...]:
    base = (
        "outcome movement does not establish short-squeeze causation",
        "published short interest evidence is unavailable",
        "historical borrow evidence remains unavailable",
    )
    if forward_source == "stage2_forward_outcome":
        return base + (
            "forward outcome window uses Phase 3E Stage 2 adjusted Monday window",
            "weekend boundary shifted +72h calendar with ~6.5h regular session bias",
            "absolute price-level semantics remain blocked by Batch 07 readiness",
        )
    if live and forward_bar_count >= 100:
        return base + (
            "forward outcome window uses live IBKR historical bars",
            "absolute price-level semantics remain blocked by Batch 07 readiness",
        )
    return base + (
        "forward outcome window uses sparse IBKR-shaped fixture coverage",
        "absolute price-level semantics remain blocked by Batch 07 readiness",
    )


def build_outcome(
    *,
    symbol: str,
    case_id: str,
    batch05_root: Path,
    live_intake: bool,
    research_case_id: str | None = None,
) -> OutcomeBuildResult:
    """Compute outcome observation and separate manifest for one symbol."""
    reference = _reference_price(batch05_root, symbol)
    maximum, adverse, forward_bars, forward_source = _outcome_moves(
        batch05_root, symbol, reference
    )
    limitations = _outcome_limitations(
        live=live_intake,
        forward_bar_count=forward_bars,
        forward_source=forward_source,
    )
    completeness = (
        OutcomeCompleteness.COMPLETE
        if live_intake and forward_bars >= 100
        else OutcomeCompleteness.PARTIAL
    )
    resolved_case_id = research_case_id or f"{symbol}_ARTIFACT_DISCOVERY"
    observation = RetrospectiveOutcomeObservation(
        case_id=resolved_case_id,
        symbol=symbol,
        detection_boundary=FROZEN_BOUNDARY,
        reference_price_policy="first_eligible_trade_bar_close_at_or_after_boundary.v1",
        reference_price=reference,
        horizon="24_HOURS",
        maximum_observed_move_percent=maximum,
        maximum_adverse_move_percent=adverse,
        completeness=completeness,
        supporting_observation_ids=(boundary_id_for(case_id, symbol),),
        limitations=limitations,
    )
    manifest_id = outcome_manifest_id_for(case_id)
    policy = load_outcome_policy(OUTCOME_LABEL_POLICY_VERSION)
    label_result = label_outcome(observation, policy)
    manifest = {
        "schema_version": "1.0.0",
        "outcome_manifest_id": manifest_id,
        "acquisition_plan_id": STAGE2_PLAN_ID,
        "acquisition_plan_version": STAGE2_PLAN_VERSION,
        "outcome_label_policy_version": OUTCOME_LABEL_POLICY_VERSION,
        "horizon": policy.horizon,
        "upward_threshold_percent": str(policy.upward_threshold_percent),
        "downward_threshold_percent": str(policy.downward_threshold_percent),
        "captured": True,
        "forward_source": forward_source,
        "forward_bar_count": forward_bars,
        "case_id": case_id,
        "symbol": symbol,
        "outcome_label": label_result.label.value,
        "outcome_label_id": label_result.deterministic_id,
        "note": (
            "Retrospective outcome manifest is a separate contract from the Phase 3A "
            "evaluation freeze. Outcome bars were acquired only after the Stage 2 plan "
            "and Phase 3A freeze were committed."
        ),
    }
    return OutcomeBuildResult(
        symbol=symbol,
        case_id=case_id,
        observation=observation,
        manifest=manifest,
        manifest_id=manifest_id,
        forward_source=forward_source,
        forward_bar_count=forward_bars,
    )


def write_outcome_artifacts(result: OutcomeBuildResult, out_dir: Path) -> dict[str, str]:
    """Write outcome-manifest.json and outcome-observation.json for one symbol."""
    symbol_dir = out_dir / result.symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    manifest_bytes = canonical_json_bytes(result.manifest)
    observation_bytes = serialize_research_model(result.observation)
    manifest_path = symbol_dir / "outcome-manifest.json"
    observation_path = symbol_dir / "outcome-observation.json"
    manifest_path.write_bytes(manifest_bytes)
    observation_path.write_bytes(observation_bytes)
    return {
        "manifest_path": str(manifest_path),
        "observation_path": str(observation_path),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "observation_sha256": hashlib.sha256(observation_bytes).hexdigest(),
        "manifest_id": result.manifest_id,
    }


__all__ = [
    "OutcomeBuildResult",
    "build_outcome",
    "outcome_manifest_id_for",
    "write_outcome_artifacts",
]
