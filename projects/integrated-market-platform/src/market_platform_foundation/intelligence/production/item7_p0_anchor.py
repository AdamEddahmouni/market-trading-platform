"""Item 7 — lawful P0 (TRADE) anchor preflight for BUILD 15 ledger registration.

Connects capture ingestion (#212), forecast binding (#213), and settlement policy
(#214) to ``PredictionLedgerService.register_forecast``. SNAPSHOT_BBO envelopes
supply grid/tape context only; P0 requires a real TRADE observation already in the
repository (for example from ``US_EQUITY_TICKS`` capture lines). Never synthesizes
TRADE from ``last_price`` or quote midpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..contracts.event import EventV1
from ..contracts.forecast import ForecastV1
from ..outcomes.errors import OutcomeRegistrationError
from ..outcomes.observations import event_observation_kind
from ..outcomes.opend_capture_ledger import (
    CaptureLedgerMaterializationResult,
    materialize_capture_paths,
    materialize_opend_capture_jsonl,
)
from ..outcomes.policy import OutcomeSettlementPolicy, policy_for_forecast
from ..outcomes.types import UnlabelableReason
from ..persistence.repository import IntelligenceRepository
from .item7_capture_forecast_binding import production_forecast_ledger_refusal_reasons

ARTIFACT_KIND = "item7_p0_anchor_preflight_v1"

REFUSAL_FORECAST_SNAPSHOT_MISSING = "FORECAST_SNAPSHOT_MISSING"
REFUSAL_TARGET_INSTRUMENT_NOT_IN_SCOPE = "TARGET_INSTRUMENT_NOT_IN_SCOPE"
REFUSAL_P0_TRADE_MISSING = UnlabelableReason.NO_VALID_ANCHOR.value


@dataclass(frozen=True, slots=True)
class P0AnchorPreflightResult:
    forecast_id: str
    refusal_reasons: tuple[str, ...] = ()
    policy_id: str | None = None

    @property
    def anchor_ready(self) -> bool:
        return not self.refusal_reasons

    def to_dict(self) -> dict[str, object]:
        return {
            "anchor_ready": self.anchor_ready,
            "artifact_kind": ARTIFACT_KIND,
            "forecast_id": self.forecast_id,
            "policy_id": self.policy_id,
            "refusal_reasons": list(self.refusal_reasons),
        }


def _latest_pit_trade_event(
    repository: IntelligenceRepository,
    *,
    instrument_id: str,
    decision_time_ns: int,
) -> EventV1 | None:
    rows = repository.query_events_as_of(
        decision_time_ns,
        instrument_id=instrument_id,
        limit=10_000,
    )
    trades: list[EventV1] = []
    for event in rows:
        if event_observation_kind(event) != "TRADE":
            continue
        if event.event_time_ns > decision_time_ns:
            continue
        if event.available_time_ns > decision_time_ns:
            continue
        trades.append(event)
    if not trades:
        return None
    return max(trades, key=lambda row: (row.event_time_ns, row.available_time_ns, row.event_id))


def ensure_forecast_snapshot_trade_anchor(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
    *,
    decision_time_ns: int,
    instrument_id: str,
) -> tuple[str, ...]:
    """Require lawful snapshot row plus an ingested TRADE anchor (never synthesized)."""

    snapshot = repository.get_snapshot(forecast.snapshot_id)
    if snapshot is None:
        return (REFUSAL_FORECAST_SNAPSHOT_MISSING,)

    from ..snapshots.resolver import resolve_snapshot

    resolved = resolve_snapshot(snapshot, repository, strict=False)
    if any(event_observation_kind(event) == "TRADE" for event in resolved.events):
        return ()

    trade = _latest_pit_trade_event(
        repository,
        instrument_id=instrument_id,
        decision_time_ns=decision_time_ns,
    )
    if trade is None:
        return (REFUSAL_P0_TRADE_MISSING,)
    return ()


def p0_anchor_refusal_reasons(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
    *,
    policy: OutcomeSettlementPolicy | None = None,
) -> tuple[str, ...]:
    """Fail-closed P0 checks using the same anchor freeze path as ledger registration."""

    active_policy = policy or policy_for_forecast(
        target_kind=str(forecast.target.target_kind),
        horizon_ns=int(forecast.horizon.duration_ns),
    )
    if active_policy is None:
        return production_forecast_ledger_refusal_reasons(forecast)

    snapshot = repository.get_snapshot(forecast.snapshot_id)
    if snapshot is None:
        return (REFUSAL_FORECAST_SNAPSHOT_MISSING,)

    from ..outcomes.anchor import freeze_anchor_observation

    try:
        freeze_anchor_observation(forecast, repository, policy=active_policy)
    except OutcomeRegistrationError as exc:
        code = str(exc.code)
        if code == UnlabelableReason.NO_VALID_ANCHOR.value:
            return (REFUSAL_P0_TRADE_MISSING,)
        return (code,)
    return ()


def preflight_p0_anchor_for_forecast(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
) -> P0AnchorPreflightResult:
    policy = policy_for_forecast(
        target_kind=str(forecast.target.target_kind),
        horizon_ns=int(forecast.horizon.duration_ns),
    )
    reasons = p0_anchor_refusal_reasons(forecast, repository, policy=policy)
    return P0AnchorPreflightResult(
        forecast_id=str(forecast.forecast_id),
        refusal_reasons=reasons,
        policy_id=policy.policy_id if policy is not None else None,
    )


def materialize_item7_lawful_capture_ledger(
    capture_paths: Iterable[Path],
    repository: IntelligenceRepository,
    *,
    as_of_ns: int,
    session_start_ns: int,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    forecast_bindings: dict[str, str] | None = None,
    bind_expected_account_id: str | None = None,
    bind_expected_mode: str | None = None,
    register_ledger: bool = True,
    use_production_ingress: bool = False,
) -> CaptureLedgerMaterializationResult:
    """#212 capture JSONL → #213 bind → #214 policy → ledger when inputs are lawful."""

    paths = tuple(capture_paths)
    if len(paths) == 1:
        return materialize_opend_capture_jsonl(
            paths[0],
            repository,
            as_of_ns=as_of_ns,
            session_start_ns=session_start_ns,
            forecast_bindings=forecast_bindings,
            contributor_path=contributor_path,
            forecast_path=forecast_path,
            auto_bind_production_forecasts=True,
            bind_expected_account_id=bind_expected_account_id,
            bind_expected_mode=bind_expected_mode,
            register_ledger=register_ledger,
            use_production_ingress=use_production_ingress,
        )
    return materialize_capture_paths(
        paths,
        repository,
        as_of_ns=as_of_ns,
        session_start_ns=session_start_ns,
        forecast_bindings=forecast_bindings,
        contributor_path=contributor_path,
        forecast_path=forecast_path,
        auto_bind_production_forecasts=True,
        bind_expected_account_id=bind_expected_account_id,
        bind_expected_mode=bind_expected_mode,
        use_production_ingress=use_production_ingress,
    )


__all__ = [
    "ARTIFACT_KIND",
    "P0AnchorPreflightResult",
    "REFUSAL_FORECAST_SNAPSHOT_MISSING",
    "REFUSAL_P0_TRADE_MISSING",
    "REFUSAL_TARGET_INSTRUMENT_NOT_IN_SCOPE",
    "ensure_forecast_snapshot_trade_anchor",
    "materialize_item7_lawful_capture_ledger",
    "p0_anchor_refusal_reasons",
    "preflight_p0_anchor_for_forecast",
]
