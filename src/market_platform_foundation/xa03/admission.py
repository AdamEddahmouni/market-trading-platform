"""XA-03 admission bridge from existing CFTC positioning observations."""

from __future__ import annotations

from market_platform_foundation.cftc.contracts import InstitutionalPositioningObservation

from market_platform_foundation.xa02.contracts import (
    AdmissionEnvelope,
    PositioningPayload,
    SourceProvenance,
)
from market_platform_foundation.xa02.enums import (
    AdmissionStatus,
    ObservationPayloadKind,
    ReferenceSubjectType,
    RevisionClassification,
    SourceProvider,
)
from market_platform_foundation.xa02.envelope import eligible_at_decision_time_envelope, positioning_unit_label

from .catalog import is_admitted_market, lookup_admitted_market_by_code
from .errors import Xa03Error, Xa03ErrorCode
from .identity import derive_positioning_observation_id, market_report_id, revision_identity_material


_POSITION_UNIT = positioning_unit_label()



def build_cftc_provenance(obs: InstitutionalPositioningObservation, *, retrieved_time: str) -> SourceProvenance:
    return SourceProvenance(
        provider=SourceProvider.CFTC,
        series_id=obs.cftc_contract_market_code,
        api_version=obs.source_dataset,
        provenance_ref=obs.provenance_ref,
        retrieved_time=retrieved_time,
        observed_time=obs.observed_time,
        ingested_time=retrieved_time,
        source_publication_time=obs.publication_time,
        provider_first_observed_time=obs.observed_time,
        revision_number=0,
    )


def observation_event_time(obs: InstitutionalPositioningObservation) -> str:
    return obs.position_date[:10]


def observation_available_time(obs: InstitutionalPositioningObservation) -> str:
    return obs.available_time or obs.publication_time or ""


def validate_positioning_units() -> tuple[str, ...]:
    return ()


def admit_positioning_observation(
    obs: InstitutionalPositioningObservation,
    *,
    retrieved_time: str,
    revision_number: int = 0,
) -> AdmissionEnvelope:
    report_id = market_report_id(
        cftc_contract_market_code=obs.cftc_contract_market_code,
        report_family=obs.report_family.value,
        position_scope=obs.position_scope.value,
    )
    if not is_admitted_market(report_id):
        raise Xa03Error(
            Xa03ErrorCode.NOT_ADMITTED_MARKET,
            "market report is outside XA-03 admitted catalog",
            {"market_report_id": report_id},
        )
    admitted_def = lookup_admitted_market_by_code(obs.cftc_contract_market_code)
    if admitted_def is None:
        raise Xa03Error(
            Xa03ErrorCode.NOT_ADMITTED_MARKET,
            "CFTC market code not in admitted catalog",
            {"cftc_contract_market_code": obs.cftc_contract_market_code},
        )
    if admitted_def.report_family != obs.report_family or admitted_def.position_scope != obs.position_scope:
        raise Xa03Error(
            Xa03ErrorCode.NOT_ADMITTED_MARKET,
            "report family or scope does not match admitted catalog entry",
            {
                "market_report_id": report_id,
                "expected_report_family": admitted_def.report_family.value,
                "expected_position_scope": admitted_def.position_scope.value,
            },
        )
    unit_flags = validate_positioning_units()
    if unit_flags:
        raise Xa03Error(
            Xa03ErrorCode.UNSUPPORTED_UNIT,
            "unsupported positioning unit",
            {"market_report_id": report_id},
        )
    revision_identity = revision_identity_material(content_hash=obs.content_hash, revision_number=revision_number)
    revision_class = (
        RevisionClassification.VINTAGE_IDENTIFIED
        if revision_number > 0
        else RevisionClassification.ORIGINAL_OR_AS_REPORTED
        if obs.content_hash
        else RevisionClassification.REVISION_STATUS_UNKNOWN
    )
    provenance = build_cftc_provenance(obs, retrieved_time=retrieved_time)
    if revision_number > 0:
        provenance = SourceProvenance(
            provider=provenance.provider,
            series_id=provenance.series_id,
            api_version=provenance.api_version,
            provenance_ref=provenance.provenance_ref,
            retrieved_time=provenance.retrieved_time,
            observed_time=provenance.observed_time,
            ingested_time=provenance.ingested_time,
            source_publication_time=provenance.source_publication_time,
            provider_first_observed_time=provenance.provider_first_observed_time,
            realtime_start=provenance.realtime_start,
            realtime_end=provenance.realtime_end,
            vintage_date=provenance.vintage_date,
            revision_number=revision_number,
        )
    payload = PositioningPayload(
        market_report_id=report_id,
        provider_market_id=obs.market_id,
        cftc_contract_market_code=obs.cftc_contract_market_code,
        cftc_commodity_code=obs.cftc_commodity_code,
        market_and_exchange_names=obs.market_and_exchange_names,
        report_family=obs.report_family.value,
        position_scope=obs.position_scope.value,
        participant_category=obs.participant_category.value,
        position_date=obs.position_date,
        open_interest=obs.open_interest,
        long_positions=obs.long_positions,
        short_positions=obs.short_positions,
        spreading_positions=obs.spreading_positions,
        position_unit=_POSITION_UNIT,
        open_interest_unit=_POSITION_UNIT,
        source_dataset=obs.source_dataset,
        source_row_id=obs.source_row_id,
        content_hash=obs.content_hash,
    )
    available_time = observation_available_time(obs)
    if revision_number > 0:
        available_time = obs.observed_time or available_time
    return AdmissionEnvelope(
        observation_id=derive_positioning_observation_id(
            market_report_id_value=report_id,
            position_date=obs.position_date,
            participant_category=obs.participant_category.value,
            revision_identity=revision_identity,
        ),
        source_provider=SourceProvider.CFTC,
        source_subject_id=report_id,
        subject_type=ReferenceSubjectType.CFTC_MARKET_REPORT,
        event_time=observation_event_time(obs),
        available_time=available_time,
        retrieval_time=retrieved_time,
        revision_classification=revision_class,
        admission_status=AdmissionStatus.ADMITTED,
        provenance=provenance,
        payload_kind=ObservationPayloadKind.POSITIONING_STRUCTURED,
        positioning_payload=payload,
        quality_flags=tuple(dict.fromkeys((*obs.quality_flags, *unit_flags))),
    )


def eligible_at_decision_time(envelope: AdmissionEnvelope, decision_time: str) -> bool:
    return eligible_at_decision_time_envelope(envelope, decision_time)
