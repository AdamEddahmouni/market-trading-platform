"""Generate Phase 3A evaluation fixtures for IBKR cohort symbols.

Prefers live Batch 05 private intake under ``intake/local-bars/ibkr-batch-05`` when
present (from ``tools.ibkr_historical_export run``). Falls back to the committed Batch 08
synthetic Batch-05-shaped fixtures for offline CI.

Outcome aggregates are computed from the frozen-forward CSV window with explicit
limitations when coverage is sparse.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from squeeze_core.acquisition.operation_readiness.evidence_inputs import (  # noqa: E402
    FROZEN_BOUNDARY,
    FROZEN_COHORT,
    boundary_id_for,
)
from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import (  # noqa: E402
    load_detection_context_bars,
)
from squeeze_core.acquisition.phase3a_freeze.models import (  # noqa: E402
    ReceiptModelingPolicy,
    TimestampInterpretation,
)
from squeeze_core.evaluation.serialization import serialize_candidate_evaluation  # noqa: E402
from squeeze_core.research.models import OutcomeCompleteness, RetrospectiveOutcomeObservation  # noqa: E402
from squeeze_core.research.serialization import serialize_research_model  # noqa: E402
from squeeze_core.serialization import canonical_json_bytes  # noqa: E402

LIVE_BATCH05_ROOT = ROOT / "intake" / "local-bars" / "ibkr-batch-05"
STAGE2_FORWARD_ROOT = LIVE_BATCH05_ROOT / "raw"
STAGE2_SUMMARY = ROOT / "build" / "acquisition" / "stage2" / "collection-summary.json"
SYNTHETIC_BATCH05_ROOT = ROOT / "tests" / "fixtures" / "acquisition" / "batch08" / "synthetic-batch05"
LIVE_FREEZE_ROOT = LIVE_BATCH05_ROOT / "phase3a" / "batch-08"
SYNTHETIC_FREEZE_ROOT = ROOT / "intake" / "local-bars" / "phase3a-batch08-synthetic"
EVAL_OUT = ROOT / "tests" / "fixtures" / "evaluation"
RESEARCH_OUT = ROOT / "tests" / "fixtures" / "research"

# Phase 3E preregistered 13-symbol pilot cohort plus KLRS/SG IBKR extensions.
COHORT = tuple(
    (symbol, f"{symbol}_ARTIFACT_DISCOVERY", case_id)
    for symbol, case_id in FROZEN_COHORT[:13]
) + (
    ("KLRS", "KLRS_ARTIFACT_DISCOVERY", "BATCH01_KLRS_20260718"),
    ("SG", "SG_ARTIFACT_DISCOVERY", "BATCH01_SG_20260718"),
)

RETRIEVAL_COMPLETED_AT = datetime(2026, 7, 23, 20, 0, 1, tzinfo=UTC)


def _resolve_roots() -> tuple[Path, Path, bool]:
    """Return (batch05_root, freeze_root, using_live_intake)."""
    if (LIVE_BATCH05_ROOT / "raw").is_dir():
        freeze_root = (
            LIVE_FREEZE_ROOT
            if LIVE_FREEZE_ROOT.is_dir()
            else SYNTHETIC_FREEZE_ROOT
        )
        return LIVE_BATCH05_ROOT, freeze_root, True
    return SYNTHETIC_BATCH05_ROOT, SYNTHETIC_FREEZE_ROOT, False


def _parse_forward_csv(batch05_root: Path, symbol: str) -> tuple[list[dict[str, str]], str]:
    stage2_path = STAGE2_FORWARD_ROOT / f"{symbol}-forward-outcome.csv"
    legacy_path = batch05_root / "raw" / f"{symbol}-frozen-forward-24h.csv"
    if stage2_path.exists():
        path = stage2_path
        source = "stage2_forward_outcome"
    else:
        path = legacy_path
        source = "frozen_forward_24h"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty forward window for {symbol}: {path}")
    return rows, source


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


def _write_evidence(symbol: str, observations: tuple) -> None:
    records: list[bytes] = []
    for item in observations:
        records.append(
            canonical_json_bytes({"record_type": "observation", "data": item.model_dump(mode="json")})
        )
    path = EVAL_OUT / f"{symbol.lower()}_boundary_evidence.jsonl"
    path.write_bytes(b"\n".join(records) + b"\n")


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


def _write_outcome(
    *,
    case_id: str,
    batch_case_id: str,
    symbol: str,
    boundary: datetime,
    reference: Decimal,
    maximum: Decimal,
    adverse: Decimal,
    limitations: tuple[str, ...],
    forward_bar_count: int,
    live: bool,
) -> None:
    completeness = (
        OutcomeCompleteness.COMPLETE
        if live and forward_bar_count >= 100
        else OutcomeCompleteness.PARTIAL
    )
    observation = RetrospectiveOutcomeObservation(
        case_id=case_id,
        symbol=symbol,
        detection_boundary=boundary,
        reference_price_policy="first_eligible_trade_bar_close_at_or_after_boundary.v1",
        reference_price=reference,
        horizon="24_HOURS",
        maximum_observed_move_percent=maximum,
        maximum_adverse_move_percent=adverse,
        completeness=completeness,
        supporting_observation_ids=(boundary_id_for(batch_case_id, symbol),),
        limitations=limitations,
    )
    path = RESEARCH_OUT / f"{symbol.lower()}_outcome_observation.json"
    path.write_bytes(serialize_research_model(observation))


def write_outputs() -> dict[str, object]:
    batch05_root, freeze_root, live = _resolve_roots()
    if not freeze_root.exists():
        raise SystemExit(
            "missing freeze artifacts; run phase3a_freeze generate-phase3a-freeze first"
        )
    anchors: dict[str, str] = {}
    meta: dict[str, object] = {
        "batch05_root": str(batch05_root),
        "freeze_root": str(freeze_root),
        "live_intake": live,
    }
    for symbol, case_id, batch_case_id in COHORT:
        evaluation_path = freeze_root / "results" / f"{batch_case_id}.json"
        if not evaluation_path.is_file():
            raise SystemExit(f"missing freeze result: {evaluation_path}")
        evaluation_bytes = evaluation_path.read_bytes()
        eval_name = f"{symbol.lower()}_boundary_evaluation.json"
        (EVAL_OUT / eval_name).write_bytes(evaluation_bytes)

        observations = _load_detection_bars(batch05_root, symbol)
        _write_evidence(symbol, observations)

        reference = _reference_price(batch05_root, symbol)
        maximum, adverse, forward_bars, forward_source = _outcome_moves(
            batch05_root, symbol, reference
        )
        limitations = _outcome_limitations(
            live=live,
            forward_bar_count=forward_bars,
            forward_source=forward_source,
        )
        _write_outcome(
            case_id=case_id,
            batch_case_id=batch_case_id,
            symbol=symbol,
            boundary=FROZEN_BOUNDARY,
            reference=reference,
            maximum=maximum,
            adverse=adverse,
            limitations=limitations,
            forward_bar_count=forward_bars,
            live=live,
        )
        anchors[eval_name] = json.loads(evaluation_bytes.decode())["deterministic_id"]
        meta[symbol] = {
            "detection_bar_count": len(observations),
            "forward_bar_count": forward_bars,
            "forward_source": forward_source,
            "reference_price": str(reference),
            "maximum_move_percent": str(maximum),
            "maximum_adverse_percent": str(adverse),
        }
    manifest = {
        "schema_version": "1.0.0",
        "boundary": FROZEN_BOUNDARY.isoformat().replace("+00:00", "Z"),
        "anchors": anchors,
        "provenance": meta,
    }
    (EVAL_OUT / "ibkr_cohort_phase_3a_anchors.json").write_bytes(canonical_json_bytes(manifest))
    return meta


if __name__ == "__main__":
    result = write_outputs()
    print(json.dumps(result, indent=2))
