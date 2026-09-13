"""One-shot Paper/Demo Path A hop: provider → admission → G7 → Path A.

Not a daemon. Does not start LiveObservationalRuntime. Ingest stays a reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from market_platform_foundation.clock import monotonic_wall_ns
from market_platform_foundation.intelligence.contracts.common import ContractReference
from market_platform_foundation.intelligence.opportunity.freshness import (
    OpportunityFreshnessPolicy,
    OpportunityFreshnessResult,
    evaluate_opportunity_freshness,
    fail_closed_for_actionable,
    merge_freshness_into_payload,
)
from market_platform_foundation.intelligence.opportunity.policy import build_opportunity_policy
from market_platform_foundation.intelligence.opportunity.types import (
    OpportunityContext,
    OpportunityPolicyV1,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion.types import (
    ChampionAssignmentReason,
    ChampionAssignmentV1,
    ChampionScopeV1,
)
from market_platform_foundation.intelligence.quality.models import QualityAssessment
from market_platform_foundation.market_data.live_admission import LiveAdmissionEngine
from market_platform_foundation.market_data.runtime_composition import ObservationalRuntimeComposition
from market_platform_foundation.providers.contracts import EquityQuoteProvider, ProviderResult
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.providers.runtime_capability import (
    DataTimeliness,
    EntitlementState,
    ProviderHealth,
    ProviderRuntimeState,
)

from .path_a_scan_caller import (
    ALLOWED_SCAN_MODES,
    FORBIDDEN_LIVE_MODES,
    PathAScanCallResult,
    PathAScanCaller,
    PathAScanCallerError,
)
from .path_a_forecast_store import (
    load_paper_demo_forecasts,
    select_eligible_forecast,
)
from .path_a_preregistration_store import (
    load_paper_demo_preregistrations,
    select_eligible_preregistration,
)
from .path_a_strategy_catalog import (
    build_paper_demo_strategy_catalog,
    paper_demo_catalog_specs,
)
from .scanning import (
    CapabilityContextSnapshot,
    PointInTimeUniverse,
    ScanBudget,
    ScanRequest,
    ScanScope,
    ScanTrigger,
    ScanTriggerType,
    UniversalStrategyScanner,
)


def _normalize_mode(value: str) -> str:
    return str(value).strip().lower()

STATUS_LIVE_FORBIDDEN = "LIVE_FORBIDDEN"
STATUS_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
STATUS_MALFORMED = "MALFORMED"
STATUS_ADMISSION_BLOCKED = "ADMISSION_BLOCKED"
STATUS_G7_NOT_ACTIONABLE = "G7_NOT_ACTIONABLE"
STATUS_EMPTY = "EMPTY"
STATUS_MINTED = "MINTED"
STATUS_SCAN_SKIPPED = "SCAN_SKIPPED"

DELAYED_SOURCE = "DELAYED_PROSPECTIVE"
LIVE_OBSERVED_SOURCE = "PAPER_OBSERVATIONAL"

PERSIST_NOT_MINTED = "NOT_MINTED"
PERSIST_INTENTIONAL_EPHEMERAL = "INTENTIONAL_EPHEMERAL"
PERSIST_SKIPPED_NO_SESSION = "SKIPPED_NO_SESSION"
PERSIST_WRITTEN = "PERSISTED"

HONESTY_HORIZON_NS = 300_000_000_000
HONESTY_SCAN_TTL_NS = 60_000_000_000


@dataclass(frozen=True, slots=True)
class PathAHonestyInvoke:
    """Paper/Demo Path A invoke with no MATCHED fixture. Honest EMPTY is success."""

    caller: PathAScanCaller
    scan_request: ScanRequest


def _quote_context_from_event(event: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(event, Mapping):
        return None
    raw_payload = event.get("raw_payload")
    last_price = raw_payload.get("last_price") if isinstance(raw_payload, Mapping) else None
    if last_price is None:
        return None
    clocks = event.get("clocks")
    event_time_ns = clocks.get("event_time_ns") if isinstance(clocks, Mapping) else None
    context: dict[str, Any] = {"last_price": last_price}
    if isinstance(event_time_ns, int):
        context["event_time_ns"] = event_time_ns
    return context


def _quote_event_time_ns(event: Mapping[str, Any] | None) -> int | None:
    if not isinstance(event, Mapping):
        return None
    clocks = event.get("clocks")
    event_time_ns = clocks.get("event_time_ns") if isinstance(clocks, Mapping) else None
    return event_time_ns if isinstance(event_time_ns, int) else None


def _eligible_preregistrations(
    *,
    preregistration_path: str | Path | None,
    quote_event: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if preregistration_path is None:
        return {}
    event_time_ns = _quote_event_time_ns(quote_event)
    if event_time_ns is None:
        return {}
    records = load_paper_demo_preregistrations(preregistration_path)
    eligible: dict[str, dict[str, Any]] = {}
    for spec in paper_demo_catalog_specs():
        selected = select_eligible_preregistration(
            spec, records, quote_event_time_ns=event_time_ns
        )
        if selected is not None:
            eligible[str(spec["strategy_identity_hash"])] = selected
    return eligible


def _paper_demo_forecast_resolver(
    *,
    forecast_path: str | Path | None,
    request: ScanRequest,
    champion: ChampionAssignmentV1,
    policy: OpportunityPolicyV1,
):
    records = load_paper_demo_forecasts(forecast_path) if forecast_path is not None else ()

    def resolve(match):
        return select_eligible_forecast(
            match,
            records,
            request=request,
            champion=champion,
            policy=policy,
        )

    return resolve


def build_paper_demo_path_a_invoke(
    symbol: str,
    *,
    mode: str = "paper",
    as_of_time_ns: int | None = None,
    account_id: str | None = None,
    quote_event: Mapping[str, Any] | None = None,
    preregistration_path: str | Path | None = None,
    forecast_path: str | Path | None = None,
) -> PathAHonestyInvoke:
    """Build a one-shot Paper/Demo Path A caller.

    Registers the real (non-fixture) baseline strategy catalog
    (``build_paper_demo_strategy_catalog``) so the scanner actually evaluates
    against real quote data when ``quote_event`` is supplied. Loads a
    previously persisted Phase-6 record only when identity matches the spec
    and ``registered_at`` is before quote ``event_time_ns``. Does not mint a
    preregistration at eval time.

    ``forecast_resolver`` loads a previously persisted PRODUCTION ``ForecastV1``
    only when identity/PIT/champion/horizon/account/mode match Opportunity
    Engine hop policy. Absent or mismatch → ``None`` (``FORECAST_UNAVAILABLE``).
    Does not mint a probability from last_price.
    """

    mode_n = _normalize_mode(mode)
    if mode_n in FORBIDDEN_LIVE_MODES:
        raise PathAScanCallerError("LIVE_SCAN_CALLER_FORBIDDEN")
    if mode_n not in ALLOWED_SCAN_MODES:
        raise PathAScanCallerError("MODE_NOT_PAPER_OR_DEMO")
    instrument = str(symbol or "").strip().upper()
    if not instrument:
        raise PathAScanCallerError("INSTRUMENT_REQUIRED")
    as_of = as_of_time_ns if as_of_time_ns is not None else monotonic_wall_ns()
    account = str(account_id or f"acct-{mode_n}").strip()
    snapshot_id = f"snapshot-path-a-honesty-{instrument.lower()}"
    repository = InMemoryIntelligenceRepository()
    champion = ChampionAssignmentV1(
        assignment_id="champion-path-a-honesty",
        schema_version="1",
        champion_scope=ChampionScopeV1(
            component="forecast",
            target_kind="direction",
            horizon_ns=HONESTY_HORIZON_NS,
            mode=mode_n.upper(),
            scenario_id="path-a-honesty",
        ),
        candidate_id="candidate-path-a-honesty",
        candidate_artifact_hash="artifact-path-a-honesty",
        promotion_decision_id=None,
        previous_assignment_id=None,
        effective_from_ns=as_of - 1 if as_of > 0 else 0,
        assignment_reason=ChampionAssignmentReason.BOOTSTRAP,
    )
    policy = build_opportunity_policy(
        champion_scope=champion.champion_scope,
        max_forecast_age_ns=HONESTY_HORIZON_NS,
        max_opportunity_lifetime_ns=20_000_000_000,
        minimum_probability_edge=0.05,
    )
    quote_context = _quote_context_from_event(quote_event)
    eligible = _eligible_preregistrations(
        preregistration_path=preregistration_path,
        quote_event=quote_event,
    )
    scan_context: dict[str, Any] = {
        "honesty": (
            "LOADED_PHASE6_PREREGISTRATION"
            if eligible
            else "NO_PREREGISTRATION_AUTHORITY_FOR_PATH_A_HOP"
        ),
        "session": "REGULAR",
    }
    if quote_context is not None:
        scan_context["quote"] = quote_context
    catalog = build_paper_demo_strategy_catalog(preregistrations=eligible)
    request = ScanRequest(
        universe=PointInTimeUniverse(
            as_of,
            (InstrumentIdentity("canonical", instrument, "EQUITY", "XNYS", "USD"),),
        ),
        capability_snapshot=CapabilityContextSnapshot(
            snapshot_id=snapshot_id,
            as_of_time_ns=as_of,
            quality_assessment=QualityAssessment(decision_time_ns=as_of),
            context=scan_context,
        ),
        strategies=catalog,
        scope=ScanScope(account_id=account, mode=mode_n),
        trigger=ScanTrigger(ScanTriggerType.SESSION_OPEN, {"session": "REGULAR"}),
        decision_time_ns=as_of,
        expires_at_ns=as_of + HONESTY_SCAN_TTL_NS,
        budget=ScanBudget(max_evaluations=len(catalog), max_cost_units=len(catalog)),
    )
    caller = PathAScanCaller(
        scanner=UniversalStrategyScanner(query_planner=None, repository=repository),
        repository=repository,
        forecast_resolver=_paper_demo_forecast_resolver(
            forecast_path=forecast_path,
            request=request,
            champion=champion,
            policy=policy,
        ),
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_policy=policy,
        opportunity_context=OpportunityContext(
            snapshot_ref=ContractReference(kind="snapshot", id=snapshot_id),
            snapshot_available_time_ns=as_of,
            mode=mode_n,
            scenario_id="path-a-honesty",
            account_id=account,
        ),
    )
    return PathAHonestyInvoke(caller=caller, scan_request=request)


@dataclass(frozen=True, slots=True)
class PathAPersistContext:
    """Existing Paper FT session for optional PD-09 v6 write. Does not activate FTEP."""

    service: Any
    account_id: str
    session_id: str
    strategy_id: str
    strategy_version: str


@dataclass(frozen=True, slots=True)
class PathAProspectiveResult:
    status: str
    mode: str
    provider_id: str
    instrument_id: str
    reason_codes: tuple[str, ...]
    timeliness: str
    source: str
    freshness: dict[str, Any]
    provenance: dict[str, Any]
    selection: dict[str, Any]
    path_a: PathAScanCallResult | None = None
    freshness_payload: dict[str, Any] = field(default_factory=dict)
    persist_status: str = PERSIST_NOT_MINTED
    forward_test_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body = {
            "freshness": dict(self.freshness),
            "forward_test_id": self.forward_test_id,
            "instrument_id": self.instrument_id,
            "mode": self.mode,
            "path_a_status": None if self.path_a is None else self.path_a.status,
            "persist_status": self.persist_status,
            "provenance": dict(self.provenance),
            "provider_id": self.provider_id,
            "reason_codes": list(self.reason_codes),
            "selection": dict(self.selection),
            "source": self.source,
            "status": self.status,
            "timeliness": self.timeliness,
        }
        if self.freshness_payload:
            body["freshness_payload"] = dict(self.freshness_payload)
        return body


def _timeliness_from_result(result: ProviderResult, event: Mapping[str, Any] | None) -> str:
    if event is not None:
        raw = str(event.get("timeliness") or "").upper()
        if raw:
            return raw
    if "delayed" in str(result.provider_id).lower() or "yahoo" in str(result.provider_id).lower():
        return "DELAYED"
    return "UNKNOWN"


class PathAProspectiveComposer:
    """One entitled/delayed snapshot through G7 into one Path A call."""

    def __init__(
        self,
        *,
        quote_provider: EquityQuoteProvider,
        composition: ObservationalRuntimeComposition | None = None,
        admission: LiveAdmissionEngine | None = None,
        path_a_caller: PathAScanCaller | None = None,
        freshness_policy: OpportunityFreshnessPolicy | None = None,
        persist: PathAPersistContext | None = None,
        preregistration_path: str | Path | None = None,
        forecast_path: str | Path | None = None,
    ) -> None:
        self.quote_provider = quote_provider
        self.composition = composition or ObservationalRuntimeComposition()
        self.admission = admission or LiveAdmissionEngine()
        self.path_a_caller = path_a_caller
        self.freshness_policy = freshness_policy or OpportunityFreshnessPolicy()
        self.persist = persist
        self.preregistration_path = preregistration_path
        self.forecast_path = forecast_path

    def run(
        self,
        symbol: str,
        *,
        mode: str = "paper",
        scan_request: ScanRequest | None = None,
        as_of_time_ns: int | None = None,
        session_state: str | None = "REGULAR",
    ) -> PathAProspectiveResult:
        mode_n = _normalize_mode(mode)
        instrument = str(symbol or "").strip().upper()
        as_of = as_of_time_ns if as_of_time_ns is not None else monotonic_wall_ns()
        if mode_n in FORBIDDEN_LIVE_MODES:
            return self._finish(
                STATUS_LIVE_FORBIDDEN,
                mode=mode_n,
                instrument=instrument,
                reasons=("LIVE_SCAN_CALLER_FORBIDDEN",),
                as_of=as_of,
            )
        fetched = self.quote_provider.fetch_quote(instrument)
        provider_id = str(fetched.provider_id or getattr(self.quote_provider, "provider_id", "") or "")
        if fetched.status != "available" or not fetched.events:
            status = STATUS_MALFORMED if fetched.reason_code in {"MALFORMED_RECORD", "MISSING_TIMESTAMP"} else STATUS_PROVIDER_UNAVAILABLE
            return self._finish(
                status,
                mode=mode_n,
                instrument=instrument,
                reasons=(str(fetched.reason_code or "PROVIDER_NOT_CONFIGURED"),),
                provider_id=provider_id,
                as_of=as_of,
            )
        event = dict(fetched.events[0])
        timeliness = _timeliness_from_result(fetched, event)
        source = DELAYED_SOURCE if timeliness == "DELAYED" else LIVE_OBSERVED_SOURCE
        admitted = self.composition.ingest_one_shot(
            event,
            admission=self.admission,
            wall_now_ns=as_of,
        )
        display = str((admitted.get("admission") or {}).get("display") or "")
        if display == "BLOCKED" or not admitted.get("admitted"):
            return self._finish(
                STATUS_ADMISSION_BLOCKED,
                mode=mode_n,
                instrument=instrument,
                reasons=tuple(admitted.get("eligibility_reason_codes") or ("ADMISSION_BLOCKED",)),
                provider_id=provider_id,
                timeliness=timeliness,
                source=source,
                as_of=as_of,
                extra_provenance={"admission": admitted.get("admission")},
            )
        self._stamp_runtime(provider_id, timeliness)
        snapshot = self.composition.runtime_capability_snapshot_for(
            instrument, provider_id=provider_id
        )
        evaluation = evaluate_opportunity_freshness(
            source=source,
            as_of_time_ns=as_of,
            last_source_time_ns=snapshot.get("last_source_time_ns"),
            policy=self.freshness_policy,
            runtime_capability=snapshot.get("runtime_capability"),
            session_state=session_state,
        )
        selection = self.composition.select_for_capability(
            "OBSERVATIONAL_L1",
            instrument,
            require_real_time=self.freshness_policy.realtime_required,
            provider_id=provider_id,
        )
        reasons = [evaluation.reason_code]
        if selection.get("outcome") not in {"SELECTED", "REPLAY_ONLY"}:
            reasons.append(f"G7_SELECTION_{selection.get('outcome') or 'NO_PROVIDER'}")
        path_a: PathAScanCallResult | None = None
        status = STATUS_G7_NOT_ACTIONABLE if fail_closed_for_actionable(evaluation) else STATUS_SCAN_SKIPPED
        caller = self.path_a_caller
        request = scan_request
        if caller is None and request is None:
            invoke = build_paper_demo_path_a_invoke(
                instrument,
                mode=mode_n,
                as_of_time_ns=as_of,
                quote_event=event,
                preregistration_path=self.preregistration_path,
                forecast_path=self.forecast_path,
            )
            caller = invoke.caller
            request = invoke.scan_request
        if caller is not None and request is not None:
            try:
                path_a = caller.run(request)
            except PathAScanCallerError as exc:
                if "LIVE" in str(exc):
                    return self._finish(
                        STATUS_LIVE_FORBIDDEN,
                        mode=mode_n,
                        instrument=instrument,
                        reasons=("LIVE_SCAN_CALLER_FORBIDDEN",),
                        provider_id=provider_id,
                        timeliness=timeliness,
                        source=source,
                        evaluation=evaluation,
                        selection=selection,
                        as_of=as_of,
                    )
                raise
            status = path_a.status if not fail_closed_for_actionable(evaluation) else STATUS_G7_NOT_ACTIONABLE
            if path_a.status == "EMPTY" and not fail_closed_for_actionable(evaluation):
                status = STATUS_EMPTY
            if path_a.status == "MINTED" and not fail_closed_for_actionable(evaluation):
                status = STATUS_MINTED
            reasons = tuple(dict.fromkeys((*reasons, *path_a.reason_codes)))
        payload = merge_freshness_into_payload(
            {
                "instrument_id": instrument,
                "provider_id": provider_id,
                "opportunity_id": None if path_a is None or not path_a.opportunities else path_a.opportunities[0].opportunity_id,
            },
            evaluation,
        )
        result = PathAProspectiveResult(
            status=status,
            mode=mode_n,
            provider_id=provider_id,
            instrument_id=instrument,
            reason_codes=tuple(reasons) if isinstance(reasons, tuple) else tuple(reasons),
            timeliness=timeliness,
            source=source,
            freshness=evaluation.to_dict(),
            provenance={
                "provider": provider_id,
                "provider_feed": provider_id,
                "instrument": instrument,
                "asset_class": "EQUITY",
                "event_time_ns": event.get("clocks", {}).get("event_time_ns") if isinstance(event.get("clocks"), dict) else None,
                "receive_time_ns": event.get("clocks", {}).get("received_time_ns") if isinstance(event.get("clocks"), dict) else None,
                "evaluation_time_ns": as_of,
                "realtime_delayed_eod": timeliness,
                "sequence": event.get("sequence"),
                "normalization_version": event.get("normalization_version"),
            },
            selection=selection,
            path_a=path_a,
            freshness_payload=payload,
        )
        return self._persist_minted(result, evaluation=evaluation, as_of=as_of, event=event)

    def _stamp_runtime(self, provider_id: str, timeliness: str) -> None:
        delay = timeliness == "DELAYED"
        self.composition.capability_registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=provider_id,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.DELAYED if delay else EntitlementState.ENTITLED,
                timeliness=DataTimeliness.DELAYED if delay else DataTimeliness.REAL_TIME,
                live_verified=False,
                notes="PATH_A_ONE_SHOT",
            )
        )
        self.composition.active_provider_id = provider_id

    def _persist_minted(
        self,
        result: PathAProspectiveResult,
        *,
        evaluation: OpportunityFreshnessResult,
        as_of: int,
        event: Mapping[str, Any],
    ) -> PathAProspectiveResult:
        from market_platform_foundation.intelligence.contracts.common import OpportunitySide
        from market_platform_foundation.intelligence.paper_forward_bridge import ForwardTestMode
        from market_platform_foundation.local_state.paths import persistence_enabled

        if result.status != STATUS_MINTED or result.path_a is None or not result.path_a.opportunities:
            return _result_with_persist(result, PERSIST_NOT_MINTED, None)
        if result.mode != "paper":
            return _result_with_persist(result, PERSIST_INTENTIONAL_EPHEMERAL, None)
        if not persistence_enabled():
            return _result_with_persist(result, PERSIST_INTENTIONAL_EPHEMERAL, None)
        if self.persist is None:
            return _result_with_persist(result, PERSIST_SKIPPED_NO_SESSION, None)
        opportunity = result.path_a.opportunities[0]
        side = opportunity.side
        if side == OpportunitySide.SHORT:
            direction = "SELL"
        else:
            direction = "BUY"
        clocks = event.get("clocks") if isinstance(event.get("clocks"), dict) else {}
        source_time_ns = clocks.get("event_time_ns")
        if not isinstance(source_time_ns, int) or source_time_ns > as_of:
            source_time_ns = as_of
        payload = merge_freshness_into_payload(
            {
                "instrument_id": result.instrument_id,
                "opportunity_id": opportunity.opportunity_id,
                "path_a_status": result.status,
                "provider_id": result.provider_id,
                "signal_id": result.path_a.scan_id,
            },
            evaluation,
        )
        decision = self.persist.service.create_decision(
            account_id=self.persist.account_id,
            mode="PAPER",
            session_id=self.persist.session_id,
            symbol=result.instrument_id,
            direction=direction,
            decision_time_ns=as_of,
            source_time_ns=source_time_ns,
            strategy_id=self.persist.strategy_id,
            strategy_version=self.persist.strategy_version,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
            decision_payload=payload,
            research_artifact_ref=opportunity.opportunity_id,
        )
        return _result_with_persist(result, PERSIST_WRITTEN, decision.forward_test_id)

    def _finish(
        self,
        status: str,
        *,
        mode: str,
        instrument: str,
        reasons: tuple[str, ...],
        provider_id: str = "",
        timeliness: str = "UNKNOWN",
        source: str = DELAYED_SOURCE,
        evaluation: OpportunityFreshnessResult | None = None,
        selection: Mapping[str, Any] | None = None,
        as_of: int | None = None,
        extra_provenance: Mapping[str, Any] | None = None,
    ) -> PathAProspectiveResult:
        if evaluation is None:
            evaluation = evaluate_opportunity_freshness(
                source=source,
                as_of_time_ns=as_of,
                policy=self.freshness_policy,
                runtime_capability={"timeliness": timeliness, "entitlement": "UNKNOWN", "runtime_state": "UNAVAILABLE"},
            )
        provenance = {"provider": provider_id, "instrument": instrument}
        if extra_provenance:
            provenance.update(dict(extra_provenance))
        return PathAProspectiveResult(
            status=status,
            mode=mode,
            provider_id=provider_id,
            instrument_id=instrument,
            reason_codes=reasons,
            timeliness=timeliness,
            source=source,
            freshness=evaluation.to_dict(),
            provenance=dict(provenance),
            selection=dict(selection or {}),
            path_a=None,
            freshness_payload=merge_freshness_into_payload({"instrument_id": instrument}, evaluation),
            persist_status=PERSIST_NOT_MINTED,
            forward_test_id=None,
        )


def _result_with_persist(
    result: PathAProspectiveResult,
    persist_status: str,
    forward_test_id: str | None,
) -> PathAProspectiveResult:
    return PathAProspectiveResult(
        status=result.status,
        mode=result.mode,
        provider_id=result.provider_id,
        instrument_id=result.instrument_id,
        reason_codes=result.reason_codes,
        timeliness=result.timeliness,
        source=result.source,
        freshness=result.freshness,
        provenance=result.provenance,
        selection=result.selection,
        path_a=result.path_a,
        freshness_payload=result.freshness_payload,
        persist_status=persist_status,
        forward_test_id=forward_test_id,
    )


__all__ = [
    "DELAYED_SOURCE",
    "LIVE_OBSERVED_SOURCE",
    "PERSIST_INTENTIONAL_EPHEMERAL",
    "PERSIST_NOT_MINTED",
    "PERSIST_SKIPPED_NO_SESSION",
    "PERSIST_WRITTEN",
    "PathAHonestyInvoke",
    "PathAPersistContext",
    "PathAProspectiveComposer",
    "PathAProspectiveResult",
    "build_paper_demo_path_a_invoke",
]
