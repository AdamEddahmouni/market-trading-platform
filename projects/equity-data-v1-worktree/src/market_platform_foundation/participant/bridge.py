"""Bridge whale ledger disclosure envelopes to Participant Intelligence contracts.

Preserves point-in-time semantics: copyability uses available_time, not action_time.
Does not invent participant identity beyond what the source supports.
"""

from __future__ import annotations

from typing import Any

from ..contracts.identity import normalized_event_id
from ..contracts.participant import (
    ActionDirection,
    DirectionalClarity,
    IdentityConfidence,
    InsiderDiscretion,
    ParticipantAction,
    ParticipantActionType,
    ParticipantHorizon,
    ParticipantIdentity,
    ParticipantMechanism,
    ParticipantQualityFlag,
    ParticipantResearchClassification,
    ParticipantResolutionMethod,
    ParticipantType,
    disclosure_quality_flags,
    infer_action_from_disclosure,
    infer_participant_type_from_form,
    participant_action_to_dict,
    participant_id_from_source,
    participant_identity_to_dict,
)
from .institutional_13f import (
    collect_13f_snapshot_rows,
    is_13f_form,
    query_13f_position_changes_from_ledger,
)


def disclosure_envelope_to_participant_identity(
    disclosure: dict[str, Any],
    *,
    source: str = "regulatory_disclosure",
) -> ParticipantIdentity:
    filer = str(disclosure.get("filer", "")).strip()
    form_type = str(disclosure.get("form_type", ""))
    accession = str(disclosure.get("accession_number", disclosure.get("source_record_id", "")))
    accepted_at = str(disclosure.get("accepted_at", ""))
    participant_type = infer_participant_type_from_form(form_type)
    if filer:
        identity_confidence = IdentityConfidence.KNOWN_IDENTITY
        resolution_method = ParticipantResolutionMethod.REGULATORY_FILING_NAMED
    else:
        identity_confidence = IdentityConfidence.UNKNOWN
        resolution_method = ParticipantResolutionMethod.UNRESOLVED
    quality_flags: list[str] = []
    if identity_confidence == IdentityConfidence.UNKNOWN:
        quality_flags.append(ParticipantQualityFlag.PARTICIPANT_UNKNOWN.value)
        quality_flags.append(ParticipantQualityFlag.IDENTITY_LOW_CONFIDENCE.value)
    return ParticipantIdentity(
        participant_id=participant_id_from_source(
            source=source,
            source_record_id=accession,
            participant_label=filer or "unknown",
        ),
        display_name=filer or "Unknown participant",
        participant_type=participant_type,
        identity_confidence=identity_confidence,
        resolution_method=resolution_method,
        source=source,
        label_available_time=accepted_at or None,
        quality_flags=tuple(quality_flags),
    )


def _default_horizon_for_form(form_type: str) -> ParticipantHorizon:
    normalized = form_type.upper().replace("/A", "")
    if normalized == "4":
        return ParticipantHorizon.MONTHS
    if normalized in {"13D", "13G"}:
        return ParticipantHorizon.YEARS
    if normalized.startswith("13F"):
        return ParticipantHorizon.MONTHS
    return ParticipantHorizon.UNKNOWN


def _default_classification_for_action(
    action_type: ParticipantActionType,
) -> ParticipantResearchClassification:
    if action_type == ParticipantActionType.OPEN_MARKET_BUY:
        return ParticipantResearchClassification.INSUFFICIENT_INFORMATION
    if action_type in {
        ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT,
        ParticipantActionType.PUBLIC_STATEMENT,
        ParticipantActionType.POSITION_INITIATED,
        ParticipantActionType.POSITION_INCREASED,
        ParticipantActionType.POSITION_REDUCED,
        ParticipantActionType.POSITION_EXITED,
    }:
        return ParticipantResearchClassification.INFORMATIONAL_CONTEXT_ONLY
    if action_type in {
        ParticipantActionType.INSIDER_TAX_WITHHOLDING,
        ParticipantActionType.INSIDER_AWARD_GRANT,
        ParticipantActionType.INSIDER_GIFT,
    }:
        return ParticipantResearchClassification.PASSIVE_FLOW_LIKELY
    if action_type == ParticipantActionType.ACTIVIST_STAKE_INITIATED:
        return ParticipantResearchClassification.STRATEGIC_ALIGNMENT_CANDIDATE
    return ParticipantResearchClassification.INSUFFICIENT_INFORMATION


def _parse_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _insider_discretion_from_disclosure(
    *,
    form_type: str,
    action_type: ParticipantActionType,
    disclosure: dict[str, Any],
) -> InsiderDiscretion | None:
    if not form_type.upper().startswith("4"):
        return None
    if disclosure.get("is_10b5_1") is True:
        return InsiderDiscretion.PLAN_10B5_1
    if action_type == ParticipantActionType.OPEN_MARKET_BUY:
        return InsiderDiscretion.DISCRETIONARY
    if action_type in {
        ParticipantActionType.INSIDER_AWARD_GRANT,
        ParticipantActionType.INSIDER_TAX_WITHHOLDING,
    }:
        return InsiderDiscretion.COMPENSATION
    return InsiderDiscretion.UNKNOWN


def _activist_context_from_disclosure(disclosure: dict[str, Any]) -> dict[str, Any] | None:
    form_type = str(disclosure.get("form_type", "")).upper().replace("/A", "")
    if form_type not in {"13D", "13G"}:
        return None
    context: dict[str, Any] = {}
    stake = _parse_optional_float(disclosure.get("stake_percent"))
    if stake is not None:
        context["stake_percent"] = stake
    if disclosure.get("campaign_objective") is not None:
        context["campaign_objective"] = str(disclosure.get("campaign_objective"))
    if disclosure.get("is_passive") is not None:
        context["is_passive"] = bool(disclosure.get("is_passive"))
    return context or None


def _transaction_fields_from_disclosure(disclosure: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    quantity = _parse_optional_float(disclosure.get("shares"))
    transaction_price = _parse_optional_float(disclosure.get("price_per_share"))
    notional = None
    if quantity is not None and transaction_price is not None:
        notional = quantity * transaction_price
    return quantity, transaction_price, notional


def disclosure_envelope_to_participant_action(
    envelope: dict[str, Any],
    *,
    instrument_id: str,
    asset_class: str = "equity",
) -> ParticipantAction | None:
    disclosure = envelope.get("disclosure_event")
    if not isinstance(disclosure, dict):
        return None
    identity = disclosure_envelope_to_participant_identity(disclosure)
    form_type = str(disclosure.get("form_type", ""))
    event_type = str(disclosure.get("event_type", ""))
    transaction_code = disclosure.get("transaction_code")
    action_type, direction, directional_clarity = infer_action_from_disclosure(
        form_type=form_type,
        event_type=event_type,
        transaction_code=str(transaction_code) if transaction_code is not None else None,
    )
    action_time = str(
        disclosure.get("transaction_date", disclosure.get("accepted_at", envelope.get("event_time", "")))
    )
    available_time = str(envelope.get("available_time", action_time))
    event_time = str(envelope.get("event_time", action_time))
    quality_flags = list(
        disclosure_quality_flags(
            form_type=form_type,
            transaction_code=str(transaction_code) if transaction_code is not None else None,
            available_time=available_time,
            action_time=action_time,
        )
    )
    quality_flags.extend(identity.quality_flags)
    insider_discretion = _insider_discretion_from_disclosure(
        form_type=form_type,
        action_type=action_type,
        disclosure=disclosure,
    )
    quantity, transaction_price, notional = _transaction_fields_from_disclosure(disclosure)
    if disclosure.get("shares_owned_following") is not None:
        quality_flags = [
            flag
            for flag in quality_flags
            if flag != ParticipantQualityFlag.OWNERSHIP_DELTA_UNAVAILABLE.value
        ]
    action_id = normalized_event_id(
        provider_id=str(envelope.get("provider_id", "regulatory_disclosure")),
        venue_id="SEC",
        publisher_id=str(disclosure.get("filer", "unknown")),
        channel_id=form_type,
        source_instance_id=str(envelope.get("source_instance_id", "edgar")),
        source_record_id=str(envelope.get("source_record_id", disclosure.get("accession_number", ""))),
        source_revision_id=str(envelope.get("source_revision_id", disclosure.get("source_revision_id", "1"))),
        event_family="participant_action",
        subrecord_discriminator=str(transaction_code or ""),
    )
    return ParticipantAction(
        action_id=action_id,
        participant_id=identity.participant_id,
        participant_type=identity.participant_type,
        instrument_id=instrument_id,
        asset_class=asset_class,
        action_type=action_type,
        direction=direction,
        directional_clarity=directional_clarity,
        quantity=quantity,
        notional=notional,
        transaction_price=transaction_price,
        estimated_basis=transaction_price,
        basis_confidence=1.0 if transaction_price is not None else None,
        action_time=action_time,
        event_time=event_time,
        available_time=available_time,
        ingested_time=None,
        source="regulatory_disclosure",
        source_record_id=str(envelope.get("source_record_id", "")),
        identity_confidence=identity.identity_confidence,
        insider_discretion=insider_discretion,
        form_type=form_type,
        quality_flags=tuple(sorted(set(quality_flags))),
        provenance_ref=str(disclosure.get("source_url", "")),
    )


def _enrich_action_payload(
    payload: dict[str, Any],
    *,
    disclosure: dict[str, Any],
    action: ParticipantAction,
) -> dict[str, Any]:
    activist_context = _activist_context_from_disclosure(disclosure)
    if activist_context is not None:
        payload["activist_context"] = activist_context
    shares_owned = _parse_optional_float(disclosure.get("shares_owned_following"))
    if shares_owned is not None:
        payload["shares_owned_following"] = shares_owned
    if disclosure.get("transaction_date") is not None:
        payload["transaction_date"] = str(disclosure.get("transaction_date"))
    if disclosure.get("is_10b5_1") is not None:
        payload["is_10b5_1"] = bool(disclosure.get("is_10b5_1"))
    payload["display_name"] = str(disclosure.get("filer", ""))
    return payload


def query_participant_actions_from_ledger(
    ledger_events: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
    asset_class: str = "equity",
) -> list[dict[str, Any]]:
    """Return participant actions visible at prediction_cutoff (PIT-safe)."""
    rows: list[dict[str, Any]] = []
    for envelope in ledger_events:
        if str(envelope.get("instrument_id", "")) != instrument_id:
            continue
        if int(envelope.get("available_time", 0)) > prediction_cutoff:
            continue
        disclosure = envelope.get("disclosure_event")
        if not isinstance(disclosure, dict):
            continue
        form_type = str(disclosure.get("form_type", ""))
        if is_13f_form(form_type) and isinstance(disclosure.get("holdings"), list):
            continue
        action = disclosure_envelope_to_participant_action(
            envelope,
            instrument_id=instrument_id,
            asset_class=asset_class,
        )
        if action is None:
            continue
        payload = participant_action_to_dict(action)
        payload["participant_identity"] = participant_identity_to_dict(
            disclosure_envelope_to_participant_identity(disclosure)
        )
        payload["estimated_horizon"] = _default_horizon_for_form(form_type).value
        payload["research_classification"] = _default_classification_for_action(
            action.action_type
        ).value
        payload["primary_mechanism"] = ParticipantMechanism.UNKNOWN.value
        rows.append(_enrich_action_payload(payload, disclosure=disclosure, action=action))

    thirteen_f_snapshots = collect_13f_snapshot_rows(
        ledger_events,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    for snapshot in thirteen_f_snapshots:
        snapshot["participant_identity"] = participant_identity_to_dict(
            disclosure_envelope_to_participant_identity(
                {
                    "filer": snapshot.get("display_name", ""),
                    "form_type": snapshot.get("form_type", "13F-HR"),
                    "accession_number": snapshot.get("source_record_id", ""),
                    "accepted_at": snapshot.get("available_time", ""),
                }
            )
        )
        snapshot["estimated_horizon"] = _default_horizon_for_form(
            str(snapshot.get("form_type", "13F-HR"))
        ).value
        snapshot["research_classification"] = _default_classification_for_action(
            ParticipantActionType(str(snapshot.get("action_type", "")))
        ).value
        snapshot["primary_mechanism"] = ParticipantMechanism.PORTFOLIO_ALLOCATION.value
        rows.append(snapshot)

    position_changes = query_13f_position_changes_from_ledger(
        ledger_events,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    for change in position_changes:
        change["participant_identity"] = participant_identity_to_dict(
            disclosure_envelope_to_participant_identity(
                {
                    "filer": change.get("display_name", ""),
                    "form_type": change.get("form_type", "13F-HR"),
                    "accession_number": change.get("source_record_id", ""),
                    "accepted_at": change.get("available_time", ""),
                }
            )
        )
        change["estimated_horizon"] = _default_horizon_for_form(
            str(change.get("form_type", "13F-HR"))
        ).value
        change["research_classification"] = _default_classification_for_action(
            ParticipantActionType(str(change.get("action_type", "")))
        ).value
        change["primary_mechanism"] = ParticipantMechanism.PORTFOLIO_ALLOCATION.value
        rows.append(change)

    rows.sort(key=lambda row: (row["available_time"], row["action_id"]))
    return rows
