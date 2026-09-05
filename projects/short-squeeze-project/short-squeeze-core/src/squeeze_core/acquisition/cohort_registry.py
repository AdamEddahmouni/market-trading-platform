"""Cohort case registry with per-case detection boundaries.

The Jul-18 frozen IBKR cohort shares one boundary instant. Phase 3F Batch 05 external
discovery uses a separate Finviz-export boundary (Aug 17). Pipelines select a cohort
track explicitly rather than mixing boundaries inside ``FROZEN_COHORT``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

CohortTrack = Literal["frozen", "batch3f05", "all"]

REPO_ROOT = Path(__file__).resolve().parents[3]
BATCH3F05_DISCOVERY_PATH = (
    REPO_ROOT
    / "intake"
    / "batches"
    / "phase-3f-cohort-expansion-05-external"
    / "normalized"
    / "batch3f05_external_discovery_rows.json"
)


@dataclass(frozen=True)
class CohortCase:
    symbol: str
    case_id: str
    boundary: datetime


def _parse_observed_at(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def frozen_cohort_cases() -> tuple[CohortCase, ...]:
    from .operation_readiness.evidence_inputs import FROZEN_BOUNDARY, FROZEN_COHORT

    return tuple(
        CohortCase(symbol=symbol, case_id=case_id, boundary=FROZEN_BOUNDARY)
        for symbol, case_id in FROZEN_COHORT
    )


def batch3f05_cohort_cases(
    discovery_path: Path | None = None,
) -> tuple[CohortCase, ...]:
    """Load Batch 05 external symbols and shared export boundary from discovery JSON."""
    path = discovery_path or BATCH3F05_DISCOVERY_PATH
    if not path.is_file():
        return ()
    import json

    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("rows") or []
    if not rows:
        raw = document.get("raw_source", {}).get("capture_timestamp")
        if not raw:
            return ()
        boundary = _parse_observed_at(str(raw))
    else:
        boundary = _parse_observed_at(str(rows[0]["observed_at"]))
    date_suffix = boundary.strftime("%Y%m%d")
    cases: list[CohortCase] = []
    for row in rows:
        symbol = str(row.get("ticker", "")).strip().upper()
        if not symbol:
            continue
        case_id = f"BATCH3F05_{symbol}_{date_suffix}"
        cases.append(CohortCase(symbol=symbol, case_id=case_id, boundary=boundary))
    return tuple(cases)


def resolve_cohort_cases(
    track: CohortTrack,
    *,
    discovery_path: Path | None = None,
) -> tuple[CohortCase, ...]:
    if track == "frozen":
        return frozen_cohort_cases()
    if track == "batch3f05":
        return batch3f05_cohort_cases(discovery_path)
    frozen = frozen_cohort_cases()
    external = batch3f05_cohort_cases(discovery_path)
    return frozen + external


def cohort_cases_as_symbol_case_pairs(
    cases: tuple[CohortCase, ...],
) -> tuple[tuple[str, str], ...]:
    return tuple((case.symbol, case.case_id) for case in cases)


def boundary_map(cases: tuple[CohortCase, ...]) -> dict[str, datetime]:
    return {case.symbol: case.boundary for case in cases}


def cohort_boundary_descriptor(cases: tuple[CohortCase, ...]) -> str:
    boundaries = {case.boundary for case in cases}
    if len(boundaries) == 1:
        only = next(iter(boundaries))
        return f"SHARED_BOUNDARY_INSTANT_{only.isoformat().replace('+00:00', 'Z')}"
    return "HETEROGENOUS_BOUNDARY_COHORT_V1"


__all__ = [
    "BATCH3F05_DISCOVERY_PATH",
    "CohortCase",
    "CohortTrack",
    "batch3f05_cohort_cases",
    "boundary_map",
    "cohort_boundary_descriptor",
    "cohort_cases_as_symbol_case_pairs",
    "frozen_cohort_cases",
    "resolve_cohort_cases",
]
