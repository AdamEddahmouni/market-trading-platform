"""Prediction ledger entry construction (BUILD 15)."""

from __future__ import annotations

from ..contracts.common import ContractKind, ContractReference, INTELLIGENCE_SCHEMA_VERSION
from ..contracts.forecast import ForecastV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from .anchor import freeze_anchor_observation
from .errors import OutcomeRegistrationError
from .identity import derive_ledger_entry_id
from .policy import OutcomeSettlementPolicy, policy_for_forecast
from .types import PriceObservationReceipt, SettlementMode, UnlabelableReason


def build_prediction_ledger_entry(
    forecast: ForecastV1,
    repository,
    *,
    policy: OutcomeSettlementPolicy | None = None,
    mode: SettlementMode = SettlementMode.ACTUAL_LIVE,
    scenario_id: str | None = None,
    registered_at_ns: int,
    reject_late_registration: bool = True,
) -> PredictionLedgerEntryV1:
    active_policy = policy or policy_for_forecast(
        target_kind=forecast.target.target_kind,
        horizon_ns=forecast.horizon.duration_ns,
    )
    if active_policy is None:
        raise OutcomeRegistrationError(
            UnlabelableReason.UNSUPPORTED_TARGET.value,
            details={"target_kind": forecast.target.target_kind},
        )
    if not active_policy.supports_horizon(forecast.horizon.duration_ns):
        raise OutcomeRegistrationError(
            UnlabelableReason.UNSUPPORTED_HORIZON.value,
            details={"horizon_ns": forecast.horizon.duration_ns},
        )
    target_time_ns = forecast.decision_time_ns + forecast.horizon.duration_ns
    if reject_late_registration and mode == SettlementMode.ACTUAL_LIVE and registered_at_ns > target_time_ns:
        raise OutcomeRegistrationError(
            "LATE_REGISTRATION",
            details={"registered_at_ns": registered_at_ns, "target_time_ns": target_time_ns},
        )
    anchor = freeze_anchor_observation(forecast, repository, policy=active_policy)
    window_start, window_end = active_policy.target_window(target_time_ns=target_time_ns)
    cutoff_ns = active_policy.availability_cutoff(target_window_end_ns=window_end)
    anchor_body = anchor.to_dict()
    ledger_entry_id = derive_ledger_entry_id(
        forecast_id=forecast.forecast_id,
        settlement_policy_identity=active_policy.policy_id,
        anchor_observation=anchor_body,
        target_time_ns=target_time_ns,
        target_window_start_ns=window_start,
        target_window_end_ns=window_end,
        availability_cutoff_ns=cutoff_ns,
        mode=mode,
        scenario_id=scenario_id,
    )
    return PredictionLedgerEntryV1(
        ledger_entry_id=ledger_entry_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        forecast_id=forecast.forecast_id,
        forecast_ref=ContractReference(kind=ContractKind.FORECAST.value, id=forecast.forecast_id),
        target=forecast.target,
        horizon_ns=forecast.horizon.duration_ns,
        scope=forecast.scope,
        instrument_id=forecast.target.instrument_id,
        forecast_decision_time_ns=forecast.decision_time_ns,
        anchor_observation=anchor_body,
        target_time_ns=target_time_ns,
        target_window_start_ns=window_start,
        target_window_end_ns=window_end,
        availability_cutoff_ns=cutoff_ns,
        settlement_policy_identity=active_policy.policy_id,
        observation_source_policy=active_policy.observation_source_policy(),
        mode=str(mode),
        registered_at_ns=registered_at_ns,
        scenario_id=scenario_id,
        lineage_refs=(ContractReference(kind=ContractKind.FORECAST.value, id=forecast.forecast_id),),
        metadata={
            "forecast_stage": forecast.metadata.get("forecast_stage"),
            "contributor_role": forecast.metadata.get("contributor_role"),
        },
    )


def anchor_receipt_from_entry(entry: PredictionLedgerEntryV1) -> PriceObservationReceipt:
    body = entry.anchor_observation
    return PriceObservationReceipt(
        event_id=str(body["event_id"]),
        price=float(body["price"]),
        event_time_ns=int(body["event_time_ns"]),
        available_time_ns=int(body["available_time_ns"]),
        observation_kind=str(body["observation_kind"]),
        provider_id=body.get("provider_id"),
        source_type=body.get("source_type"),
    )


__all__ = ["anchor_receipt_from_entry", "build_prediction_ledger_entry"]
