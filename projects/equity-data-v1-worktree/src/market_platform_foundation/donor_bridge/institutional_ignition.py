"""Institutional evidence supplements for squeeze workspace ignition cards."""

from __future__ import annotations

from typing import Any

from ..providers.projections import (
    build_workspace_disclosure_payload,
    build_workspace_order_book_payload,
    disclosure_available,
    options_available,
    order_book_available,
)
from ..providers.projections import build_workspace_options_payload
from .lending_adapter import build_lending_snapshot_from_donor_detail

_DONOR_SQUEEZE_UNAVAILABLE = "Donor squeeze evidence not available for this symbol"
_OPTIONS_FROZEN_UNAVAILABLE = "Options flow not included in sanitized frozen aggregate"
_BORROW_NOT_ENTITLED = "Borrow fee/availability not on admitted institutional fixtures"
_DEPTH_NOT_ENTITLED = "Order-book depth not entitled for this symbol at replay cutoff"


def _unavailable_card(label: str, detail: str) -> dict[str, Any]:
    return {
        "label": label,
        "state": "UNAVAILABLE",
        "detail": detail,
        "epistemic_class": "OBSERVED",
    }


def build_institutional_borrow_card(
    symbol: str,
    *,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None = None,
    donor_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol_upper = symbol.strip().upper()
    lending_snapshot = build_lending_snapshot_from_donor_detail(donor_detail)
    if lending_snapshot:
        fee_rate = lending_snapshot.get("fee_rate")
        shares_available = lending_snapshot.get("shares_available")
        detail_parts: list[str] = []
        if fee_rate is not None:
            detail_parts.append(f"IBKR borrow fee {fee_rate}%")
        if shares_available is not None:
            detail_parts.append(f"shortable shares {shares_available:,}")
        if lending_snapshot.get("utilization_rate") is None:
            detail_parts.append("utilization UNAVAILABLE (provider omitted)")
        velocity = lending_snapshot.get("borrow_utilization_velocity")
        if velocity is not None:
            detail_parts.append(f"fee velocity {velocity:+.2f}pp")
        return {
            "label": "Borrow",
            "state": "ADMITTED",
            "detail": " · ".join(detail_parts) if detail_parts else "IBKR lending snapshot",
            "epistemic_class": "OBSERVED",
            "explain_ref": f"explain:squeeze:{symbol_upper}",
            "source": str(lending_snapshot.get("provenance_ref", "IBKR")),
        }

    if prediction_cutoff is None:
        return _unavailable_card("Borrow", "Borrow institutional cross-ref requires replay context")
    if not disclosure_available(instrument_id=symbol_upper, prediction_cutoff=prediction_cutoff):
        return _unavailable_card("Borrow", _BORROW_NOT_ENTITLED)

    payload = build_workspace_disclosure_payload(
        symbol_upper,
        as_of_context=as_of_context or {},
        prediction_cutoff=prediction_cutoff,
    )
    if not payload.get("available"):
        return _unavailable_card(
            "Borrow",
            str(payload.get("reason", _BORROW_NOT_ENTITLED)),
        )

    summary = payload.get("participant_summary", {})
    if not isinstance(summary, dict):
        summary = {}
    discretionary = int(summary.get("discretionary_buy_count", 0))
    activist = int(summary.get("activist_disclosure_count", 0))
    event_count = int(payload.get("event_count", 0))
    detail_parts: list[str] = []
    if discretionary:
        detail_parts.append(f"{discretionary} discretionary insider buy(s)")
    if activist:
        detail_parts.append(f"{activist} activist disclosure(s)")
    skill_summary = summary.get("participant_skill")
    if isinstance(skill_summary, dict) and skill_summary.get("skill_available"):
        elevated = int(skill_summary.get("elevated_participant_count", 0))
        below = int(skill_summary.get("below_baseline_participant_count", 0))
        if elevated:
            detail_parts.append(f"{elevated} participant(s) elevated buy_skill")
        if below:
            detail_parts.append(f"{below} participant(s) below baseline buy_skill")
    if not detail_parts:
        detail_parts.append(f"{event_count} SEC filing(s) on admitted ledger")
    detail_parts.append("borrow fee/availability not on fixture")
    return {
        "label": "Borrow",
        "state": "PARTIAL",
        "detail": " — ".join(detail_parts),
        "epistemic_class": "OBSERVED",
        "explain_ref": f"explain:disclosure:{symbol_upper}",
        "source": "ADMITTED-DISCLOSURE-BIYA-001",
    }


def build_institutional_depth_card(
    symbol: str,
    *,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol_upper = symbol.strip().upper()
    if prediction_cutoff is None:
        return _unavailable_card("Depth", "Depth institutional cross-ref requires replay context")
    if not order_book_available(instrument_id=symbol_upper, prediction_cutoff=prediction_cutoff):
        return _unavailable_card("Depth", _DEPTH_NOT_ENTITLED)

    payload = build_workspace_order_book_payload(
        symbol_upper,
        as_of_context=as_of_context or {},
        prediction_cutoff=prediction_cutoff,
    )
    if not payload.get("available"):
        return _unavailable_card(
            "Depth",
            str(payload.get("reason", _DEPTH_NOT_ENTITLED)),
        )

    snapshot_count = int(payload.get("snapshot_count", 0))
    imbalance = payload.get("latest_imbalance_ratio")
    detail_parts = [f"{snapshot_count} admitted depth snapshot(s)"]
    if imbalance is not None:
        detail_parts.append(f"imbalance {imbalance}")
    return {
        "label": "Depth",
        "state": "ADMITTED",
        "detail": " · ".join(detail_parts),
        "epistemic_class": "OBSERVED",
        "explain_ref": f"explain:order-book:{symbol_upper}",
        "source": "ADMITTED-ORDER-BOOK-NVDA-001",
    }


def build_institutional_options_card(
    symbol: str,
    *,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol_upper = symbol.strip().upper()
    if prediction_cutoff is None:
        return _unavailable_card(
            "Options",
            "Options institutional cross-ref requires replay context",
        )
    if not options_available(instrument_id=symbol_upper, prediction_cutoff=prediction_cutoff):
        return _unavailable_card(
            "Options",
            "No entitled options source for this symbol at replay cutoff",
        )

    payload = build_workspace_options_payload(
        symbol_upper,
        as_of_context=as_of_context or {},
        prediction_cutoff=prediction_cutoff,
    )
    if not payload.get("available"):
        return _unavailable_card(
            "Options",
            str(payload.get("reason", "No PIT-eligible options events at replay cutoff")),
        )

    activities = payload.get("activities", [])
    if not isinstance(activities, list):
        activities = []
    elevated = sum(
        1
        for row in activities
        if isinstance(row, dict) and float(row.get("volume_oi_ratio") or 0) >= 2.0
    )
    ambiguous = sum(
        1
        for row in activities
        if isinstance(row, dict) and str(row.get("direction_label", "")) == "ambiguous"
    )
    activity_count = int(payload.get("activity_count", len(activities)))
    detail_parts = [f"{activity_count} admitted activities"]
    if elevated:
        detail_parts.append(f"{elevated} elevated vol/OI")
    if ambiguous:
        detail_parts.append(f"{ambiguous} direction ambiguous")

    return {
        "label": "Options",
        "state": "ADMITTED",
        "detail": " · ".join(detail_parts),
        "epistemic_class": "OBSERVED",
        "explain_ref": f"explain:options:{symbol_upper}",
        "source": "ADMITTED-OPTIONS-BIYA-001",
    }


def build_supplemental_ignition_evidence(
    symbol: str,
    *,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ignition cards when donor squeeze evidence is unavailable but institutional refs may exist."""
    return [
        _unavailable_card("SI / Float", _DONOR_SQUEEZE_UNAVAILABLE),
        build_institutional_borrow_card(
            symbol,
            prediction_cutoff=prediction_cutoff,
            as_of_context=as_of_context,
        ),
        build_institutional_options_card(
            symbol,
            prediction_cutoff=prediction_cutoff,
            as_of_context=as_of_context,
        ),
        build_institutional_depth_card(
            symbol,
            prediction_cutoff=prediction_cutoff,
            as_of_context=as_of_context,
        ),
    ]


def _replace_card(cards: list[dict[str, Any]], label: str, replacement: dict[str, Any]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    replaced = False
    for card in cards:
        if card.get("label") == label:
            merged.append(replacement)
            replaced = True
        else:
            merged.append(card)
    if not replaced:
        merged.append(replacement)
    return merged


def merge_institutional_ignition_cards(
    cards: list[dict[str, Any]],
    *,
    symbol: str,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None = None,
    frozen_aggregate_only: bool = False,
    donor_detail: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Merge institutional borrow, options, and depth cards when replay context exists."""
    if prediction_cutoff is None and frozen_aggregate_only:
        return cards

    merged = cards
    if prediction_cutoff is not None:
        borrow = build_institutional_borrow_card(
            symbol,
            prediction_cutoff=prediction_cutoff,
            as_of_context=as_of_context,
            donor_detail=donor_detail,
        )
        if borrow.get("state") != "UNAVAILABLE" or not any(
            card.get("label") == "Borrow" and card.get("state") != "UNAVAILABLE" for card in merged
        ):
            merged = _replace_card(merged, "Borrow", borrow)

        depth = build_institutional_depth_card(
            symbol,
            prediction_cutoff=prediction_cutoff,
            as_of_context=as_of_context,
        )
        if depth.get("state") != "UNAVAILABLE":
            merged = _replace_card(merged, "Depth", depth)
        elif not any(card.get("label") == "Depth" for card in merged):
            merged.append(depth)

    return merge_options_institutional_card(
        merged,
        symbol=symbol,
        prediction_cutoff=prediction_cutoff,
        as_of_context=as_of_context,
        frozen_aggregate_only=frozen_aggregate_only,
    )


def merge_options_institutional_card(
    cards: list[dict[str, Any]],
    *,
    symbol: str,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None = None,
    frozen_aggregate_only: bool = False,
) -> list[dict[str, Any]]:
    """Replace or append the Options card with institutional fixture data when entitled."""
    if prediction_cutoff is None and frozen_aggregate_only:
        return cards

    institutional = build_institutional_options_card(
        symbol,
        prediction_cutoff=prediction_cutoff,
        as_of_context=as_of_context,
    )
    if prediction_cutoff is None:
        return cards

    merged: list[dict[str, Any]] = []
    replaced = False
    for card in cards:
        if card.get("label") == "Options":
            merged.append(institutional)
            replaced = True
        else:
            merged.append(card)
    if not replaced:
        merged.append(institutional)
    return merged


__all__ = [
    "build_institutional_borrow_card",
    "build_institutional_depth_card",
    "build_institutional_options_card",
    "build_supplemental_ignition_evidence",
    "merge_institutional_ignition_cards",
    "merge_options_institutional_card",
    "_OPTIONS_FROZEN_UNAVAILABLE",
]
