"""Observational Cboe options context for opportunity evidence overlays.

Evidence / context only. Not execution authority, not an options strategy,
and not Live options trading authorization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .aggregate import build_options_aggregate_context
from .contracts import (
    OptionContractActivitySnapshot,
    OptionsMarketStatisticObservation,
    contract_snapshot_to_dict,
    market_statistic_to_dict,
)
from .derived import DerivedPutCallRatio, derive_put_call_features
from .quality import CboeOptionsQualityFlag
from .store import CboeOptionsStore

AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION = "EVIDENCE_NOT_PREDICTION"
ATTACHMENT_KIND = "CBOE_OPTIONS_OBSERVATIONAL_CONTEXT"
PROVENANCE_REF = "cboe_options.opportunity_observational_context"

EXPLICIT_EXCLUSIONS: tuple[str, ...] = (
    "NOT_OPTIONS_LIVE_TRADING",
    "NOT_OPTIONS_EXECUTION_AUTHORITY",
    "NOT_OPTIONS_STRATEGY",
    "NOT_DIRECTIONAL_SIGNAL",
    "NOT_PREDICTIVE_MODEL",
    "AGGREGATE_CONTEXT_IS_PRODUCT_SCOPE_NOT_SINGLE_NAME",
)

FORBIDDEN_AUTHORITY_KEYS: frozenset[str] = frozenset(
    {
        "execution_authority",
        "live_trading",
        "submit_order",
        "broker_order",
        "options_strategy",
        "trade_direction",
        "bullish",
        "bearish",
        "smart_money",
        "whale",
        "alpha",
        "expected_return",
        "score",
        "signal",
    }
)

_UNDERLYING_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")


def underlying_symbol_from_instrument_id(instrument_id: str) -> str:
    """Resolve a ticker root from common instrument id forms (generic; not a symbol allowlist)."""

    value = str(instrument_id or "").strip().upper()
    if not value:
        return ""
    symbol = value.replace("/", ":").split(":")[-1].strip()
    if not _UNDERLYING_RE.fullmatch(symbol):
        return ""
    return symbol


def _derived_to_dict(row: DerivedPutCallRatio) -> dict[str, Any]:
    return {
        "canonical_statistic_id": row.canonical_statistic_id,
        "put_call_ratio": row.put_call_ratio,
        "call_share": row.call_share,
        "put_share": row.put_share,
        "available_time": row.available_time,
        "feature_layer": row.feature_layer.value,
        "predictive": row.predictive,
        "semantics": "ACTIVITY_MIX_NOT_DIRECTION",
    }


@dataclass(frozen=True, slots=True)
class CboeOptionsObservationalContext:
    """Bounded observational options context for an equity underlying.

    Market aggregates retain product-class scope. Single-name contract rows are
    filtered by underlying when exchange symbol snapshots are available.
    """

    underlying_symbol: str
    decision_time: str
    authority_class: str = AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION
    attachment_kind: str = ATTACHMENT_KIND
    evidence_class: str = "OBSERVATIONAL"
    predictive: bool = False
    live_trading_authorized: bool = False
    options_strategy: None = None
    open_interest: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    volume: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    derived_activity: tuple[DerivedPutCallRatio, ...] = field(default_factory=tuple)
    underlying_contract_activity: tuple[OptionContractActivitySnapshot, ...] = field(
        default_factory=tuple
    )
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    staleness: dict[str, str | None] = field(default_factory=dict)
    provenance_ref: str = PROVENANCE_REF
    explicit_exclusions: tuple[str, ...] = EXPLICIT_EXCLUSIONS
    aggregate_provenance_ref: str = ""


def build_cboe_options_observational_context(
    store: CboeOptionsStore,
    *,
    underlying_symbol: str,
    decision_time: str,
) -> CboeOptionsObservationalContext:
    symbol = underlying_symbol_from_instrument_id(underlying_symbol) or str(
        underlying_symbol
    ).strip().upper()
    aggregate = build_options_aggregate_context(store, as_of_time=decision_time)

    underlying_snaps = tuple(
        snap
        for snap in aggregate.contract_activity_snapshot
        if str(snap.underlying or "").strip().upper() == symbol
    )

    derived: list[DerivedPutCallRatio] = []
    for obs in aggregate.put_call_activity:
        feature = derive_put_call_features(obs)
        if feature is not None:
            derived.append(feature)

    quality_flags = set(aggregate.quality_flags)
    quality_flags.add(CboeOptionsQualityFlag.OPEN_CLOSE_UNKNOWN.value)
    quality_flags.add(CboeOptionsQualityFlag.DIRECTION_UNKNOWN.value)
    if not underlying_snaps:
        quality_flags.add("UNDERLYING_CONTRACT_ACTIVITY_NOT_OBSERVED")

    staleness = dict(aggregate.staleness)
    staleness["underlying_contract_activity"] = max(
        (snap.available_time for snap in underlying_snaps),
        default=None,
    )

    return CboeOptionsObservationalContext(
        underlying_symbol=symbol,
        decision_time=decision_time,
        open_interest=aggregate.open_interest_context,
        volume=aggregate.volume_activity,
        derived_activity=tuple(derived),
        underlying_contract_activity=underlying_snaps,
        quality_flags=tuple(sorted(quality_flags)),
        staleness=staleness,
        aggregate_provenance_ref=aggregate.provenance_ref,
    )


def observational_context_to_dict(context: CboeOptionsObservationalContext) -> dict[str, Any]:
    """Serialize observational context for evidence overlays (no authority upgrade)."""

    return {
        "underlying_symbol": context.underlying_symbol,
        "decision_time": context.decision_time,
        "authority_class": context.authority_class,
        "attachment_kind": context.attachment_kind,
        "evidence_class": context.evidence_class,
        "predictive": context.predictive,
        "live_trading_authorized": context.live_trading_authorized,
        "options_strategy": context.options_strategy,
        "open_interest": [market_statistic_to_dict(obs) for obs in context.open_interest],
        "volume": [market_statistic_to_dict(obs) for obs in context.volume],
        "derived_activity": [_derived_to_dict(row) for row in context.derived_activity],
        "underlying_contract_activity": [
            contract_snapshot_to_dict(obs) for obs in context.underlying_contract_activity
        ],
        "quality_flags": list(context.quality_flags),
        "staleness": dict(context.staleness),
        "provenance_ref": context.provenance_ref,
        "aggregate_provenance_ref": context.aggregate_provenance_ref,
        "explicit_exclusions": list(context.explicit_exclusions),
        "market_aggregate_scope_note": (
            "open_interest and volume rows are Cboe product-class aggregates; "
            "they are not single-name claims unless present in underlying_contract_activity"
        ),
    }


__all__ = [
    "ATTACHMENT_KIND",
    "AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION",
    "CboeOptionsObservationalContext",
    "EXPLICIT_EXCLUSIONS",
    "FORBIDDEN_AUTHORITY_KEYS",
    "PROVENANCE_REF",
    "build_cboe_options_observational_context",
    "observational_context_to_dict",
    "underlying_symbol_from_instrument_id",
]
