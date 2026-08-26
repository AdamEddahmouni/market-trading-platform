"""Build campaign observation inputs from persisted campaign evidence."""

from __future__ import annotations

from ..evidence01.types import ForwardObservationInputV1
from ..receipt import build_forward_prediction_receipt
from ..types import EvidenceClass
from ...contracts.forecast import ForecastV1, forecast_v1_from_dict
from ...contracts.prediction_ledger import PredictionLedgerEntryV1, prediction_ledger_entry_v1_from_dict
from ...persistence.repository import IntelligenceRepository
from .store import CampaignStore
from .types import CampaignEvidenceOrigin


_ORIGIN_TO_EVIDENCE_CLASS = {
    CampaignEvidenceOrigin.LIVE_FORWARD: EvidenceClass.ACTUAL_FORWARD,
    CampaignEvidenceOrigin.FIXTURE: EvidenceClass.REPLAY,
    CampaignEvidenceOrigin.REPLAY: EvidenceClass.REPLAY,
    CampaignEvidenceOrigin.SYNTHETIC: EvidenceClass.COUNTERFACTUAL,
}


def origin_qualifies_for_real_evidence(origin: CampaignEvidenceOrigin) -> bool:
    return origin == CampaignEvidenceOrigin.LIVE_FORWARD


def load_campaign_repository(store: CampaignStore) -> IntelligenceRepository:
    from ...persistence import InMemoryIntelligenceRepository

    repo = InMemoryIntelligenceRepository()
    seen_forecasts: set[str] = set()
    seen_ledgers: set[str] = set()
    for row in store.list_intelligence_records():
        record_type = row["record_type"]
        payload = row["payload"]
        if record_type == "forecast":
            forecast = forecast_v1_from_dict(payload)
            if forecast.forecast_id in seen_forecasts:
                continue
            seen_forecasts.add(forecast.forecast_id)
            repo.put_forecast(forecast)
        elif record_type == "prediction_ledger_entry":
            entry = prediction_ledger_entry_v1_from_dict(payload)
            if entry.ledger_entry_id in seen_ledgers:
                continue
            seen_ledgers.add(entry.ledger_entry_id)
            repo.put_prediction_ledger_entry(entry)
        elif record_type == "outcome":
            from ...contracts.outcome import outcome_v1_from_dict

            repo.put_outcome(outcome_v1_from_dict(payload))
    return repo


def build_observation_inputs(
    *,
    store: CampaignStore,
    repository: IntelligenceRepository,
    require_live_forward: bool = True,
) -> tuple[ForwardObservationInputV1, ...]:
    observations: list[ForwardObservationInputV1] = []
    for ref in store.list_observation_refs():
        if require_live_forward and not origin_qualifies_for_real_evidence(ref.evidence_origin):
            continue
        forecast = repository.get_forecast(ref.forecast_id)
        if forecast is None:
            continue
        ledger_entry = repository.get_prediction_ledger_entry(ref.ledger_entry_id)
        if ledger_entry is None:
            continue
        evidence_class = _ORIGIN_TO_EVIDENCE_CLASS[ref.evidence_origin]
        receipt = build_forward_prediction_receipt(
            forecast=forecast,
            ledger_entry=ledger_entry,
            qualification_run_ref=ref.campaign_id,
            recorded_at_ns=ref.decision_time_ns,
            evidence_class=evidence_class,
        )
        observations.append(
            ForwardObservationInputV1(
                receipt=receipt,
                forecast=forecast,
                ledger_entry=ledger_entry,
                quality_state=ref.quality_state,
                session_id=ref.session_id,
                provider_connected=ref.metadata.get("provider_connected", True),
            )
        )
    return tuple(observations)


def persist_forecast(store: CampaignStore, forecast: ForecastV1) -> None:
    from ...contracts.forecast import forecast_v1_to_dict

    store.append_intelligence_record("forecast", forecast_v1_to_dict(forecast))


def persist_ledger_entry(store: CampaignStore, entry: PredictionLedgerEntryV1) -> None:
    from ...contracts.prediction_ledger import prediction_ledger_entry_v1_to_dict

    store.append_intelligence_record("prediction_ledger_entry", prediction_ledger_entry_v1_to_dict(entry))


def persist_outcome(store: CampaignStore, outcome) -> None:
    from ...contracts.outcome import outcome_v1_to_dict

    store.append_intelligence_record("outcome", outcome_v1_to_dict(outcome))
