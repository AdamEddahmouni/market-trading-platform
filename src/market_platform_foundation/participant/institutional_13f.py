"""13F holdings parse, quarter-over-quarter diff, and PIT-safe position change actions — PI4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.identity import normalized_event_id
from ..contracts.participant import (
    ActionDirection,
    DirectionalClarity,
    IdentityConfidence,
    InstitutionalHoldingLine,
    ParticipantAction,
    ParticipantActionType,
    ParticipantQualityFlag,
    ParticipantType,
    THIRTEEN_F_LIMITATIONS,
    disclosure_quality_flags,
    infer_participant_type_from_form,
    participant_id_from_source,
)


from ..donor_patterns.edgar_whale import is_13f_form


def parse_13f_holdings(disclosure: dict[str, Any]) -> list[InstitutionalHoldingLine]:
    raw_holdings = disclosure.get("holdings")
    if not isinstance(raw_holdings, list):
        return []
    lines: list[InstitutionalHoldingLine] = []
    for item in raw_holdings:
        if not isinstance(item, dict):
            continue
        cusip = str(item.get("cusip", "")).strip()
        if not cusip:
            continue
        shares_raw = item.get("shares")
        try:
            shares = float(shares_raw) if shares_raw is not None else 0.0
        except (TypeError, ValueError):
            shares = 0.0
        value_raw = item.get("value_usd")
        value_usd: float | None
        try:
            value_usd = float(value_raw) if value_raw is not None else None
        except (TypeError, ValueError):
            value_usd = None
        symbol = item.get("symbol")
        put_call = item.get("put_call")
        lines.append(
            InstitutionalHoldingLine(
                cusip=cusip,
                issuer_name=str(item.get("issuer_name", "")),
                shares=shares,
                value_usd=value_usd,
                symbol=str(symbol).strip().upper() if symbol is not None else None,
                put_call=str(put_call) if put_call is not None else None,
            )
        )
    return lines


def _holding_key(line: InstitutionalHoldingLine) -> str:
    return line.cusip


def _parse_revision(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class QoQChange:
    participant_id: str
    display_name: str
    participant_type: ParticipantType
    instrument_id: str
    cusip: str
    action_type: ParticipantActionType
    direction: ActionDirection
    directional_clarity: DirectionalClarity
    quantity: float
    prior_shares: float | None
    current_shares: float | None
    quarter_end: str
    available_time: str
    event_time: str
    action_time: str
    source_record_id: str
    source_revision_id: str
    form_type: str
    identity_confidence: IdentityConfidence
    quality_flags: tuple[str, ...]
    provenance_ref: str


def _classify_change(
    *,
    prior_shares: float | None,
    current_shares: float | None,
) -> tuple[ParticipantActionType, ActionDirection, DirectionalClarity, float] | None:
    prior = 0.0 if prior_shares is None else prior_shares
    current = 0.0 if current_shares is None else current_shares
    if prior == current:
        return None
    if prior <= 0 and current > 0:
        return (
            ParticipantActionType.POSITION_INITIATED,
            ActionDirection.LONG,
            DirectionalClarity.PARTIAL,
            current,
        )
    if prior > 0 and current > prior:
        return (
            ParticipantActionType.POSITION_INCREASED,
            ActionDirection.LONG,
            DirectionalClarity.PARTIAL,
            current - prior,
        )
    if prior > 0 and 0 < current < prior:
        return (
            ParticipantActionType.POSITION_REDUCED,
            ActionDirection.SELL,
            DirectionalClarity.PARTIAL,
            prior - current,
        )
    if prior > 0 and current <= 0:
        return (
            ParticipantActionType.POSITION_EXITED,
            ActionDirection.SELL,
            DirectionalClarity.PARTIAL,
            prior,
        )
    return None


def _snapshot_record_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("participant_id", "")),
        str(row.get("quarter_end", "")),
        str(row.get("cusip", "")),
    )


def _dedupe_snapshots_by_revision(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in snapshots:
        key = _snapshot_record_key(row)
        existing = best.get(key)
        if existing is None or _parse_revision(row.get("source_revision_id")) >= _parse_revision(
            existing.get("source_revision_id")
        ):
            best[key] = row
    return sorted(
        best.values(),
        key=lambda row: (
            str(row.get("quarter_end", "")),
            int(row.get("available_time", 0)),
            str(row.get("action_id", "")),
        ),
    )


def diff_quarter_snapshots(
    prior_snapshots: list[dict[str, Any]],
    current_snapshots: list[dict[str, Any]],
) -> list[QoQChange]:
    """Compare two deduped quarter snapshot lists for one participant."""
    prior_by_cusip = {str(row["cusip"]): row for row in prior_snapshots}
    current_by_cusip = {str(row["cusip"]): row for row in current_snapshots}
    all_cusips = sorted(set(prior_by_cusip) | set(current_by_cusip))
    changes: list[QoQChange] = []
    for cusip in all_cusips:
        prior_row = prior_by_cusip.get(cusip)
        current_row = current_by_cusip.get(cusip)
        prior_shares = prior_row.get("shares") if prior_row else None
        current_shares = current_row.get("shares") if current_row else None
        if prior_row is None and current_row is None:
            continue
        base = current_row or prior_row
        assert base is not None
        classified = _classify_change(
            prior_shares=float(prior_shares) if prior_shares is not None else None,
            current_shares=float(current_shares) if current_shares is not None else None,
        )
        if classified is None:
            continue
        action_type, direction, clarity, quantity = classified
        changes.append(
            QoQChange(
                participant_id=str(base["participant_id"]),
                display_name=str(base.get("display_name", "")),
                participant_type=ParticipantType(str(base.get("participant_type", ParticipantType.UNKNOWN.value))),
                instrument_id=str(base["instrument_id"]),
                cusip=cusip,
                action_type=action_type,
                direction=direction,
                directional_clarity=clarity,
                quantity=quantity,
                prior_shares=float(prior_shares) if prior_shares is not None else None,
                current_shares=float(current_shares) if current_shares is not None else None,
                quarter_end=str(base.get("quarter_end", "")),
                available_time=str(base.get("available_time", "")),
                event_time=str(base.get("event_time", "")),
                action_time=str(base.get("action_time", "")),
                source_record_id=str(base.get("source_record_id", "")),
                source_revision_id=str(base.get("source_revision_id", "1")),
                form_type=str(base.get("form_type", "13F-HR")),
                identity_confidence=IdentityConfidence(
                    str(base.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
                ),
                quality_flags=tuple(base.get("quality_flags", [])),
                provenance_ref=str(base.get("provenance_ref", "")),
            )
        )
    return changes


def qoq_change_to_participant_action(change: QoQChange) -> ParticipantAction:
    action_id = normalized_event_id(
        provider_id="participant_intelligence",
        venue_id="SEC",
        publisher_id=change.display_name,
        channel_id=change.form_type,
        source_instance_id="13f_qoq",
        source_record_id=change.source_record_id,
        source_revision_id=change.source_revision_id,
        event_family="participant_action",
        subrecord_discriminator=f"{change.cusip}:{change.action_type.value}",
    )
    notional = None
    return ParticipantAction(
        action_id=action_id,
        participant_id=change.participant_id,
        participant_type=change.participant_type,
        instrument_id=change.instrument_id,
        asset_class="equity",
        action_type=change.action_type,
        direction=change.direction,
        directional_clarity=change.directional_clarity,
        quantity=change.quantity,
        notional=notional,
        transaction_price=None,
        estimated_basis=None,
        basis_confidence=None,
        action_time=change.action_time,
        event_time=change.event_time,
        available_time=change.available_time,
        ingested_time=None,
        source="regulatory_disclosure",
        source_record_id=change.source_record_id,
        identity_confidence=change.identity_confidence,
        insider_discretion=None,
        form_type=change.form_type,
        quality_flags=change.quality_flags,
        provenance_ref=change.provenance_ref,
    )


def build_13f_snapshot_payload(
    *,
    line: InstitutionalHoldingLine,
    disclosure: dict[str, Any],
    envelope: dict[str, Any],
    instrument_id: str,
    identity_participant_id: str,
    display_name: str,
    participant_type: ParticipantType,
    identity_confidence: IdentityConfidence,
) -> dict[str, Any]:
    form_type = str(disclosure.get("form_type", ""))
    quarter_end = str(disclosure.get("quarter_end", disclosure.get("accepted_at", "")))
    available_time = str(envelope.get("available_time", ""))
    action_time = quarter_end
    quality_flags = list(
        disclosure_quality_flags(
            form_type=form_type,
            transaction_code=None,
            available_time=available_time,
            action_time=action_time,
        )
    )
    quality_flags = [
        flag
        for flag in quality_flags
        if flag != ParticipantQualityFlag.OWNERSHIP_DELTA_UNAVAILABLE.value
    ]
    action_id = normalized_event_id(
        provider_id=str(envelope.get("provider_id", "regulatory_disclosure")),
        venue_id="SEC",
        publisher_id=display_name,
        channel_id=form_type,
        source_instance_id=str(envelope.get("source_instance_id", "edgar")),
        source_record_id=str(envelope.get("source_record_id", disclosure.get("accession_number", ""))),
        source_revision_id=str(envelope.get("source_revision_id", disclosure.get("source_revision_id", "1"))),
        event_family="participant_action",
        subrecord_discriminator=line.cusip,
    )
    return {
        "action_id": action_id,
        "participant_id": identity_participant_id,
        "participant_type": participant_type.value,
        "instrument_id": instrument_id,
        "asset_class": "equity",
        "action_type": ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value,
        "direction": ActionDirection.NEUTRAL.value,
        "directional_clarity": DirectionalClarity.AMBIGUOUS.value,
        "quantity": line.shares,
        "notional": line.value_usd,
        "transaction_price": None,
        "estimated_basis": None,
        "basis_confidence": None,
        "action_time": action_time,
        "event_time": str(envelope.get("event_time", action_time)),
        "available_time": available_time,
        "ingested_time": None,
        "source": "regulatory_disclosure",
        "source_record_id": str(envelope.get("source_record_id", "")),
        "source_revision_id": str(envelope.get("source_revision_id", disclosure.get("source_revision_id", "1"))),
        "identity_confidence": identity_confidence.value,
        "insider_discretion": None,
        "form_type": form_type,
        "quality_flags": sorted(set(quality_flags)),
        "provenance_ref": str(disclosure.get("source_url", "")),
        "display_name": display_name,
        "quarter_end": quarter_end,
        "cusip": line.cusip,
        "shares": line.shares,
        "issuer_name": line.issuer_name,
        "limitations": list(THIRTEEN_F_LIMITATIONS),
        "holding_context": {
            "quarter_end": quarter_end,
            "accession_number": str(disclosure.get("accession_number", "")),
            "cusip": line.cusip,
            "issuer_name": line.issuer_name,
            "symbol": line.symbol,
            "shares": line.shares,
            "value_usd": line.value_usd,
        },
    }


def stable_13f_participant_id(filer: str) -> str:
    return participant_id_from_source(
        source="regulatory_disclosure",
        source_record_id=filer,
        participant_label=filer,
    )


def _identity_from_13f_disclosure(disclosure: dict[str, Any]) -> tuple[str, str, ParticipantType, IdentityConfidence]:
    filer = str(disclosure.get("filer", "")).strip()
    form_type = str(disclosure.get("form_type", ""))
    participant_type = infer_participant_type_from_form(form_type)
    if filer:
        return filer, stable_13f_participant_id(filer), participant_type, IdentityConfidence.KNOWN_IDENTITY
    return "Unknown participant", participant_id_from_source(
        source="regulatory_disclosure",
        source_record_id=str(disclosure.get("accession_number", "unknown")),
        participant_label="unknown",
    ), participant_type, IdentityConfidence.UNKNOWN


def collect_13f_snapshot_rows(
    ledger_events: list[dict[str, Any]],
    *,
    instrument_id: str | None = None,
    prediction_cutoff: int,
    participant_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for envelope in ledger_events:
        if int(envelope.get("available_time", 0)) > prediction_cutoff:
            continue
        disclosure = envelope.get("disclosure_event")
        if not isinstance(disclosure, dict):
            continue
        form_type = str(disclosure.get("form_type", ""))
        if not is_13f_form(form_type):
            continue
        row_instrument = str(envelope.get("instrument_id", ""))
        if instrument_id is not None and row_instrument != instrument_id:
            continue
        display_name, participant_id, participant_type, identity_confidence = _identity_from_13f_disclosure(
            disclosure
        )
        if participant_ids is not None and participant_id not in participant_ids:
            continue
        holdings = parse_13f_holdings(disclosure)
        if not holdings:
            continue
        for line in holdings:
            rows.append(
                build_13f_snapshot_payload(
                    line=line,
                    disclosure=disclosure,
                    envelope=envelope,
                    instrument_id=row_instrument,
                    identity_participant_id=participant_id,
                    display_name=display_name,
                    participant_type=participant_type,
                    identity_confidence=identity_confidence,
                )
            )
    return _dedupe_snapshots_by_revision(rows)


def _participant_ids_for_instrument(
    ledger_events: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
) -> set[str]:
    participant_ids: set[str] = set()
    for row in collect_13f_snapshot_rows(
        ledger_events,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    ):
        participant_ids.add(str(row["participant_id"]))
    return participant_ids


def compute_13f_position_changes(
    snapshots: list[dict[str, Any]],
    *,
    instrument_id: str | None = None,
) -> list[dict[str, Any]]:
    """Derive QoQ position change action dicts from deduped snapshot rows."""
    by_participant: dict[str, list[dict[str, Any]]] = {}
    for row in snapshots:
        by_participant.setdefault(str(row["participant_id"]), []).append(row)

    change_rows: list[dict[str, Any]] = []
    for participant_rows in by_participant.values():
        by_quarter: dict[str, list[dict[str, Any]]] = {}
        for row in participant_rows:
            by_quarter.setdefault(str(row["quarter_end"]), []).append(row)
        quarter_ends = sorted(by_quarter)
        prior_quarter_rows: list[dict[str, Any]] | None = None
        for quarter_end in quarter_ends:
            current_rows = by_quarter[quarter_end]
            if prior_quarter_rows is not None:
                for change in diff_quarter_snapshots(prior_quarter_rows, current_rows):
                    action = qoq_change_to_participant_action(change)
                    payload = {
                        "action_id": action.action_id,
                        "participant_id": action.participant_id,
                        "participant_type": action.participant_type.value,
                        "instrument_id": action.instrument_id,
                        "asset_class": action.asset_class,
                        "action_type": action.action_type.value,
                        "direction": action.direction.value,
                        "directional_clarity": action.directional_clarity.value,
                        "quantity": action.quantity,
                        "notional": action.notional,
                        "transaction_price": action.transaction_price,
                        "estimated_basis": action.estimated_basis,
                        "basis_confidence": action.basis_confidence,
                        "action_time": action.action_time,
                        "event_time": action.event_time,
                        "available_time": action.available_time,
                        "ingested_time": action.ingested_time,
                        "source": action.source,
                        "source_record_id": action.source_record_id,
                        "identity_confidence": action.identity_confidence.value,
                        "insider_discretion": None,
                        "form_type": action.form_type,
                        "quality_flags": list(action.quality_flags),
                        "provenance_ref": action.provenance_ref,
                        "display_name": change.display_name,
                        "quarter_end": change.quarter_end,
                        "cusip": change.cusip,
                        "prior_shares": change.prior_shares,
                        "current_shares": change.current_shares,
                        "share_delta": change.quantity,
                        "limitations": list(THIRTEEN_F_LIMITATIONS),
                    }
                    change_rows.append(payload)
            else:
                for row in current_rows:
                    classified = _classify_change(
                        prior_shares=None,
                        current_shares=float(row.get("shares", 0)),
                    )
                    if classified is None:
                        continue
                    action_type, direction, clarity, quantity = classified
                    change = QoQChange(
                        participant_id=str(row["participant_id"]),
                        display_name=str(row.get("display_name", "")),
                        participant_type=ParticipantType(str(row.get("participant_type", ParticipantType.UNKNOWN.value))),
                        instrument_id=str(row["instrument_id"]),
                        cusip=str(row["cusip"]),
                        action_type=action_type,
                        direction=direction,
                        directional_clarity=clarity,
                        quantity=quantity,
                        prior_shares=None,
                        current_shares=float(row.get("shares", 0)),
                        quarter_end=str(row.get("quarter_end", "")),
                        available_time=str(row.get("available_time", "")),
                        event_time=str(row.get("event_time", "")),
                        action_time=str(row.get("action_time", "")),
                        source_record_id=str(row.get("source_record_id", "")),
                        source_revision_id=str(row.get("source_revision_id", "1")),
                        form_type=str(row.get("form_type", "13F-HR")),
                        identity_confidence=IdentityConfidence(
                            str(row.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
                        ),
                        quality_flags=tuple(row.get("quality_flags", [])),
                        provenance_ref=str(row.get("provenance_ref", "")),
                    )
                    action = qoq_change_to_participant_action(change)
                    change_rows.append(
                        {
                            "action_id": action.action_id,
                            "participant_id": action.participant_id,
                            "participant_type": action.participant_type.value,
                            "instrument_id": action.instrument_id,
                            "asset_class": action.asset_class,
                            "action_type": action.action_type.value,
                            "direction": action.direction.value,
                            "directional_clarity": action.directional_clarity.value,
                            "quantity": action.quantity,
                            "notional": action.notional,
                            "transaction_price": action.transaction_price,
                            "estimated_basis": action.estimated_basis,
                            "basis_confidence": action.basis_confidence,
                            "action_time": action.action_time,
                            "event_time": action.event_time,
                            "available_time": action.available_time,
                            "ingested_time": action.ingested_time,
                            "source": action.source,
                            "source_record_id": action.source_record_id,
                            "identity_confidence": action.identity_confidence.value,
                            "insider_discretion": None,
                            "form_type": action.form_type,
                            "quality_flags": list(action.quality_flags),
                            "provenance_ref": action.provenance_ref,
                            "display_name": change.display_name,
                            "quarter_end": change.quarter_end,
                            "cusip": change.cusip,
                            "prior_shares": change.prior_shares,
                            "current_shares": change.current_shares,
                            "share_delta": change.quantity,
                            "limitations": list(THIRTEEN_F_LIMITATIONS),
                        }
                    )
            prior_quarter_rows = current_rows
    if instrument_id is not None:
        change_rows = [row for row in change_rows if str(row.get("instrument_id", "")) == instrument_id]
    return change_rows


def query_13f_position_changes_from_ledger(
    ledger_events: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    participant_ids = _participant_ids_for_instrument(
        ledger_events,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not participant_ids:
        return []
    snapshots = collect_13f_snapshot_rows(
        ledger_events,
        prediction_cutoff=prediction_cutoff,
        participant_ids=participant_ids,
    )
    return compute_13f_position_changes(snapshots, instrument_id=instrument_id)


__all__ = [
    "QoQChange",
    "build_13f_snapshot_payload",
    "collect_13f_snapshot_rows",
    "compute_13f_position_changes",
    "diff_quarter_snapshots",
    "is_13f_form",
    "parse_13f_holdings",
    "qoq_change_to_participant_action",
    "query_13f_position_changes_from_ledger",
    "stable_13f_participant_id",
]