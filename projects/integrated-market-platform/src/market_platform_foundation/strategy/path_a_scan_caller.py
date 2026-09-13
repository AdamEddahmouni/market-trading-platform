"""Bounded Paper/Demo Path A scan caller.

Runs ``UniversalStrategyScanner`` once and mints through the canonical Path A
bridge. This is not a daemon, not ``StrategyPaperRuntime`` workstation wiring, not
ingest, not Live, and not FTEP.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

from market_platform_foundation.intelligence.contracts.common import ContractReference
from market_platform_foundation.intelligence.contracts.forecast import ForecastV1
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.intelligence.opportunity.bridge import (
    OpportunityBridgeResult,
    bridge_strategy_match_to_opportunity,
)
from market_platform_foundation.intelligence.opportunity.economic_assessment import (
    UniversalEconomicAssessmentV1,
)
from market_platform_foundation.intelligence.opportunity.engine import OpportunityEngine
from market_platform_foundation.intelligence.opportunity.types import (
    OpportunityAssessmentV1,
    OpportunityContext,
    OpportunityPolicyV1,
)
from market_platform_foundation.intelligence.persistence.repository import IntelligenceRepository
from market_platform_foundation.intelligence.promotion.types import ChampionAssignmentV1

from .scanning import ScanRequest, ScanResult, UniversalStrategyScanner

ALLOWED_SCAN_MODES = frozenset({"demo", "paper"})
FORBIDDEN_LIVE_MODES = frozenset({"live", "actual_live"})

STATUS_EMPTY = "EMPTY"
STATUS_MINTED = "MINTED"
STATUS_SUPPRESSED = "SUPPRESSED"
STATUS_FORECAST_UNAVAILABLE = "FORECAST_UNAVAILABLE"


class PathAScanCallerError(ValueError):
    """A Path A scan-caller precondition failed."""


@dataclass(frozen=True, slots=True)
class PathAScanCallResult:
    """Honest outcome of one bounded Path A scan call."""

    status: str
    scan_id: str
    run_id: str
    mode: str
    reason_codes: tuple[str, ...]
    matched_count: int
    assessments: tuple[OpportunityAssessmentV1, ...]
    opportunities: tuple[OpportunityV1, ...]
    scan: ScanResult


def _normalize_mode(value: str) -> str:
    return str(value).strip().lower()


def _attach_forecast_reference(match: StrategyMatch, forecast: ForecastV1) -> StrategyMatch:
    ref = ContractReference(kind="forecast", id=forecast.forecast_id)
    if ref in match.source_forecast_refs:
        return match
    enriched = replace(
        match,
        source_forecast_refs=(ref,),
        lineage_refs=(*match.lineage_refs, ref),
    )
    object.__setattr__(enriched, "match_id", f"SM-{enriched.match_identity_hash}")
    return enriched


def _resolve_forecast(
    *,
    match: StrategyMatch,
    request: ScanRequest,
    forecast: Any,
    champion: ChampionAssignmentV1,
) -> ForecastV1 | None:
    if not isinstance(forecast, ForecastV1):
        return None
    if forecast.scope != match.scope:
        return None
    if forecast.decision_time_ns > request.decision_time_ns:
        return None
    if forecast.horizon.duration_ns != champion.champion_scope.horizon_ns:
        return None
    if forecast.resolve_time_ns is not None and forecast.resolve_time_ns <= forecast.decision_time_ns:
        return None
    metadata = forecast.metadata
    if metadata.get("account_id") not in {None, request.scope.account_id}:
        return None
    if metadata.get("mode") not in {None, request.scope.mode, str(request.scope.mode).upper()}:
        return None
    return forecast


class PathAScanCaller:
    """One-shot Paper/Demo caller: scan library → Path A mint. No execution."""

    def __init__(
        self,
        *,
        scanner: UniversalStrategyScanner,
        repository: IntelligenceRepository,
        forecast_resolver: Callable[[StrategyMatch], ForecastV1 | None],
        champion_at_forecast: ChampionAssignmentV1,
        champion_at_opportunity: ChampionAssignmentV1,
        opportunity_policy: OpportunityPolicyV1,
        opportunity_context: OpportunityContext,
        economic_assessment: UniversalEconomicAssessmentV1 | None = None,
        engine: OpportunityEngine | None = None,
    ) -> None:
        self.scanner = scanner
        self.repository = repository
        self.forecast_resolver = forecast_resolver
        self.champion_at_forecast = champion_at_forecast
        self.champion_at_opportunity = champion_at_opportunity
        self.opportunity_policy = opportunity_policy
        self.opportunity_context = opportunity_context
        self.economic_assessment = economic_assessment
        self.engine = engine

    def run(self, request: ScanRequest) -> PathAScanCallResult:
        mode = _normalize_mode(request.scope.mode)
        if mode in FORBIDDEN_LIVE_MODES:
            raise PathAScanCallerError("LIVE_SCAN_CALLER_FORBIDDEN")
        if mode not in ALLOWED_SCAN_MODES:
            raise PathAScanCallerError("MODE_NOT_PAPER_OR_DEMO")
        context_mode = _normalize_mode(self.opportunity_context.mode)
        if context_mode in FORBIDDEN_LIVE_MODES:
            raise PathAScanCallerError("LIVE_SCAN_CALLER_FORBIDDEN")
        if context_mode not in ALLOWED_SCAN_MODES:
            raise PathAScanCallerError("MODE_NOT_PAPER_OR_DEMO")

        scan = self.scanner.run(request)
        matched = tuple(
            match
            for match in scan.matches
            if match.disposition == StrategyMatchDisposition.MATCHED
        )
        if not matched:
            return PathAScanCallResult(
                status=STATUS_EMPTY,
                scan_id=scan.scan_id,
                run_id=scan.run_id,
                mode=mode,
                reason_codes=("NO_MATCHED_STRATEGY",),
                matched_count=0,
                assessments=(),
                opportunities=(),
                scan=scan,
            )

        assessments: list[OpportunityAssessmentV1] = []
        opportunities: list[OpportunityV1] = []
        last_status = STATUS_EMPTY
        reason_codes: list[str] = []

        for match in matched:
            try:
                resolved = self.forecast_resolver(match)
            except Exception:
                resolved = None
            forecast = _resolve_forecast(
                match=match,
                request=request,
                forecast=resolved,
                champion=self.champion_at_forecast,
            )
            if forecast is None:
                last_status = STATUS_FORECAST_UNAVAILABLE
                reason_codes.append("FORECAST_RESOLUTION_FAILED")
                continue
            match = _attach_forecast_reference(match, forecast)
            self.repository.put_strategy_match(match)
            self.repository.put_forecast(forecast)
            bridge: OpportunityBridgeResult = bridge_strategy_match_to_opportunity(
                match=match,
                forecast=forecast,
                champion_at_forecast=self.champion_at_forecast,
                champion_at_opportunity=self.champion_at_opportunity,
                policy=self.opportunity_policy,
                context=self.opportunity_context,
                opportunity_decision_time_ns=request.decision_time_ns,
                economic_assessment=self.economic_assessment,
                repository=self.repository,
                engine=self.engine,
            )
            assessments.append(bridge.assessment)
            if bridge.opportunity is None:
                last_status = STATUS_SUPPRESSED
                reason_codes.extend(
                    str(getattr(reason, "value", reason))
                    for reason in bridge.assessment.reason_codes
                )
                continue
            opportunities.append(bridge.opportunity)
            last_status = STATUS_MINTED

        if opportunities:
            status = STATUS_MINTED
            result_reasons: tuple[str, ...] = ("OPPORTUNITY_EMITTED",)
        else:
            status = last_status if last_status != STATUS_EMPTY else STATUS_FORECAST_UNAVAILABLE
            result_reasons = tuple(reason_codes)
        return PathAScanCallResult(
            status=status,
            scan_id=scan.scan_id,
            run_id=scan.run_id,
            mode=mode,
            reason_codes=result_reasons,
            matched_count=len(matched),
            assessments=tuple(assessments),
            opportunities=tuple(opportunities),
            scan=scan,
        )


__all__ = [
    "ALLOWED_SCAN_MODES",
    "FORBIDDEN_LIVE_MODES",
    "STATUS_EMPTY",
    "STATUS_FORECAST_UNAVAILABLE",
    "STATUS_MINTED",
    "STATUS_SUPPRESSED",
    "PathAScanCallResult",
    "PathAScanCaller",
    "PathAScanCallerError",
]
