"""Item 7 — lawful capture grid-point → pre-existing PRODUCTION ``ForecastV1`` binding.

Resolves governed contributor forecasts for ``CaptureLedgerCandidate`` rows.
Does not mint forecasts from quotes, fabricate probabilities, or register ledger
rows without a lawful PRODUCTION_RAW contributor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..contracts.forecast import ForecastV1
from ..outcomes.opend_capture_ledger import CaptureLedgerCandidate
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .readiness import is_lawful_production_raw_contributor, production_contributor_refusal_reasons

REFUSAL_NO_PRODUCTION_FORECAST_SOURCE = "NO_PRODUCTION_FORECAST_SOURCE"
REFUSAL_NO_LAWFUL_PRODUCTION_FORECAST = "NO_LAWFUL_PRODUCTION_FORECAST_FOR_CANDIDATE"
REFUSAL_AMBIGUOUS_PRODUCTION_FORECAST = "AMBIGUOUS_PRODUCTION_FORECAST_MATCH"

BINDING_ARTIFACT_KIND = "item7_capture_forecast_binding_v1"
REFUSAL_LEDGER_POLICY_UNSUPPORTED = "LEDGER_POLICY_UNSUPPORTED_TARGET"


@dataclass(frozen=True, slots=True)
class CaptureForecastBindingResult:
    candidate_id: str
    forecast_id: str | None
    refusal_reasons: tuple[str, ...] = ()
    forecast: ForecastV1 | None = None

    @property
    def bound(self) -> bool:
        return self.forecast_id is not None and not self.refusal_reasons

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_kind": BINDING_ARTIFACT_KIND,
            "bound": self.bound,
            "candidate_id": self.candidate_id,
            "forecast_id": self.forecast_id,
            "refusal_reasons": list(self.refusal_reasons),
        }


def _iter_repository_forecasts(repository: IntelligenceRepository) -> tuple[ForecastV1, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    bucket = stores.get("forecasts")
    if not isinstance(bucket, dict):
        return ()
    decode = getattr(repository, "_decode", None)
    if decode is None:
        return ()
    rows: list[ForecastV1] = []
    for body in bucket.values():
        forecast = decode(ForecastV1, body)
        if forecast is not None:
            rows.append(forecast)
    return tuple(sorted(rows, key=lambda row: str(row.forecast_id)))


def load_binding_eligible_production_contributors(
    *,
    repository: IntelligenceRepository,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
) -> tuple[ForecastV1, ...]:
    """Load lawful PRODUCTION_RAW contributors from operator paths and repository."""

    from ...strategy.path_a_forecast_producer import load_paper_demo_contributors
    from ...strategy.path_a_forecast_store import load_paper_demo_forecasts

    seen: dict[str, ForecastV1] = {}
    sources: list[Iterable[ForecastV1]] = []
    if contributor_path is not None and contributor_path.exists():
        sources.append(load_paper_demo_contributors(contributor_path))
    if forecast_path is not None and forecast_path.exists():
        sources.append(load_paper_demo_forecasts(forecast_path))
    sources.append(_iter_repository_forecasts(repository))

    for batch in sources:
        for forecast in batch:
            if not is_lawful_production_raw_contributor(forecast):
                continue
            seen[str(forecast.forecast_id)] = forecast
    return tuple(sorted(seen.values(), key=lambda row: str(row.forecast_id)))


def _instrument_matches(candidate: CaptureLedgerCandidate, forecast: ForecastV1) -> bool:
    bound = str(forecast.target.instrument_id or "").strip().upper()
    grid = str(candidate.instrument_id or "").strip().upper()
    if not bound or not grid:
        return False
    return bound == grid


def lookup_production_forecast_for_candidate(
    candidate: CaptureLedgerCandidate,
    *,
    contributors: Iterable[ForecastV1],
    expected_account_id: str | None = None,
    expected_mode: str | None = None,
) -> CaptureForecastBindingResult:
    """Pick the latest PIT-legal PRODUCTION_RAW contributor for a grid candidate."""

    pool = tuple(contributors)
    if not pool:
        return CaptureForecastBindingResult(
            candidate_id=candidate.candidate_id,
            forecast_id=None,
            refusal_reasons=(REFUSAL_NO_PRODUCTION_FORECAST_SOURCE,),
        )

    matches: list[ForecastV1] = []
    for forecast in pool:
        if not _instrument_matches(candidate, forecast):
            continue
        reasons = production_contributor_refusal_reasons(
            forecast,
            as_of_time_ns=candidate.decision_time_ns,
            expected_account_id=expected_account_id,
            expected_mode=expected_mode,
            expected_instrument_id=candidate.instrument_id,
        )
        if reasons:
            continue
        if forecast.decision_time_ns > candidate.decision_time_ns:
            continue
        matches.append(forecast)

    if not matches:
        return CaptureForecastBindingResult(
            candidate_id=candidate.candidate_id,
            forecast_id=None,
            refusal_reasons=(REFUSAL_NO_LAWFUL_PRODUCTION_FORECAST,),
        )

    best_time = max(row.decision_time_ns for row in matches)
    at_best = [row for row in matches if row.decision_time_ns == best_time]
    if len(at_best) > 1:
        ids = {str(row.forecast_id) for row in at_best}
        if len(ids) > 1:
            return CaptureForecastBindingResult(
                candidate_id=candidate.candidate_id,
                forecast_id=None,
                refusal_reasons=(REFUSAL_AMBIGUOUS_PRODUCTION_FORECAST,),
            )

    chosen = at_best[0]
    return CaptureForecastBindingResult(
        candidate_id=candidate.candidate_id,
        forecast_id=str(chosen.forecast_id),
        refusal_reasons=(),
        forecast=chosen,
    )


def production_forecast_ledger_refusal_reasons(forecast: ForecastV1) -> tuple[str, ...]:
    """Fail closed when BUILD 15 policy cannot register this forecast target."""

    from ..outcomes.policy import policy_for_forecast

    policy = policy_for_forecast(
        target_kind=str(forecast.target.target_kind),
        horizon_ns=int(forecast.horizon.duration_ns),
    )
    if policy is None:
        return (REFUSAL_LEDGER_POLICY_UNSUPPORTED,)
    return ()


def ensure_production_forecast_in_repository(
    repository: IntelligenceRepository,
    forecast: ForecastV1,
) -> RepositoryPutResult | None:
    """Persist a pre-existing contributor row when absent (no synthesis)."""

    if repository.get_forecast(str(forecast.forecast_id)) is not None:
        return RepositoryPutResult.ALREADY_PRESENT
    return repository.put_forecast(forecast)


def resolve_capture_forecast_bindings(
    candidates: Iterable[CaptureLedgerCandidate],
    *,
    repository: IntelligenceRepository,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    expected_account_id: str | None = None,
    expected_mode: str | None = None,
    persist_forecasts: bool = True,
) -> tuple[dict[str, str], tuple[CaptureForecastBindingResult, ...]]:
    """Build ``candidate_id`` → ``forecast_id`` bindings for materialization."""

    contributors = load_binding_eligible_production_contributors(
        repository=repository,
        contributor_path=contributor_path,
        forecast_path=forecast_path,
    )
    bindings: dict[str, str] = {}
    results: list[CaptureForecastBindingResult] = []
    for candidate in candidates:
        resolved = lookup_production_forecast_for_candidate(
            candidate,
            contributors=contributors,
            expected_account_id=expected_account_id,
            expected_mode=expected_mode,
        )
        results.append(resolved)
        if resolved.forecast is None or not resolved.bound:
            continue
        if persist_forecasts:
            ensure_production_forecast_in_repository(repository, resolved.forecast)
        bindings[candidate.candidate_id] = str(resolved.forecast_id)
    return bindings, tuple(results)


__all__ = [
    "BINDING_ARTIFACT_KIND",
    "CaptureForecastBindingResult",
    "REFUSAL_AMBIGUOUS_PRODUCTION_FORECAST",
    "REFUSAL_NO_LAWFUL_PRODUCTION_FORECAST",
    "REFUSAL_LEDGER_POLICY_UNSUPPORTED",
    "REFUSAL_NO_PRODUCTION_FORECAST_SOURCE",
    "production_forecast_ledger_refusal_reasons",
    "ensure_production_forecast_in_repository",
    "load_binding_eligible_production_contributors",
    "lookup_production_forecast_for_candidate",
    "resolve_capture_forecast_bindings",
]
