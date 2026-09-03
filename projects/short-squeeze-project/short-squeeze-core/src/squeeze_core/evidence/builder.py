from collections.abc import Iterable
from datetime import datetime, timedelta
from itertools import combinations

from squeeze_core.contracts import (
    BarPayload,
    Completeness,
    DataFreshness,
    EventType,
    NewsItemPayload,
    Observation,
    PublishedShortInterestPayload,
    QualityState,
    SecFilingPayload,
    TradingHaltPayload,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .models import (
    CompletenessSummary,
    CoverageDomain,
    CoverageState,
    EvidenceDiagnostic,
    EvidenceDiagnosticCode,
    EvidenceSeverity,
    FreshnessSummary,
    HaltState,
    HaltStateSummary,
    NewsRelationship,
    NewsRelationshipKind,
    ObservationAge,
    PointInTimeEvidenceBundle,
    RevisionRelationship,
    SourceCoverage,
)
from .policy import PointInTimeEvidencePolicy
from .conflicts import build_conflicts


_PHASE_1C_DOMAIN_EVENTS = (
    (CoverageDomain.CANDIDATE_SNAPSHOT, EventType.MARKET_SNAPSHOT),
    (CoverageDomain.BORROW_FEE, EventType.BORROW_FEE),
    (CoverageDomain.BORROW_AVAILABILITY, EventType.BORROW_AVAILABILITY),
)


def _is_short_interest(observation: Observation) -> bool:
    return observation.event_type is EventType.PUBLISHED_SHORT_INTEREST


def _is_sec_filing(observation: Observation) -> bool:
    return observation.event_type is EventType.SEC_FILING


def _is_trading_halt(observation: Observation) -> bool:
    return observation.event_type is EventType.TRADING_HALT


def _is_news(observation: Observation) -> bool:
    return observation.event_type is EventType.NEWS_ITEM


def _is_market_bar(observation: Observation) -> bool:
    return observation.event_type is EventType.BAR


def _is_trade(observation: Observation) -> bool:
    return observation.event_type is EventType.TRADE


def _is_quote(observation: Observation) -> bool:
    return observation.event_type is EventType.QUOTE


def _is_trade_quote(observation: Observation) -> bool:
    return _is_trade(observation) or _is_quote(observation)


def _structured_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


_HALT_STATE_BY_STATUS = {
    "HALT_ANNOUNCED": HaltState.HALT_ANNOUNCED,
    "HALT_ACTIVE": HaltState.HALTED,
    "QUOTE_RESUMPTION_SCHEDULED": HaltState.QUOTE_RESUMPTION_SCHEDULED,
    "QUOTE_RESUMED": HaltState.QUOTES_RESUMED,
    "TRADE_RESUMPTION_SCHEDULED": HaltState.TRADE_RESUMPTION_SCHEDULED,
    "TRADING_RESUMED": HaltState.TRADING_RESUMED,
    "HALT_CANCELLED": HaltState.CANCELLED,
    "UNKNOWN": HaltState.UNKNOWN,
}


def derive_halt_state(
    observations: Iterable[Observation],
    conflict_ids: Iterable[str] = (),
) -> HaltStateSummary:
    halts = sorted(
        (item for item in observations if _is_trading_halt(item)),
        key=observation_order_key,
    )
    if not halts:
        return HaltStateSummary(state=HaltState.NOT_OBSERVED)
    event_keys = tuple(
        sorted(
            {
                str(
                    item.provenance.provider_metadata.get(
                        "halt_event_key", f"observation:{item.observation_id}"
                    )
                )
                for item in halts
            }
        )
    )
    conflicts = tuple(sorted(set(conflict_ids)))
    if conflicts or any(item.quality.state is QualityState.CONFLICTED for item in halts):
        return HaltStateSummary(
            state=HaltState.CONFLICTED,
            halt_event_keys=event_keys,
            supporting_observation_ids=tuple(item.observation_id for item in halts),
            conflict_ids=conflicts,
        )
    latest = halts[-1]
    latest_key = str(
        latest.provenance.provider_metadata.get(
            "halt_event_key", f"observation:{latest.observation_id}"
        )
    )
    supporting = tuple(
        item.observation_id
        for item in halts
        if str(
            item.provenance.provider_metadata.get(
                "halt_event_key", f"observation:{item.observation_id}"
            )
        )
        == latest_key
    )
    state = _HALT_STATE_BY_STATUS.get(latest.payload.halt_status, HaltState.UNKNOWN)
    return HaltStateSummary(
        state=state,
        halt_event_keys=event_keys,
        supporting_observation_ids=supporting,
    )


def _diagnostic(
    code: EvidenceDiagnosticCode,
    severity: EvidenceSeverity,
    message: str,
    observation: Observation | None = None,
    domain: CoverageDomain | None = None,
) -> EvidenceDiagnostic:
    return EvidenceDiagnostic(
        code=code,
        severity=severity,
        message=message,
        observation_id=None if observation is None else observation.observation_id,
        domain=domain,
    )


def _coverage_state(
    items: list[Observation], stale_ids: set[str], conflict_ids: set[str]
) -> CoverageState:
    if not items:
        return CoverageState.MISSING
    if any(
        item.quality.state is QualityState.CONFLICTED
        or item.observation_id in conflict_ids
        for item in items
    ):
        return CoverageState.CONFLICTED
    if any(item.quality.state is QualityState.INVALID for item in items):
        return CoverageState.INVALID
    if any(item.observation_id in stale_ids for item in items):
        return CoverageState.STALE
    if any(
        item.data_freshness is DataFreshness.DELAYED
        or item.quality.state is QualityState.DELAYED
        for item in items
    ):
        return CoverageState.DELAYED
    if any(item.data_freshness is DataFreshness.UNKNOWN for item in items):
        return CoverageState.UNKNOWN_FRESHNESS
    return CoverageState.PRESENT


_NEWS_RELATIONSHIP_KIND = {
    "UPDATED": NewsRelationshipKind.REVISION,
    "CORRECTED": NewsRelationshipKind.CORRECTION,
    "WITHDRAWN": NewsRelationshipKind.WITHDRAWAL,
    "DELETED": NewsRelationshipKind.DELETION,
}


def _news_relationship(
    kind: NewsRelationshipKind,
    left: Observation,
    right: Observation,
    canonical_url: str | None,
) -> NewsRelationship:
    ordered = sorted((left, right), key=lambda item: item.observation_id)
    seed = {
        "kind": kind,
        "observation_ids": tuple(item.observation_id for item in ordered),
        "canonical_url": canonical_url,
    }
    return NewsRelationship(
        relationship_id=f"news-relationship-{canonical_hash(seed)[:24]}",
        kind=kind,
        observation_ids=(ordered[0].observation_id, ordered[1].observation_id),
        provider_record_ids=(ordered[0].source_record_id, ordered[1].source_record_id),
        canonical_url=canonical_url,
    )


def build_news_relationships(
    observations: Iterable[Observation],
) -> tuple[NewsRelationship, ...]:
    news = sorted(
        (item for item in observations if _is_news(item)), key=observation_order_key
    )
    by_source_id = {item.source_record_id: item for item in news}
    by_observation_id = {item.observation_id: item for item in news}
    relationships: list[NewsRelationship] = []
    linked_pairs: set[frozenset[str]] = set()

    for observation in news:
        metadata = observation.provenance.provider_metadata
        kind = _NEWS_RELATIONSHIP_KIND.get(str(metadata.get("status")))
        if kind is None:
            continue
        prior = None
        supersedes = metadata.get("supersedes_provider_record_id")
        if supersedes is not None:
            prior = by_source_id.get(str(supersedes))
        if prior is None and observation.parent_observation_ids:
            prior = by_observation_id.get(observation.parent_observation_ids[0])
        if prior is None:
            prior_url = metadata.get("prior_canonical_url")
            if prior_url:
                prior = next(
                    (
                        item
                        for item in news
                        if item is not observation
                        and item.provenance.provider == observation.provenance.provider
                        and item.payload.url == prior_url
                    ),
                    None,
                )
        if prior is None:
            continue
        relationships.append(
            _news_relationship(kind, prior, observation, observation.payload.url)
        )
        linked_pairs.add(frozenset((prior.observation_id, observation.observation_id)))

    by_url: dict[str, list[Observation]] = {}
    for observation in news:
        if observation.payload.url:
            by_url.setdefault(observation.payload.url, []).append(observation)
    for canonical_url in sorted(by_url):
        for left, right in combinations(by_url[canonical_url], 2):
            pair = frozenset((left.observation_id, right.observation_id))
            if pair in linked_pairs or left.provenance.provider == right.provenance.provider:
                continue
            relationships.append(
                _news_relationship(
                    NewsRelationshipKind.SYNDICATED, left, right, canonical_url
                )
            )

    relationships.sort(
        key=lambda item: (
            min(
                next(
                    observation.effective_timestamp
                    for observation in news
                    if observation.observation_id == observation_id
                )
                for observation_id in item.observation_ids
            ),
            item.kind.value,
            item.observation_ids,
            item.relationship_id,
        )
    )
    return tuple(relationships)


def build_point_in_time_evidence(
    symbol: str,
    observations: Iterable[Observation],
    policy: PointInTimeEvidencePolicy,
) -> PointInTimeEvidenceBundle:
    normalized_symbol = symbol.strip().upper()
    ordered_input = sorted(tuple(observations), key=observation_order_key)
    included: list[Observation] = []
    diagnostics: list[EvidenceDiagnostic] = []
    stale_ids: set[str] = set()
    observation_ages: list[ObservationAge] = []
    future_boundary = policy.as_of + timedelta(milliseconds=policy.maximum_future_skew_ms)
    short_interest_domain_active = (
        policy.include_published_short_interest_domain
        or any(_is_short_interest(item) for item in ordered_input)
    )
    sec_domain_active = policy.include_sec_filings_domain or any(
        _is_sec_filing(item) for item in ordered_input
    )
    halt_domain_active = policy.include_trading_halts_domain or any(
        _is_trading_halt(item) for item in ordered_input
    )
    news_domain_active = policy.include_news_domain or any(
        _is_news(item) for item in ordered_input
    )
    market_bars_domain_active = policy.include_market_bars_domain or any(
        _is_market_bar(item) for item in ordered_input
    )
    trades_domain_active = policy.include_trades_domain or any(
        _is_trade(item) for item in ordered_input
    )
    quotes_domain_active = policy.include_quotes_domain or any(
        _is_quote(item) for item in ordered_input
    )

    for observation in ordered_input:
        if _is_news(observation):
            associated = (
                observation.payload.associated_symbols
                if isinstance(observation.payload, NewsItemPayload)
                else ()
            )
            if normalized_symbol not in associated:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_NEWS_SYMBOL_NOT_ASSOCIATED,
                        EvidenceSeverity.INFO,
                        "News observation has no explicit association with the requested symbol.",
                        observation,
                        CoverageDomain.NEWS,
                    )
                )
                continue
        elif observation.symbol != normalized_symbol:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_SYMBOL_MISMATCH,
                    EvidenceSeverity.INFO,
                    "Observation symbol does not match the requested bundle symbol.",
                    observation,
                )
            )
            continue
        if _is_trade_quote(observation) and observation.source_timestamp > policy.as_of:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_NOT_YET_PUBLISHED,
                    EvidenceSeverity.WARNING,
                    "Trade/quote record was not provider-available at as-of.",
                    observation,
                    CoverageDomain.TRADES if _is_trade(observation) else CoverageDomain.QUOTES,
                )
            )
            if str(observation.provenance.provider_metadata.get("status")) not in {"ORIGINAL", "UNKNOWN"}:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_REVISION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later trade/quote lifecycle record was not yet provider-available.",
                        observation,
                        CoverageDomain.TRADES if _is_trade(observation) else CoverageDomain.QUOTES,
                    )
                )
            continue
        if _is_market_bar(observation) and observation.source_timestamp > policy.as_of:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_BAR_NOT_YET_PUBLISHED,
                    EvidenceSeverity.WARNING,
                    "Market-bar record was not yet provider-published at as-of.",
                    observation,
                    CoverageDomain.MARKET_BARS,
                )
            )
            if str(observation.provenance.provider_metadata.get("status")) == "CORRECTED":
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_BAR_CORRECTION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later market-bar correction was not yet provider-available.",
                        observation,
                        CoverageDomain.MARKET_BARS,
                    )
                )
            continue
        if _is_news(observation) and observation.source_timestamp > policy.as_of:
            basis = str(
                observation.provenance.provider_metadata.get("availability_basis", "")
            )
            diagnostics.append(
                _diagnostic(
                    (
                        EvidenceDiagnosticCode.EVIDENCE_NEWS_NOT_YET_PUBLISHED
                        if basis == "PUBLICATION_TIMESTAMP"
                        else EvidenceDiagnosticCode.EVIDENCE_NEWS_NOT_YET_AVAILABLE
                    ),
                    EvidenceSeverity.WARNING,
                    "News record was not yet available from the provider at as-of.",
                    observation,
                    CoverageDomain.NEWS,
                )
            )
            if str(observation.provenance.provider_metadata.get("status")) != "ORIGINAL":
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_NEWS_UPDATE_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later news lifecycle record was not yet provider-available.",
                        observation,
                        CoverageDomain.NEWS,
                    )
                )
            continue
        if _is_short_interest(observation) and observation.source_timestamp > policy.as_of:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_NOT_YET_PUBLISHED,
                    EvidenceSeverity.WARNING,
                    "Published short interest was not yet available from the source at as-of.",
                    observation,
                    CoverageDomain.PUBLISHED_SHORT_INTEREST,
                )
            )
            revision_status = observation.provenance.provider_metadata.get(
                "revision_status"
            )
            if str(revision_status) in {"CORRECTED", "REVISED"}:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_REVISION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later short-interest revision was not yet published.",
                        observation,
                        CoverageDomain.PUBLISHED_SHORT_INTEREST,
                    )
                )
            continue
        if _is_sec_filing(observation) and observation.source_timestamp > policy.as_of:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_NOT_YET_ACCEPTED,
                    EvidenceSeverity.WARNING,
                    "SEC filing was not yet publicly available at as-of.",
                    observation,
                    CoverageDomain.SEC_FILINGS,
                )
            )
            if observation.provenance.provider_metadata.get("is_amendment"):
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_AMENDMENT_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later filing amendment was not yet publicly available.",
                        observation,
                        CoverageDomain.SEC_FILINGS,
                    )
                )
            continue
        if _is_trading_halt(observation) and observation.source_timestamp > policy.as_of:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_HALT_NOT_YET_PUBLISHED,
                    EvidenceSeverity.WARNING,
                    "Trading-halt announcement was not yet publicly available at as-of.",
                    observation,
                    CoverageDomain.TRADING_HALTS,
                )
            )
            if str(
                observation.provenance.provider_metadata.get("revision_status")
            ) not in {"ORIGINAL", "UNKNOWN", "None"}:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_HALT_REVISION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later halt lifecycle update was not yet public.",
                        observation,
                        CoverageDomain.TRADING_HALTS,
                    )
                )
            continue
        if observation.received_timestamp > policy.as_of:
            code = (
                EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_NOT_YET_RECEIVED
                if _is_short_interest(observation)
                else (
                    EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_NOT_YET_RECEIVED
                    if _is_sec_filing(observation)
                    else EvidenceDiagnosticCode.EVIDENCE_HALT_NOT_YET_RECEIVED
                    if _is_trading_halt(observation)
                    else EvidenceDiagnosticCode.EVIDENCE_NEWS_NOT_YET_RECEIVED
                    if _is_news(observation)
                    else EvidenceDiagnosticCode.EVIDENCE_BAR_NOT_YET_RECEIVED
                    if _is_market_bar(observation)
                    else EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_NOT_YET_RECEIVED
                    if _is_trade_quote(observation)
                    else EvidenceDiagnosticCode.EVIDENCE_EXCLUDED_RECEIVED_AFTER_AS_OF
                )
            )
            diagnostics.append(
                _diagnostic(
                    code,
                    EvidenceSeverity.WARNING,
                    "Observation was first received after the bundle as-of time.",
                    observation,
                    (
                        CoverageDomain.PUBLISHED_SHORT_INTEREST
                        if _is_short_interest(observation)
                        else CoverageDomain.SEC_FILINGS
                        if _is_sec_filing(observation)
                        else CoverageDomain.TRADING_HALTS
                        if _is_trading_halt(observation)
                        else CoverageDomain.NEWS
                        if _is_news(observation)
                        else CoverageDomain.MARKET_BARS
                        if _is_market_bar(observation)
                        else CoverageDomain.TRADES
                        if _is_trade(observation)
                        else CoverageDomain.QUOTES
                        if _is_quote(observation)
                        else None
                    ),
                )
            )
            if _is_short_interest(observation):
                revision_status = observation.provenance.provider_metadata.get(
                    "revision_status"
                )
                if str(revision_status) in {"CORRECTED", "REVISED"}:
                    diagnostics.append(
                        _diagnostic(
                            EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_REVISION_NOT_YET_AVAILABLE,
                            EvidenceSeverity.INFO,
                            "A later short-interest revision had not yet been received.",
                            observation,
                            CoverageDomain.PUBLISHED_SHORT_INTEREST,
                        )
                    )
            if _is_sec_filing(observation) and observation.provenance.provider_metadata.get("is_amendment"):
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_AMENDMENT_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later filing amendment had not yet been received.",
                        observation,
                        CoverageDomain.SEC_FILINGS,
                    )
                )
            if _is_trading_halt(observation) and str(
                observation.provenance.provider_metadata.get("revision_status")
            ) not in {"ORIGINAL", "UNKNOWN", "None"}:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_HALT_REVISION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later halt lifecycle update had not yet been received.",
                        observation,
                        CoverageDomain.TRADING_HALTS,
                    )
                )
            if _is_news(observation) and str(
                observation.provenance.provider_metadata.get("status")
            ) != "ORIGINAL":
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_NEWS_UPDATE_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later news lifecycle record had not yet been received.",
                        observation,
                        CoverageDomain.NEWS,
                    )
                    )
            if _is_market_bar(observation) and str(
                observation.provenance.provider_metadata.get("status")
            ) == "CORRECTED":
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_BAR_CORRECTION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later market-bar correction had not yet been received.",
                        observation,
                        CoverageDomain.MARKET_BARS,
                    )
                )
            if _is_trade_quote(observation) and str(
                observation.provenance.provider_metadata.get("status")
            ) not in {"ORIGINAL", "UNKNOWN"}:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_REVISION_NOT_YET_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A later trade/quote lifecycle record had not yet been received.",
                        observation,
                        CoverageDomain.TRADES if _is_trade(observation) else CoverageDomain.QUOTES,
                    )
                )
            continue
        if observation.effective_timestamp > future_boundary:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_EXCLUDED_AFTER_AS_OF,
                    EvidenceSeverity.WARNING,
                    "Observation effective time is after the permitted as-of boundary.",
                    observation,
                )
            )
            continue
        if _is_trade_quote(observation):
            event_timestamp = _structured_datetime(
                observation.provenance.provider_metadata.get("event_timestamp")
            )
            if event_timestamp is not None and event_timestamp > policy.as_of:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_FUTURE_EVENT,
                        EvidenceSeverity.WARNING,
                        "Trade/quote event time is after as-of and is not included early.",
                        observation,
                        CoverageDomain.TRADES if _is_trade(observation) else CoverageDomain.QUOTES,
                    )
                )
                continue

        maximum_age = policy.maximum_age_ms_by_event_type.get(observation.event_type)
        age_ms = max(
            0,
            int((policy.as_of - observation.effective_timestamp).total_seconds() * 1000),
        )
        stale = maximum_age is not None and age_ms > maximum_age
        reporting_period_age_days: int | None = None
        filing_age_ms: int | None = None
        announcement_age_ms: int | None = None
        halt_event_age_ms: int | None = None
        resumption_event_age_ms: int | None = None
        publication_age_ms: int | None = None
        update_age_ms: int | None = None
        capture_age_ms: int | None = None
        interval_age_ms: int | None = None
        correction_age_ms: int | None = None
        event_age_ms: int | None = None
        reporting_period_stale = False
        if _is_short_interest(observation) and isinstance(
            observation.payload, PublishedShortInterestPayload
        ):
            if observation.payload.settlement_date is not None:
                reporting_period_age_days = max(
                    0,
                    (policy.as_of.date() - observation.payload.settlement_date).days,
                )
                reporting_period_stale = (
                    policy.maximum_reporting_period_age_days is not None
                    and reporting_period_age_days
                    > policy.maximum_reporting_period_age_days
                )
        if _is_sec_filing(observation) and isinstance(
            observation.payload, SecFilingPayload
        ):
            filing_age_ms = max(
                0,
                int((policy.as_of - observation.source_timestamp).total_seconds() * 1000),
            )
            if observation.payload.period_of_report is not None:
                reporting_period_age_days = max(
                    0,
                    (policy.as_of.date() - observation.payload.period_of_report).days,
                )
        if _is_trading_halt(observation) and isinstance(
            observation.payload, TradingHaltPayload
        ):
            announcement_age_ms = max(
                0,
                int((policy.as_of - observation.source_timestamp).total_seconds() * 1000),
            )
            if observation.payload.halt_time is not None:
                halt_event_age_ms = max(
                    0,
                    int((policy.as_of - observation.payload.halt_time).total_seconds() * 1000),
                )
            if observation.payload.resume_time is not None:
                resumption_event_age_ms = max(
                    0,
                    int((policy.as_of - observation.payload.resume_time).total_seconds() * 1000),
                )
        if _is_news(observation) and isinstance(observation.payload, NewsItemPayload):
            if observation.payload.published_at is not None:
                publication_age_ms = max(
                    0,
                    int(
                        (policy.as_of - observation.payload.published_at).total_seconds()
                        * 1000
                    ),
                )
            updated_at = observation.provenance.provider_metadata.get("updated_at")
            if isinstance(updated_at, datetime):
                update_age_ms = max(
                    0, int((policy.as_of - updated_at).total_seconds() * 1000)
                )
            captured_at = observation.provenance.provider_metadata.get(
                "capture_timestamp"
            )
            if isinstance(captured_at, datetime):
                capture_age_ms = max(
                    0, int((policy.as_of - captured_at).total_seconds() * 1000)
                )
        if _is_market_bar(observation) and isinstance(observation.payload, BarPayload):
            metadata = observation.provenance.provider_metadata
            bar_end = metadata.get("bar_end")
            if isinstance(bar_end, datetime):
                interval_age_ms = max(
                    0, int((policy.as_of - bar_end).total_seconds() * 1000)
                )
            publication_age_ms = max(
                0, int((policy.as_of - observation.source_timestamp).total_seconds() * 1000)
            )
            captured_at = metadata.get("capture_timestamp")
            if isinstance(captured_at, datetime):
                capture_age_ms = max(
                    0, int((policy.as_of - captured_at).total_seconds() * 1000)
                )
            if str(metadata.get("status")) == "CORRECTED":
                correction_age_ms = age_ms
        if _is_trade_quote(observation):
            metadata = observation.provenance.provider_metadata
            event_timestamp = _structured_datetime(metadata.get("event_timestamp"))
            if event_timestamp is not None:
                event_age_ms = max(
                    0, int((policy.as_of - event_timestamp).total_seconds() * 1000)
                )
            publication_age_ms = max(
                0, int((policy.as_of - observation.source_timestamp).total_seconds() * 1000)
            )
            captured_at = _structured_datetime(metadata.get("capture_timestamp"))
            if captured_at is not None:
                capture_age_ms = max(
                    0, int((policy.as_of - captured_at).total_seconds() * 1000)
                )
            if str(metadata.get("status")) in {"CORRECTED", "CANCELLED", "DELETED"}:
                correction_age_ms = age_ms
        stale = stale or reporting_period_stale
        if stale:
            if not policy.allow_stale:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_POLICY_EXCLUDED,
                        EvidenceSeverity.WARNING,
                        "Stale observation was excluded by evidence policy.",
                        observation,
                    )
                )
                continue
            stale_ids.add(observation.observation_id)
            if reporting_period_stale:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_STALE_REPORTING_PERIOD,
                        EvidenceSeverity.WARNING,
                        "Short-interest settlement period exceeds the configured reporting-age threshold.",
                        observation,
                        CoverageDomain.PUBLISHED_SHORT_INTEREST,
                    )
                )
            else:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_STALE_SOURCE,
                        EvidenceSeverity.WARNING,
                        "Observation age exceeds the configured event-type threshold.",
                        observation,
                    )
                )
        elif (
            observation.data_freshness is DataFreshness.DELAYED
            or observation.quality.state is QualityState.DELAYED
        ):
            if not policy.allow_delayed:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_POLICY_EXCLUDED,
                        EvidenceSeverity.WARNING,
                        "Delayed observation was excluded by evidence policy.",
                        observation,
                    )
                )
                continue
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_DELAYED_SOURCE,
                    EvidenceSeverity.INFO,
                    "Delayed observation was retained by evidence policy.",
                    observation,
                )
            )
        elif observation.data_freshness is DataFreshness.UNKNOWN:
            if not policy.allow_unknown_freshness:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_POLICY_EXCLUDED,
                        EvidenceSeverity.WARNING,
                        "Unknown-freshness observation was excluded by evidence policy.",
                        observation,
                    )
                )
                continue
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_UNKNOWN_FRESHNESS,
                    EvidenceSeverity.INFO,
                    "Observation freshness is unknown; recent receipt does not prove live data.",
                    observation,
                )
            )
        included.append(observation)
        if _is_short_interest(observation) or _is_sec_filing(observation) or _is_trading_halt(observation) or _is_news(observation) or _is_market_bar(observation) or _is_trade_quote(observation):
            observation_ages.append(
                ObservationAge(
                    observation_id=observation.observation_id,
                    availability_age_ms=age_ms,
                    event_age_ms=event_age_ms,
                    reporting_period_age_days=reporting_period_age_days,
                    filing_age_ms=filing_age_ms,
                    announcement_age_ms=announcement_age_ms,
                    halt_event_age_ms=halt_event_age_ms,
                    resumption_event_age_ms=resumption_event_age_ms,
                    publication_age_ms=publication_age_ms,
                    update_age_ms=update_age_ms,
                    capture_age_ms=capture_age_ms,
                    interval_age_ms=interval_age_ms,
                    correction_age_ms=correction_age_ms,
                )
            )

    revision_relationships: list[RevisionRelationship] = []
    included_by_source_id = {item.source_record_id: item for item in included}
    included_by_observation_id = {item.observation_id: item for item in included}
    for observation in included:
        if not (
            _is_short_interest(observation)
            or _is_sec_filing(observation)
            or _is_trading_halt(observation)
            or _is_market_bar(observation)
            or _is_trade_quote(observation)
        ):
            continue
        metadata = observation.provenance.provider_metadata
        is_sec = _is_sec_filing(observation)
        is_halt = _is_trading_halt(observation)
        is_bar = _is_market_bar(observation)
        is_trade_quote = _is_trade_quote(observation)
        status = str(
            metadata.get("filing_status", "UNKNOWN")
            if is_sec
            else metadata.get("status", "UNKNOWN")
            if is_bar
            else metadata.get("status", "UNKNOWN")
            if is_trade_quote
            else metadata.get("revision_status", "UNKNOWN")
            if is_halt
            else metadata.get("revision_status", "UNKNOWN")
        )
        eligible_statuses = (
            {"AMENDED", "CORRECTED", "CANCELLED"}
            if is_sec
            else {"COMPLETED", "CORRECTED", "CANCELLED"}
            if is_bar
            else {"CORRECTED", "CANCELLED", "DELETED"}
            if is_trade_quote
            else {"UPDATED", "CORRECTED", "CANCELLED"}
            if is_halt
            else {"CORRECTED", "REVISED", "CANCELLED"}
        )
        if status not in eligible_statuses:
            continue
        supersedes = (
            metadata.get("amends_accession_number")
            if is_sec
            else metadata.get("supersedes_provider_record_id")
            if is_bar
            else metadata.get("supersedes_provider_record_id")
            if is_trade_quote
            else metadata.get("supersedes_source_record_id")
        )
        prior = (
            next(
                (
                    item
                    for item in included
                    if _is_sec_filing(item)
                    and item.payload.accession_number == str(supersedes)
                ),
                None,
            )
            if is_sec and supersedes is not None
            else included_by_source_id.get(str(supersedes))
            if supersedes is not None
            else None
        )
        if prior is None and observation.parent_observation_ids:
            prior = included_by_observation_id.get(observation.parent_observation_ids[0])
        if prior is None:
            diagnostics.append(
                _diagnostic(
                    (
                        EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_AMENDMENT_NOT_YET_AVAILABLE
                        if is_sec
                    else EvidenceDiagnosticCode.EVIDENCE_HALT_REVISION_NOT_YET_AVAILABLE
                    if is_halt
                    else EvidenceDiagnosticCode.EVIDENCE_BAR_CORRECTION_NOT_YET_AVAILABLE
                    if is_bar
                    else EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_REVISION_NOT_YET_AVAILABLE
                    if is_trade_quote
                    else EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_REVISION_NOT_YET_AVAILABLE
                    ),
                    EvidenceSeverity.INFO,
                    "Revision is eligible but its referenced prior observation is not in the bundle.",
                    observation,
                    CoverageDomain.SEC_FILINGS
                    if is_sec
                    else CoverageDomain.TRADING_HALTS
                    if is_halt
                    else CoverageDomain.MARKET_BARS
                    if is_bar
                    else CoverageDomain.TRADES
                    if _is_trade(observation)
                    else CoverageDomain.QUOTES
                    if _is_quote(observation)
                    else CoverageDomain.PUBLISHED_SHORT_INTEREST,
                )
            )
            continue
        relationship_seed = {
            "prior_observation_id": prior.observation_id,
            "revision_observation_id": observation.observation_id,
            "status": status,
        }
        revision_relationships.append(
            RevisionRelationship(
                relationship_id=f"revision-{canonical_hash(relationship_seed)[:24]}",
                prior_observation_id=prior.observation_id,
                revision_observation_id=observation.observation_id,
                status=status,
            )
        )
        if is_sec:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_AMENDMENT_AVAILABLE,
                    EvidenceSeverity.INFO,
                    "An immutable SEC filing amendment and its original are available.",
                    observation,
                    CoverageDomain.SEC_FILINGS,
                )
            )
        elif is_halt:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_HALT_REVISION_AVAILABLE,
                    EvidenceSeverity.INFO,
                    "An immutable halt lifecycle update and its prior record are available.",
                    observation,
                    CoverageDomain.TRADING_HALTS,
                )
            )
        elif is_bar:
            code = (
                EvidenceDiagnosticCode.EVIDENCE_BAR_COMPLETED
                if status == "COMPLETED"
                else EvidenceDiagnosticCode.EVIDENCE_BAR_CORRECTION_AVAILABLE
            )
            diagnostics.append(
                _diagnostic(
                    code,
                    EvidenceSeverity.INFO,
                    "An immutable market-bar lifecycle record and its prior record are available.",
                    observation,
                    CoverageDomain.MARKET_BARS,
                )
            )
        elif is_trade_quote:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_REVISION_AVAILABLE,
                    EvidenceSeverity.INFO,
                    "An immutable trade/quote lifecycle record and its prior record are available.",
                    observation,
                    CoverageDomain.TRADES if _is_trade(observation) else CoverageDomain.QUOTES,
                )
            )
        else:
            diagnostics.extend(
                [
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_CORRECTION_AVAILABLE,
                        EvidenceSeverity.INFO,
                        "A published short-interest correction or revision is available.",
                        observation,
                        CoverageDomain.PUBLISHED_SHORT_INTEREST,
                    ),
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_REVISION_SUPERSEDES,
                        EvidenceSeverity.INFO,
                        "Eligible revision supersedes a preserved prior observation.",
                        observation,
                        CoverageDomain.PUBLISHED_SHORT_INTEREST,
                    ),
                ]
            )
    revision_relationships.sort(
        key=lambda item: (
            item.prior_observation_id,
            item.revision_observation_id,
            item.status,
            item.relationship_id,
        )
    )

    news_relationships = build_news_relationships(included)
    for relationship in news_relationships:
        related = next(
            item
            for item in included
            if item.observation_id == relationship.observation_ids[-1]
        )
        if relationship.kind is NewsRelationshipKind.SYNDICATED:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_NEWS_SYNDICATION,
                    EvidenceSeverity.INFO,
                    "Independent providers supplied the same sanitized canonical URL.",
                    related,
                    CoverageDomain.NEWS,
                )
            )
        elif relationship.kind is NewsRelationshipKind.WITHDRAWAL:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_NEWS_WITHDRAWAL_AVAILABLE,
                    EvidenceSeverity.INFO,
                    "An immutable news withdrawal and its prior record are available.",
                    related,
                    CoverageDomain.NEWS,
                )
            )
        else:
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_NEWS_UPDATE_AVAILABLE,
                    EvidenceSeverity.INFO,
                    "An immutable news lifecycle update and its prior record are available.",
                    related,
                    CoverageDomain.NEWS,
                )
            )

    conflicts = build_conflicts(included, policy)
    conflict_ids = {
        observation_id
        for conflict in conflicts
        if conflict.classification.value != "TEMPORAL_DIFFERENCE"
        for observation_id in conflict.observation_ids
    }
    halt_conflict_ids = tuple(
        conflict.conflict_id
        for conflict in conflicts
        if conflict.semantic_field.startswith("halt_")
        and conflict.classification.value != "TEMPORAL_DIFFERENCE"
    )
    halt_state = derive_halt_state(included, halt_conflict_ids) if halt_domain_active else None
    if halt_state is not None:
        state_diagnostics = {
            HaltState.HALTED: EvidenceDiagnosticCode.EVIDENCE_HALT_ACTIVE,
            HaltState.QUOTE_RESUMPTION_SCHEDULED: EvidenceDiagnosticCode.EVIDENCE_QUOTE_RESUMPTION_SCHEDULED,
            HaltState.QUOTES_RESUMED: EvidenceDiagnosticCode.EVIDENCE_QUOTES_RESUMED,
            HaltState.TRADE_RESUMPTION_SCHEDULED: EvidenceDiagnosticCode.EVIDENCE_TRADE_RESUMPTION_SCHEDULED,
            HaltState.TRADING_RESUMED: EvidenceDiagnosticCode.EVIDENCE_TRADING_RESUMED,
            HaltState.CONFLICTED: EvidenceDiagnosticCode.EVIDENCE_HALT_CONFLICT,
        }
        state_code = state_diagnostics.get(halt_state.state)
        if state_code is not None:
            diagnostics.append(
                _diagnostic(
                    state_code,
                    EvidenceSeverity.ERROR if halt_state.state is HaltState.CONFLICTED else EvidenceSeverity.INFO,
                    f"Objective halt state at as-of is {halt_state.state.value}.",
                    domain=CoverageDomain.TRADING_HALTS,
                )
            )
    for conflict in conflicts:
        short_interest_conflict = conflict.semantic_field.startswith("published_")
        sec_filing_conflict = conflict.semantic_field.startswith("sec_")
        halt_conflict = conflict.semantic_field.startswith("halt_")
        news_conflict = conflict.semantic_field.startswith("news_")
        bar_conflict = conflict.semantic_field.startswith("bar_")
        trade_conflict = conflict.semantic_field.startswith("trade_")
        quote_conflict = conflict.semantic_field.startswith("quote_")
        if conflict.classification.value == "VALUE_CONFLICT":
            code = (
                EvidenceDiagnosticCode.EVIDENCE_HALT_CONFLICT
                if halt_conflict
                else EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_CONFLICT
                if trade_conflict or quote_conflict
                else EvidenceDiagnosticCode.EVIDENCE_BAR_CONFLICT
                if bar_conflict
                else EvidenceDiagnosticCode.EVIDENCE_NEWS_CONFLICT
                if news_conflict
                else EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_CONFLICT
                if sec_filing_conflict
                else EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_PROVIDER_CONFLICT
                if short_interest_conflict
                else EvidenceDiagnosticCode.EVIDENCE_FIELD_CONFLICT
            )
            severity = EvidenceSeverity.ERROR
            message = "Compatible semantic values conflict; all observations were preserved."
        elif conflict.classification.value == "DUPLICATE_CONFLICT":
            code = (
                EvidenceDiagnosticCode.EVIDENCE_HALT_CONFLICT
                if halt_conflict
                else EvidenceDiagnosticCode.EVIDENCE_TRADE_QUOTE_CONFLICT
                if trade_conflict or quote_conflict
                else EvidenceDiagnosticCode.EVIDENCE_BAR_CONFLICT
                if bar_conflict
                else EvidenceDiagnosticCode.EVIDENCE_NEWS_CONFLICT
                if news_conflict
                else EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_CONFLICT
                if sec_filing_conflict
                else EvidenceDiagnosticCode.EVIDENCE_DUPLICATE_CONFLICT
            )
            severity = EvidenceSeverity.ERROR
            message = "Same-source duplicate evidence is inconsistent or redundant."
        else:
            code = (
                EvidenceDiagnosticCode.EVIDENCE_HALT_TEMPORAL_DIFFERENCE
                if halt_conflict
                else EvidenceDiagnosticCode.EVIDENCE_BAR_INTERVAL_MISMATCH
                if bar_conflict
                else EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_TEMPORAL_DIFFERENCE
                if sec_filing_conflict
                else EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_TEMPORAL_DIFFERENCE
                if short_interest_conflict
                else EvidenceDiagnosticCode.EVIDENCE_TEMPORAL_DIFFERENCE
            )
            severity = EvidenceSeverity.INFO
            message = "Compatible values come from different effective times."
        diagnostics.append(
            EvidenceDiagnostic(
                code=code,
                severity=severity,
                message=message,
                observation_id=conflict.observation_ids[0],
                domain=CoverageDomain.NEWS
                if news_conflict
                else CoverageDomain.MARKET_BARS
                if bar_conflict
                else CoverageDomain.TRADES
                if trade_conflict
                else CoverageDomain.QUOTES
                if quote_conflict
                else None,
            )
        )

    domain_events = list(_PHASE_1C_DOMAIN_EVENTS)
    if short_interest_domain_active:
        domain_events.append(
            (CoverageDomain.PUBLISHED_SHORT_INTEREST, EventType.PUBLISHED_SHORT_INTEREST)
        )
    if sec_domain_active:
        domain_events.append((CoverageDomain.SEC_FILINGS, EventType.SEC_FILING))
    if halt_domain_active:
        domain_events.append((CoverageDomain.TRADING_HALTS, EventType.TRADING_HALT))
    if news_domain_active:
        domain_events.append((CoverageDomain.NEWS, EventType.NEWS_ITEM))
    if market_bars_domain_active:
        domain_events.append((CoverageDomain.MARKET_BARS, EventType.BAR))
    if trades_domain_active:
        domain_events.append((CoverageDomain.TRADES, EventType.TRADE))
    if quotes_domain_active:
        domain_events.append((CoverageDomain.QUOTES, EventType.QUOTE))
    source_coverage: list[SourceCoverage] = []
    missing_domains = 0
    for domain, event_type in domain_events:
        items = [item for item in included if item.event_type is event_type]
        state = _coverage_state(items, stale_ids, conflict_ids)
        if (
            domain is CoverageDomain.SEC_FILINGS
            and state is CoverageState.PRESENT
            and any(item.quality.state is QualityState.MISSING for item in items)
        ):
            state = CoverageState.PARTIAL
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_PARTIAL_COVERAGE,
                    EvidenceSeverity.WARNING,
                    "Included SEC filing metadata is partial.",
                    domain=domain,
                )
            )
        if (
            domain is CoverageDomain.TRADING_HALTS
            and state is CoverageState.PRESENT
            and any(item.quality.state is QualityState.MISSING for item in items)
        ):
            state = CoverageState.PARTIAL
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_HALT_PARTIAL_COVERAGE,
                    EvidenceSeverity.WARNING,
                    "Included trading-halt metadata is partial.",
                    domain=domain,
                )
            )
        if (
            domain is CoverageDomain.NEWS
            and state is CoverageState.PRESENT
            and any(item.quality.state is QualityState.MISSING for item in items)
        ):
            state = CoverageState.PARTIAL
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_NEWS_PARTIAL_COVERAGE,
                    EvidenceSeverity.WARNING,
                    "Included objective news metadata is partial.",
                    domain=domain,
                )
            )
        if domain is CoverageDomain.MARKET_BARS and state is CoverageState.PRESENT:
            latest_by_boundary: dict[tuple[object, object, object], Observation] = {}
            for item in items:
                metadata = item.provenance.provider_metadata
                key = (item.payload.timeframe, metadata.get("bar_start"), metadata.get("bar_end"))
                latest_by_boundary[key] = item
            if any(
                str(item.provenance.provider_metadata.get("status")) in {"PARTIAL", "UNKNOWN"}
                for item in latest_by_boundary.values()
            ):
                state = CoverageState.PARTIAL
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_MARKET_BARS_PARTIAL_COVERAGE,
                        EvidenceSeverity.WARNING,
                        "Latest eligible market-bar evidence is partial or unknown.",
                        domain=domain,
                    )
                )
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_BAR_PARTIAL,
                        EvidenceSeverity.INFO,
                        "A partial market bar is the latest eligible lifecycle record.",
                        domain=domain,
                    )
                )
            elif items:
                diagnostics.append(
                    _diagnostic(
                        EvidenceDiagnosticCode.EVIDENCE_BAR_COMPLETED,
                        EvidenceSeverity.INFO,
                        "Completed or corrected market-bar evidence is eligible.",
                        domain=domain,
                    )
                )
        if (
            domain in {CoverageDomain.TRADES, CoverageDomain.QUOTES}
            and state is CoverageState.PRESENT
            and any(item.quality.completeness is Completeness.PARTIAL for item in items)
        ):
            state = CoverageState.PARTIAL
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_TRADES_PARTIAL_COVERAGE
                    if domain is CoverageDomain.TRADES
                    else EvidenceDiagnosticCode.EVIDENCE_QUOTES_PARTIAL_COVERAGE,
                    EvidenceSeverity.WARNING,
                    "Included trade/quote evidence has explicitly partial fields.",
                    domain=domain,
                )
            )
        if state is CoverageState.MISSING:
            missing_domains += 1
            diagnostics.append(
                _diagnostic(
                    EvidenceDiagnosticCode.EVIDENCE_MISSING_PUBLISHED_SHORT_INTEREST
                    if domain is CoverageDomain.PUBLISHED_SHORT_INTEREST
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_SEC_FILINGS
                    if domain is CoverageDomain.SEC_FILINGS
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_TRADING_HALTS
                    if domain is CoverageDomain.TRADING_HALTS
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_NEWS
                    if domain is CoverageDomain.NEWS
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_MARKET_BARS
                    if domain is CoverageDomain.MARKET_BARS
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_TRADES
                    if domain is CoverageDomain.TRADES
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_QUOTES
                    if domain is CoverageDomain.QUOTES
                    else EvidenceDiagnosticCode.EVIDENCE_MISSING_SOURCE_DOMAIN,
                    EvidenceSeverity.WARNING,
                    "No included observation covers this evidence domain.",
                    domain=domain,
                )
            )
        source_coverage.append(
            SourceCoverage(
                domain=domain,
                state=state,
                observation_ids=tuple(item.observation_id for item in items),
            )
        )
    if missing_domains:
        diagnostics.append(
            _diagnostic(
                EvidenceDiagnosticCode.EVIDENCE_PARTIAL_COVERAGE,
                EvidenceSeverity.WARNING,
                (
                    "The bundle has partial Phase 1G source-domain coverage."
                    if news_domain_active and not market_bars_domain_active
                    and not trades_domain_active and not quotes_domain_active
                    else "The bundle has partial Phase 1I source-domain coverage."
                    if trades_domain_active or quotes_domain_active
                    else "The bundle has partial Phase 1H source-domain coverage."
                    if market_bars_domain_active
                    else "The bundle has partial Phase 1F source-domain coverage."
                    if halt_domain_active
                    else "The bundle has partial Phase 1E source-domain coverage."
                    if sec_domain_active
                    else "The bundle has partial Phase 1D source-domain coverage."
                    if short_interest_domain_active
                    else "The bundle has partial Phase 1C source-domain coverage."
                ),
            )
        )

    diagnostics.sort(
        key=lambda item: (
            item.code.value,
            item.observation_id or "",
            "" if item.domain is None else item.domain.value,
            item.message,
        )
    )
    live_count = sum(item.data_freshness is DataFreshness.LIVE for item in included)
    delayed_count = sum(item.data_freshness is DataFreshness.DELAYED for item in included)
    historical_count = sum(item.data_freshness is DataFreshness.HISTORICAL for item in included)
    unknown_count = sum(item.data_freshness is DataFreshness.UNKNOWN for item in included)
    freshness = FreshnessSummary(
        live_count=live_count,
        delayed_count=delayed_count,
        historical_count=historical_count,
        unknown_count=unknown_count,
        stale_count=len(stale_ids),
    )
    completeness = CompletenessSummary(
        included_observation_count=len(included),
        excluded_observation_count=len(ordered_input) - len(included),
        present_domain_count=len(domain_events) - missing_domains,
        missing_domain_count=missing_domains,
    )
    preliminary = {
        "symbol": normalized_symbol,
        "as_of": policy.as_of,
        "observations": tuple(included),
        "diagnostics": tuple(diagnostics),
        "source_coverage": tuple(source_coverage),
        "conflicts": conflicts,
        "freshness_summary": freshness,
        "completeness_summary": completeness,
    }
    if observation_ages:
        preliminary["observation_ages"] = tuple(
            sorted(observation_ages, key=lambda item: item.observation_id)
        )
    if revision_relationships:
        preliminary["revision_relationships"] = tuple(revision_relationships)
    if news_relationships:
        preliminary["news_relationships"] = news_relationships
    if halt_state is not None:
        preliminary["halt_state"] = halt_state
    bundle_id = f"evidence-{canonical_hash(preliminary)[:24]}"
    hash_content = {"bundle_id": bundle_id, **preliminary}
    bundle_hash = canonical_hash(hash_content)
    return PointInTimeEvidenceBundle(
        bundle_id=bundle_id,
        **preliminary,
        bundle_hash=bundle_hash,
    )
