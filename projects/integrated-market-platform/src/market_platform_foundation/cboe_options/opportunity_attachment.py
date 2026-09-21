"""Thin adapter: attach observational Cboe options context to an admitted opportunity.

Does not mutate OpportunityV1 / thesis / invalidation schema. Produces an
evidence overlay only. Never authorizes Live options trading or invents a
strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .opportunity_evidence import (
    ATTACHMENT_KIND,
    AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
    CboeOptionsObservationalContext,
    build_cboe_options_observational_context,
    observational_context_to_dict,
    underlying_symbol_from_instrument_id,
)
from .store import CboeOptionsStore

STATUS_ADMITTED = "ADMITTED"
ASSET_CLASS_US_EQUITY = "US_EQUITY"

DENIAL_FAMILY_NOT_ADMITTED = "FAMILY_NOT_ADMITTED"
DENIAL_ASSET_CLASS_NOT_US_EQUITY = "ASSET_CLASS_NOT_US_EQUITY"
DENIAL_OPPORTUNITY_SCOPE_EMPTY = "OPPORTUNITY_SCOPE_EMPTY"
DENIAL_UNDERLYING_UNRESOLVED = "UNDERLYING_UNRESOLVED"


class _OpportunityAttachTarget(Protocol):
    opportunity_id: str

    @property
    def scope(self) -> Any: ...

    @property
    def metadata(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class CboeOptionsOpportunityAttachment:
    disposition: str
    opportunity_id: str
    underlying_symbol: str = ""
    denial_reason: str | None = None
    context: CboeOptionsObservationalContext | None = None
    authority_class: str = AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
    attachment_kind: str = ATTACHMENT_KIND


def _instrument_ids(opportunity: _OpportunityAttachTarget) -> tuple[str, ...]:
    scope = getattr(opportunity, "scope", None)
    raw = getattr(scope, "instrument_ids", ()) if scope is not None else ()
    return tuple(str(item) for item in raw if str(item).strip())


def _metadata(opportunity: _OpportunityAttachTarget) -> Mapping[str, Any]:
    meta = getattr(opportunity, "metadata", None)
    return meta if isinstance(meta, Mapping) else {}


def _admission_gate(opportunity: _OpportunityAttachTarget) -> str | None:
    meta = _metadata(opportunity)
    if meta.get("family_admission_status") != STATUS_ADMITTED:
        return DENIAL_FAMILY_NOT_ADMITTED
    asset_class = str(meta.get("asset_class") or "").strip().upper()
    if asset_class != ASSET_CLASS_US_EQUITY:
        return DENIAL_ASSET_CLASS_NOT_US_EQUITY
    instruments = _instrument_ids(opportunity)
    if not instruments:
        return DENIAL_OPPORTUNITY_SCOPE_EMPTY
    if not underlying_symbol_from_instrument_id(instruments[0]):
        return DENIAL_UNDERLYING_UNRESOLVED
    return None


def attach_cboe_options_observational_context(
    opportunity: _OpportunityAttachTarget,
    *,
    store: CboeOptionsStore,
    decision_time: str,
) -> CboeOptionsOpportunityAttachment:
    """Bind observational Cboe context onto an already-admitted US equity opportunity.

    Fail-closed on admission / asset-class / scope. Never mutates the opportunity.
    Never sets Live trading or strategy authority.
    """

    opportunity_id = str(getattr(opportunity, "opportunity_id", "") or "")
    denial = _admission_gate(opportunity)
    if denial is not None:
        return CboeOptionsOpportunityAttachment(
            disposition="DENIED",
            opportunity_id=opportunity_id,
            denial_reason=denial,
            context=None,
        )

    instruments = _instrument_ids(opportunity)
    underlying = underlying_symbol_from_instrument_id(instruments[0])
    context = build_cboe_options_observational_context(
        store,
        underlying_symbol=underlying,
        decision_time=decision_time,
    )
    return CboeOptionsOpportunityAttachment(
        disposition="ATTACHED",
        opportunity_id=opportunity_id,
        underlying_symbol=underlying,
        denial_reason=None,
        context=context,
    )


def attachment_to_dict(attachment: CboeOptionsOpportunityAttachment) -> dict[str, Any]:
    body: dict[str, Any] = {
        "disposition": attachment.disposition,
        "opportunity_id": attachment.opportunity_id,
        "underlying_symbol": attachment.underlying_symbol,
        "denial_reason": attachment.denial_reason,
        "authority_class": attachment.authority_class,
        "attachment_kind": attachment.attachment_kind,
        "live_trading_authorized": False,
        "options_strategy": None,
        "context": None,
    }
    if attachment.context is not None:
        body["context"] = observational_context_to_dict(attachment.context)
    return body


__all__ = [
    "ASSET_CLASS_US_EQUITY",
    "CboeOptionsOpportunityAttachment",
    "DENIAL_ASSET_CLASS_NOT_US_EQUITY",
    "DENIAL_FAMILY_NOT_ADMITTED",
    "DENIAL_OPPORTUNITY_SCOPE_EMPTY",
    "DENIAL_UNDERLYING_UNRESOLVED",
    "STATUS_ADMITTED",
    "attach_cboe_options_observational_context",
    "attachment_to_dict",
]
