"""Live Paper Path A: one selected Screener candidate → PRODUCTION forecast → StrategyMatch → governed Opportunity.

Every step is an existing governed component: the live corpus window and snapshot/signal engine
(``decision_inputs``), the fail-closed PRODUCTION emitter, BUILD 14 fusion with a calibrator trained on
earlier settled rows (``produce_paper_demo_forecast``), the universal scanner with one preregistered strategy
evaluated by ``interpret_strategy``, and the canonical StrategyMatch → OpportunityEngine bridge. Nothing here
mints a probability from a price, calls a language model, reaches a broker or places an order. An Opportunity
only lets the Action Decision gate consider an ENTER; the AI proposal, the gate and the Paper risk policy still
decide, and the order still goes to the internal simulator.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..intelligence.contracts.common import ContractReference, IntelligenceScope
from ..intelligence.contracts.strategy_match import StrategyMatchDisposition
from ..intelligence.fusion.types import CalibrationModelArtifact
from ..intelligence.opportunity.policy import build_opportunity_policy
from ..intelligence.opportunity.types import OpportunityContext, OpportunityPolicyV1
from ..intelligence.production.emitter import emit_production_forecast
from ..intelligence.production.identity import PATH_A_HORIZON_NS, path_a_direction_target, path_a_horizon
from ..intelligence.production.live_feature_corpus import RollingEventWindow, decision_inputs
from ..intelligence.production.model import ProductionSpecialistModel
from ..intelligence.promotion.types import ChampionAssignmentReason, ChampionAssignmentV1, ChampionScopeV1
from ..intelligence.quality.models import QualityAssessment
from ..providers.identity import InstrumentIdentity
from ..research.forecast import build_forecast, verify_forecast_interface
from .interpretation import interpret_strategy
from .path_a_forecast_producer import produce_paper_demo_forecast
from .path_a_scan_caller import PathAScanCaller
from .preregistration import verify_preregistration
from .scanning import (
    CapabilityContextSnapshot,
    PointInTimeUniverse,
    ScanBudget,
    ScanRequest,
    ScanScope,
    ScanTrigger,
    ScanTriggerType,
    StrategyEvaluationContext,
    StrategyEvaluationResult,
    StrategyRegistration,
    UniversalStrategyScanner,
)
from .strategy_spec import StrategyDefinition, build_strategy_definition

SCENARIO_ID = "paper-live-forecast"
LIVE_STRATEGY_ID = "path-a-production-direction-long"
MODE = "paper"
MINIMUM_PROBABILITY_EDGE = 0.05
MAX_FORECAST_AGE_NS = 60_000_000_000
# Shorter than the automation cadence (300 s): the Action Decision gate accepts exactly one live Opportunity per
# candidate, so one cycle's Opportunity has lapsed before the next cycle mints its own.
MAX_OPPORTUNITY_LIFETIME_NS = 240_000_000_000
SCAN_TTL_NS = 60_000_000_000

STATUS_MINTED = "MINTED"
STATUS_SUPPRESSED = "SUPPRESSED"
STATUS_NOT_MATCHED = "NOT_MATCHED"
STATUS_FORECAST_UNAVAILABLE = "FORECAST_UNAVAILABLE"


def live_strategy_definition() -> StrategyDefinition:
    """The one strategy this path evaluates. Its identity hash is what the preregistration binds."""
    return build_strategy_definition(
        alignment_type="FORECAST_MOMENTUM",
        hypothesis=("A calibrated Path A PRODUCTION 5-minute direction probability above one half, from live L1 "
                    "quotes and trades, supports a long internal-simulation Paper entry"),
        evidence_requirements=["path_a_production_forecast", "live_l1_quotes_and_trades"],
        family="path-a-production", style="intraday-direction", asset_class="EQUITY", timeframe="5m")


def qualified_instrument_id(instrument: Mapping[str, Any]) -> str:
    """The exact canonical id of a Screener candidate's own instrument record. Never a symbol lookup."""
    return InstrumentIdentity("canonical", str(instrument["instrument_id"]), str(instrument["asset_class"]),
                              str(instrument["venue_id"]), "USD").qualified_id()


@dataclass(frozen=True, slots=True)
class LiveForecastArtifacts:
    """One instrument's activated build: the specialist, its calibrator and the champion bound to them."""

    instrument_id: str
    build_id: str
    model: ProductionSpecialistModel
    calibration: CalibrationModelArtifact
    activated_at_ns: int

    @property
    def champion(self) -> ChampionAssignmentV1:
        return ChampionAssignmentV1(
            assignment_id=f"champion-paper-live-{self.model.model_id[6:22]}",
            schema_version="1",
            champion_scope=champion_scope(),
            candidate_id=f"{self.build_id}:{self.instrument_id}",
            candidate_artifact_hash=self.model.model_id,
            promotion_decision_id=None,
            previous_assignment_id=None,
            effective_from_ns=self.activated_at_ns,
            assignment_reason=ChampionAssignmentReason.BOOTSTRAP,
        )


def champion_scope() -> ChampionScopeV1:
    return ChampionScopeV1(component="forecast", target_kind="direction", horizon_ns=PATH_A_HORIZON_NS,
                           mode=MODE.upper(), scenario_id=SCENARIO_ID)


def live_policy() -> OpportunityPolicyV1:
    return build_opportunity_policy(champion_scope=champion_scope(), minimum_probability_edge=MINIMUM_PROBABILITY_EDGE,
                                    require_calibrated_probability=True, max_forecast_age_ns=MAX_FORECAST_AGE_NS,
                                    max_opportunity_lifetime_ns=MAX_OPPORTUNITY_LIFETIME_NS)


def _registered_before(preregistration: Mapping[str, Any] | None, decision_time_ns: int) -> dict[str, Any] | None:
    if not isinstance(preregistration, Mapping):
        return None
    try:
        registered = datetime.fromisoformat(str(preregistration["registered_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    if registered.tzinfo is None or int(registered.timestamp() * 1_000_000_000) >= decision_time_ns:
        return None
    return dict(preregistration)


def live_strategy_registration(preregistration: Mapping[str, Any] | None) -> StrategyRegistration:
    definition = live_strategy_definition()
    spec = definition.to_legacy_spec()

    def evaluate(context: StrategyEvaluationContext) -> StrategyEvaluationResult:
        decision_time_ns = context.capability_snapshot.as_of_time_ns
        raw = context.capability_snapshot.context
        forecast = raw.get("path_a_forecast") if isinstance(raw, Mapping) else None
        if not isinstance(forecast, Mapping) or forecast.get("calibrated_probability") is None:
            return StrategyEvaluationResult(disposition=StrategyMatchDisposition.UNAVAILABLE,
                                            unavailability_reasons=("PATH_A_FORECAST_UNAVAILABLE",))
        score = build_forecast(score=repr(float(forecast["calibrated_probability"]) - 0.5),
                               prediction_cutoff=decision_time_ns, horizon_ns=PATH_A_HORIZON_NS)
        status, _ = verify_forecast_interface(score)
        interpretation = interpret_strategy(strategy_spec=spec, preregistration=_registered_before(preregistration, decision_time_ns),
                                            forecast=score, forecast_status=status, prediction_cutoff=decision_time_ns,
                                            observation_time=int(forecast["decision_time_ns"]))
        if interpretation["outcome"] != "signal":
            return StrategyEvaluationResult(disposition=StrategyMatchDisposition.ABSTAINED,
                                            abstention_reasons=tuple(interpretation["abstention_reason_codes"]) or ("ABSTAINED",))
        if interpretation["direction"] != "long":
            # The armed Paper account is long-only; a down or flat forecast is not an entry for it.
            return StrategyEvaluationResult(disposition=StrategyMatchDisposition.REJECTED,
                                            rejection_reasons=(f"DIRECTION_{str(interpretation['direction']).upper()}_NOT_LONG",))
        return StrategyEvaluationResult(disposition=StrategyMatchDisposition.MATCHED)

    return StrategyRegistration(strategy_id=LIVE_STRATEGY_ID, definition=definition, evaluator=evaluate)


def preregistration_valid(preregistration: Mapping[str, Any] | None) -> bool:
    if not isinstance(preregistration, Mapping):
        return False
    status, _ = verify_preregistration(dict(preregistration), live_strategy_definition())
    return status == "PASS"


def _spread_bps(payload: Mapping[str, Any] | None) -> float | None:
    payload = payload or {}
    try:
        bid, ask = float(payload["bid"]), float(payload["ask"])
    except (KeyError, TypeError, ValueError):
        return None
    mid = (bid + ask) / 2
    return (ask - bid) / mid * 10_000 if mid > 0 and ask >= bid else None


def mint_live_opportunity(*, window: RollingEventWindow, candidate: Mapping[str, Any], artifacts: LiveForecastArtifacts,
                          preregistration: Mapping[str, Any] | None, account_id: str, decision_time_ns: int,
                          repository: Any, forecast_dir: Path) -> dict[str, Any]:
    """One honest attempt. Returns what happened and why; persists an Opportunity only when everything agrees."""
    instrument = candidate["instrument"]
    iid = str(instrument["instrument_id"])
    outcome: dict[str, Any] = dict(instrument_id=iid, build_id=artifacts.build_id, model_id=artifacts.model.model_id,
                                   decision_time=datetime.fromtimestamp(decision_time_ns / 1e9, UTC).isoformat())
    if iid != artifacts.instrument_id:
        return dict(outcome, status=STATUS_FORECAST_UNAVAILABLE, reason_codes=["MODEL_INSTRUMENT_MISMATCH"])
    if not preregistration_valid(preregistration):
        return dict(outcome, status=STATUS_FORECAST_UNAVAILABLE, reason_codes=["STRATEGY_PREREGISTRATION_INVALID"])
    qualified = qualified_instrument_id(instrument)
    capability_snapshot_id = f"PLF-{iid}-{decision_time_ns}"
    scope = IntelligenceScope(instrument_ids=(qualified,), context_id=f"{account_id}:{MODE}:{capability_snapshot_id}")
    row, snapshot, signals = decision_inputs(window, iid, decision_time_ns, scope=scope)
    outcome["features"] = row.get("features")
    if snapshot is None:
        return dict(outcome, status=STATUS_FORECAST_UNAVAILABLE, reason_codes=[str(row.get("reason"))])
    emitted = emit_production_forecast(snapshot=snapshot, signals=signals, model=artifacts.model, target=path_a_direction_target(iid),
                                       horizon=path_a_horizon(), mode=MODE, as_of_time_ns=decision_time_ns)
    if not emitted.emitted:
        return dict(outcome, status=STATUS_FORECAST_UNAVAILABLE, reason_codes=list(emitted.reason_codes))
    champion, policy = artifacts.champion, live_policy()
    produced = produce_paper_demo_forecast(contributors=[emitted.forecast], calibration_artifact=artifacts.calibration,
                                           champion=champion, policy=policy, destination=forecast_dir, account_id=account_id,
                                           mode=MODE, as_of_time_ns=decision_time_ns)
    outcome.update(raw_probability=emitted.forecast.estimate.probability)
    if not produced.persisted:
        return dict(outcome, status=STATUS_FORECAST_UNAVAILABLE, reason_codes=list(produced.reason_codes))
    forecast = produced.forecast
    calibrated = float(forecast.estimate.calibrated_probability)
    outcome.update(forecast_id=forecast.forecast_id, calibrated_probability=calibrated)
    evidence = tuple(ContractReference(kind="screener_evidence", id=str(item["evidence_id"]))
                     for item in candidate.get("current_market_evidence") or () if item.get("evidence_id"))
    request = ScanRequest(
        universe=PointInTimeUniverse(decision_time_ns, (InstrumentIdentity("canonical", iid, str(instrument["asset_class"]),
                                                                           str(instrument["venue_id"]), "USD"),)),
        capability_snapshot=CapabilityContextSnapshot(
            snapshot_id=capability_snapshot_id, as_of_time_ns=decision_time_ns,
            quality_assessment=QualityAssessment(decision_time_ns=decision_time_ns),
            source_snapshot_ref=ContractReference(kind="snapshot", id=snapshot.snapshot_id),
            source_evidence_refs=evidence, source_signal_refs=tuple(ContractReference(kind="signal", id=s.signal_id) for s in signals),
            context={"session": "REGULAR", "candidate_run_id": candidate.get("run_id"),
                     "path_a_forecast": {"forecast_id": forecast.forecast_id, "calibrated_probability": calibrated,
                                         "decision_time_ns": forecast.decision_time_ns}}),
        strategies=(live_strategy_registration(preregistration),),
        scope=ScanScope(account_id=account_id, mode=MODE),
        trigger=ScanTrigger(ScanTriggerType.SCHEDULED, {"source": "paper-automation-cycle"}),
        decision_time_ns=decision_time_ns, expires_at_ns=decision_time_ns + SCAN_TTL_NS,
        budget=ScanBudget(max_evaluations=1, max_cost_units=1))
    quote = window.last_quote_at_or_before(iid, decision_time_ns)
    spread = _spread_bps(quote.payload if quote is not None else None)
    caller = PathAScanCaller(
        scanner=UniversalStrategyScanner(query_planner=None, repository=repository), repository=repository,
        forecast_resolver=lambda _match: forecast, champion_at_forecast=champion, champion_at_opportunity=champion,
        opportunity_policy=policy,
        opportunity_context=OpportunityContext(
            snapshot_ref=ContractReference(kind="snapshot", id=snapshot.snapshot_id), snapshot_available_time_ns=decision_time_ns,
            spread_bps=spread, spread_available_time_ns=decision_time_ns if spread is not None else None,
            mode=MODE, scenario_id=SCENARIO_ID, account_id=account_id))
    result = caller.run(request)
    outcome.update(scan_id=result.scan_id, matched=result.matched_count, spread_bps=spread)
    if result.opportunities:
        opportunity = result.opportunities[0]
        return dict(outcome, status=STATUS_MINTED, reason_codes=["OPPORTUNITY_EMITTED"], opportunity_id=opportunity.opportunity_id,
                    side=getattr(opportunity.side, "value", opportunity.side),
                    valid_until=datetime.fromtimestamp(opportunity.valid_until_ns / 1e9, UTC).isoformat())
    if not result.matched_count:
        reasons = [reason for match in result.scan.matches for reason in
                   (*match.rejection_reasons, *match.abstention_reasons, *match.unavailability_reasons)]
        return dict(outcome, status=STATUS_NOT_MATCHED, reason_codes=reasons[:8] or list(result.reason_codes))
    return dict(outcome, status=STATUS_SUPPRESSED, reason_codes=list(result.reason_codes)[:8])


def load_preregistration(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


__all__ = [
    "LIVE_STRATEGY_ID",
    "LiveForecastArtifacts",
    "MINIMUM_PROBABILITY_EDGE",
    "SCENARIO_ID",
    "STATUS_FORECAST_UNAVAILABLE",
    "STATUS_MINTED",
    "STATUS_NOT_MATCHED",
    "STATUS_SUPPRESSED",
    "champion_scope",
    "live_policy",
    "live_strategy_definition",
    "live_strategy_registration",
    "load_preregistration",
    "mint_live_opportunity",
    "preregistration_valid",
    "qualified_instrument_id",
]
