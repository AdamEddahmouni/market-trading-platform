"""Declarative dependency data: Phase 2 operations and the 25 Phase 3A rules.

Pure data, no formula logic and no trading threshold. Each entry declares the evidence
domains, required metrics, and the IBKR *semantic* fields whose resolution materially
affects the operation. The 25 rule ids and categories here are cross-checked against the
committed Phase 3A policy JSON by a test (this module never imports the evaluation
package at runtime, keeping the readiness runtime free of Phase 3A/3B evaluation code).
"""

from __future__ import annotations

from .models import OperationDependency, OperationKind, SemanticDependency

MARKET_BARS = "MARKET_BARS"

_RATIO_PRICE = SemanticDependency(price_adjustment_ratio=True, dividend_adjustment=True)
_ABSOLUTE_PRICE = SemanticDependency(price_adjustment_absolute=True)
_VOLUME = SemanticDependency(
    volume_unit=True, volume_corporate_action=True, volume_filter_stationarity=True
)
_AVAIL = SemanticDependency()
_COMPLETED = SemanticDependency(timestamp_boundary=True)


def _op(operation: str, kind: OperationKind, **kwargs: object) -> OperationDependency:
    return OperationDependency(operation=operation, kind=kind, **kwargs)


# --- Phase 2 operation dependencies (the MARKET_BARS-reachable operations plus the
# non-market-bar operations that Phase 3A rules reference). ----------------------------
PHASE2_OPERATION_DEPENDENCIES: tuple[OperationDependency, ...] = (
    # Price ratios: one uniform split factor cancels within a series -> split-invariant.
    _op("PERCENTAGE_RETURN", OperationKind.PRICE_ONLY_RATIO,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        semantic_dependency=_RATIO_PRICE),
    _op("PERCENTAGE_SESSION_GAP", OperationKind.PRICE_ONLY_RATIO,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        semantic_dependency=_RATIO_PRICE),
    _op("PERCENTAGE_BAR_RANGE", OperationKind.PRICE_ONLY_RATIO,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        semantic_dependency=_RATIO_PRICE),
    _op("PERCENTAGE_RETURN_Z_SCORE", OperationKind.PRICE_ONLY_RATIO,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        requires_trailing_window=True, semantic_dependency=_RATIO_PRICE),
    # Price absolute differences/levels: a split factor scales the value -> NOT invariant.
    _op("ABSOLUTE_RETURN", OperationKind.PRICE_ONLY_ABSOLUTE_LEVEL,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        semantic_dependency=_ABSOLUTE_PRICE),
    _op("ABSOLUTE_SESSION_GAP", OperationKind.PRICE_ONLY_ABSOLUTE_LEVEL,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        semantic_dependency=_ABSOLUTE_PRICE),
    _op("ABSOLUTE_BAR_RANGE", OperationKind.PRICE_ONLY_ABSOLUTE_LEVEL,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        semantic_dependency=_ABSOLUTE_PRICE),
    # Volume operations: unit + corporate-action + filter-stationarity all unresolved.
    _op("MEAN_VOLUME_BASELINE", OperationKind.VOLUME_DEPENDENT,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        requires_trailing_window=True, semantic_dependency=_VOLUME),
    _op("RELATIVE_VOLUME", OperationKind.VOLUME_DEPENDENT,
        required_domains=(MARKET_BARS,), required_metric_names=("MEAN_VOLUME_BASELINE",),
        touches_detection_context_bars=True, requires_trailing_window=True,
        semantic_dependency=_VOLUME),
    _op("VOLUME_Z_SCORE", OperationKind.VOLUME_DEPENDENT,
        required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
        requires_trailing_window=True, semantic_dependency=_VOLUME),
)


# --- The 25 Phase 3A rules. Frozen; cross-checked against the policy JSON by a test. ---
def _rule(operation: str, kind: OperationKind, category: str, **kwargs: object):
    dep = _op(operation, kind, **kwargs)
    return dep, category


PHASE3A_RULE_DEPENDENCIES: tuple[tuple[OperationDependency, str], ...] = (
    # MOMENTUM_DISCOVERY
    _rule("MARKET_DATA_AVAILABLE", OperationKind.MARKET_BAR_AVAILABILITY, "MOMENTUM_DISCOVERY",
          required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
          semantic_dependency=_AVAIL),
    _rule("COMPLETED_BAR_AVAILABLE", OperationKind.MARKET_BAR_AVAILABILITY, "MOMENTUM_DISCOVERY",
          required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
          semantic_dependency=_COMPLETED),
    _rule("PERCENTAGE_CHANGE_MINIMUM", OperationKind.PRICE_ONLY_RATIO, "MOMENTUM_DISCOVERY",
          required_domains=(MARKET_BARS,), required_metric_names=("PERCENTAGE_RETURN",),
          touches_detection_context_bars=True, semantic_dependency=_RATIO_PRICE),
    _rule("PRICE_RANGE", OperationKind.PRICE_ONLY_ABSOLUTE_LEVEL, "MOMENTUM_DISCOVERY",
          required_domains=(MARKET_BARS,), touches_detection_context_bars=True,
          semantic_dependency=_ABSOLUTE_PRICE),
    _rule("RELATIVE_VOLUME_MINIMUM", OperationKind.VOLUME_DEPENDENT, "MOMENTUM_DISCOVERY",
          required_domains=(MARKET_BARS,), required_metric_names=("RELATIVE_VOLUME",),
          touches_detection_context_bars=True, requires_trailing_window=True,
          semantic_dependency=_VOLUME),
    _rule("FLOAT_MAXIMUM", OperationKind.NON_MARKET_BAR_DOMAIN, "MOMENTUM_DISCOVERY",
          required_domains=("CANDIDATE_SNAPSHOT",), touches_detection_context_bars=False),
    # SHORT_PRESSURE_CONFIRMATION
    _rule("PUBLISHED_SHORT_INTEREST_AVAILABLE", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION", required_domains=("PUBLISHED_SHORT_INTEREST",),
          touches_detection_context_bars=False),
    _rule("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION", required_domains=("PUBLISHED_SHORT_INTEREST",),
          required_metric_names=("PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE",),
          touches_detection_context_bars=False),
    _rule("DAYS_TO_COVER_MINIMUM", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION",
          required_domains=("PUBLISHED_SHORT_INTEREST",),
          required_metric_names=("DAYS_TO_COVER",),
          touches_detection_context_bars=False),
    _rule("BORROW_FEE_MINIMUM", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION", required_domains=("BORROW_FEE",),
          touches_detection_context_bars=False),
    _rule("BORROW_FEE_CHANGE_MINIMUM", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION", required_domains=("BORROW_FEE",),
          required_metric_names=("BORROW_FEE_ABSOLUTE_CHANGE",),
          touches_detection_context_bars=False),
    _rule("BORROW_AVAILABILITY_MAXIMUM", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION", required_domains=("BORROW_AVAILABILITY",),
          touches_detection_context_bars=False),
    _rule("BORROW_AVAILABILITY_CHANGE_MAXIMUM", OperationKind.NON_MARKET_BAR_DOMAIN,
          "SHORT_PRESSURE_CONFIRMATION", required_domains=("BORROW_AVAILABILITY",),
          required_metric_names=("BORROW_AVAILABILITY_ABSOLUTE_CHANGE",),
          touches_detection_context_bars=False),
    # CATALYST_EVIDENCE
    _rule("NEWS_AVAILABLE", OperationKind.NON_MARKET_BAR_DOMAIN, "CATALYST_EVIDENCE",
          required_domains=("NEWS",), touches_detection_context_bars=False),
    _rule("NEWS_AVAILABLE_BEFORE_AS_OF", OperationKind.NON_MARKET_BAR_DOMAIN, "CATALYST_EVIDENCE",
          required_domains=("NEWS",), touches_detection_context_bars=False),
    _rule("NEWS_TIMESTAMP_KNOWN", OperationKind.NON_MARKET_BAR_DOMAIN, "CATALYST_EVIDENCE",
          required_domains=("NEWS",), touches_detection_context_bars=False),
    _rule("SEC_FILING_AVAILABLE", OperationKind.NON_MARKET_BAR_DOMAIN, "CATALYST_EVIDENCE",
          required_domains=("SEC_FILINGS",), touches_detection_context_bars=False),
    _rule("CORPORATE_ACTION_CONTEXT_AVAILABLE", OperationKind.NON_MARKET_BAR_DOMAIN,
          "CATALYST_EVIDENCE", touches_detection_context_bars=False),
    # EVIDENCE_VALIDITY (meta-rules over the assembled request, not over the bars alone)
    _rule("REQUIRED_DOMAINS_PRESENT", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
    _rule("NO_MATERIAL_CONFLICTS", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
    _rule("POINT_IN_TIME_ELIGIBLE", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
    _rule("REQUIRED_UNITS_COMPATIBLE", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
    _rule("REQUIRED_HISTORY_SUFFICIENT", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
    _rule("NO_DEFAULT_SUBSTITUTION", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
    _rule("PROVIDER_SCOPE_EXPLICIT", OperationKind.EVIDENCE_META, "EVIDENCE_VALIDITY",
          touches_detection_context_bars=False),
)

# Domains present in the Batch 05 detection-context evidence set.
DETECTION_CONTEXT_PRESENT_DOMAINS: frozenset[str] = frozenset({MARKET_BARS})

# The frozen enabled rule ids (order-independent; sorted). Cross-checked to the policy.
ENABLED_RULE_IDS: tuple[str, ...] = tuple(
    sorted(dep.operation for dep, _ in PHASE3A_RULE_DEPENDENCIES)
)


__all__ = [
    "MARKET_BARS",
    "PHASE2_OPERATION_DEPENDENCIES",
    "PHASE3A_RULE_DEPENDENCIES",
    "DETECTION_CONTEXT_PRESENT_DOMAINS",
    "ENABLED_RULE_IDS",
]
