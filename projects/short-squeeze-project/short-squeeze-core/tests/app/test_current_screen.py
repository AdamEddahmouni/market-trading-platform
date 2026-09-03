"""Batch 11 — the current operational screen.

Every test runs offline against :class:`SyntheticProvider`. Nothing here needs an IB
Gateway, a network, or a market session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apps.research_screener import current_eval, discovery, session_state
from apps.research_screener.provider_session import CurrentBar
from apps.research_screener.truth import ValueStatus

from .synthetic_provider import (
    SyntheticProvider, fake_external_providers, quote, rising_bars,
)


@pytest.fixture
def session() -> session_state.ScreenerSession:
    return session_state.ScreenerSession(
        provider=SyntheticProvider(), symbols_per_cycle=10
    )


def _refreshed(session: session_state.ScreenerSession, profile: str = "BROAD_MOVERS"):
    session.refresh_discovery(profile)
    session.refresh_all()
    return session.rows()


# ------------------------------------------------------------------ discovery


def test_automated_discovery_produces_candidates(session):
    result = session.refresh_discovery("BROAD_MOVERS")
    assert result["discovered"] == 3
    assert set(session.states) == {"AAA", "BBB", "CCC"}


def test_discovery_profiles_expose_explicit_criteria(session):
    profiles = session.profiles
    assert set(profiles) == {
        "BROAD_MOVERS", "MOST_ACTIVE", "HISTORICAL_RUBRIC_LIKE", "MANUAL_SYMBOL",
        "FINVIZ_SCREENER",
    }
    for profile in profiles.values():
        payload = profile.as_dict()
        assert payload["criteria"], f"{profile.profile_id} must state its criteria"
        assert payload["ordering"] == "Provider scanner order"
        assert "not a validated squeeze scanner" in payload["disclaimer"]


def test_rubric_profile_price_bounds_come_from_the_committed_policy(session):
    scanner = session.profiles["HISTORICAL_RUBRIC_LIKE"].scanner
    low, high = discovery.price_range_bounds(session.policy)
    assert (scanner.above_price, scanner.below_price) == (low, high)
    assert (str(low), str(high)) == ("2", "20")


def test_scanner_failure_degrades_without_destroying_the_screen():
    provider = SyntheticProvider()
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=10)
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()
    assert len(session.states) == 3

    provider.scanner_fails = True
    result = session.refresh_discovery("BROAD_MOVERS")
    assert result["discovered"] == 0
    assert result["error"]
    # The screen survives the outage.
    assert len(session.states) == 3
    assert all(not state.candidate.in_current_scan for state in session.states.values())


def test_symbol_leaving_the_scan_is_dropped_from_active_set():
    provider = SyntheticProvider(symbols=("AAA", "BBB"))
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=10)
    _refreshed(session)
    assert session.states["BBB"].history
    assert "AAA" in session.states

    provider.symbols = ("AAA",)
    session.refresh_discovery("BROAD_MOVERS")
    assert "BBB" not in session.states
    assert "AAA" in session.states
    assert session.states["AAA"].history


def test_remaining_symbol_keeps_history_across_discovery():
    provider = SyntheticProvider(symbols=("AAA", "BBB"))
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=10)
    _refreshed(session)
    aaa_history = list(session.states["AAA"].history)
    assert aaa_history

    provider.symbols = ("AAA",)
    session.refresh_discovery("BROAD_MOVERS")
    assert session.states["AAA"].history == aaa_history


def test_manual_symbols_survive_discovery_rebuild():
    provider = SyntheticProvider(symbols=("AAA",))
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=10)
    session.refresh_discovery("BROAD_MOVERS")
    session.add_manual_symbols(["ZZZ"])
    session.refresh_discovery("BROAD_MOVERS")
    assert "ZZZ" in session.states
    assert session.states["ZZZ"].candidate.profile_id == "MANUAL_SYMBOL"


def test_candidate_identity_is_stable_across_refreshes(session):
    _refreshed(session)
    before = {s: session.states[s].candidate.candidate_key for s in session.states}
    first_seen = {s: session.states[s].candidate.first_seen_at for s in session.states}
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()
    after = {s: session.states[s].candidate.candidate_key for s in session.states}
    assert before == after
    assert first_seen == {s: session.states[s].candidate.first_seen_at for s in session.states}


# ------------------------------------------------------------------ evidence


def test_quote_updates_populate_separate_price_fields(session):
    rows = _refreshed(session)
    fields = rows[0]["fields"]
    for name in ("last", "bid", "ask", "previous_close"):
        assert fields[name]["status"] == "KNOWN", name
    # Distinct fields, never one standing in for another.
    assert fields["last"]["value"] != fields["bid"]["value"] != fields["ask"]["value"]


def test_market_data_type_label_comes_from_the_provider():
    for code, label in ((1, "REALTIME"), (2, "FROZEN"), (3, "DELAYED"), (4, "DELAYED_FROZEN")):
        provider = SyntheticProvider(
            symbols=("AAA",), quote_factory=lambda s, c=code: quote(s, market_data_type=c)
        )
        session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
        rows = _refreshed(session)
        assert rows[0]["market_data_mode"] == label


def test_unknown_market_data_type_is_not_called_live():
    provider = SyntheticProvider(
        symbols=("AAA",), quote_factory=lambda s: quote(s, market_data_type=None)
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    rows = _refreshed(session)
    assert rows[0]["market_data_mode"] == "UNKNOWN"
    assert rows[0]["data_mode"] == "UNAVAILABLE"


def test_missing_quote_stays_unknown_and_never_zero():
    provider = SyntheticProvider(
        symbols=("AAA",), quote_factory=lambda s: quote(s, last=None)
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    rows = _refreshed(session)
    for name in ("last", "bid", "ask", "previous_close"):
        cell = rows[0]["fields"][name]
        assert cell["status"] == "UNKNOWN"
        assert cell["value"] is None
        assert cell["display"] == "—"
        assert cell["missing_reason"]


def test_short_pressure_without_a_provider_stays_missing(session):
    rows = _refreshed(session)
    fields = rows[0]["fields"]
    for name in ("float_shares", "short_float", "published_short_interest",
                 "borrow_fee", "days_to_cover"):
        assert fields[name]["status"] == ValueStatus.NOT_CONFIGURED.value
        assert fields[name]["value"] is None
    for name in ("shortable", "borrow_availability"):
        assert fields[name]["status"] == ValueStatus.UNAVAILABLE.value
        assert fields[name]["value"] is None


def test_shortability_ticks_are_shown_when_the_provider_supplies_them():
    provider = SyntheticProvider(
        symbols=("AAA",),
        quote_factory=lambda s: quote(s, shortable=3.0, shortable_shares=50000.0),
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    rows = _refreshed(session)
    assert rows[0]["fields"]["shortable"]["value"] == 3.0
    assert rows[0]["fields"]["borrow_availability"]["value"] == 50000.0


def test_news_provider_is_reported_as_not_configured(session):
    rows = _refreshed(session)
    catalyst = rows[0]["fields"]["catalyst"]
    assert catalyst["status"] == ValueStatus.NOT_CONFIGURED.value


def test_explicit_fake_external_providers_enrich_without_network():
    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("AAA",)),
        external_providers=fake_external_providers(),
        symbols_per_cycle=5,
    )
    rows = _refreshed(session)
    fields = rows[0]["fields"]
    assert fields["float_shares"]["value"] == 8_000_000
    assert fields["float_shares"]["provider"] == "Finviz Elite"
    assert fields["short_float"]["value"] == 14.0
    assert fields["short_ratio"]["value"] == 3.2
    assert fields["days_to_cover"]["status"] == ValueStatus.KNOWN.value
    assert fields["days_to_cover"]["value"] == 3.2
    assert fields["published_short_interest"]["status"] == ValueStatus.KNOWN.value
    assert fields["published_short_interest"]["value"] == 14.0
    assert fields["relative_volume"]["value"] == 2.0
    assert fields["news_count"]["value"] == 1
    assert fields["latest_headline"]["status"] == ValueStatus.KNOWN.value
    assert fields["latest_headline"]["value"] == "AAA files deterministic test update"
    assert fields["catalyst"]["status"] == ValueStatus.UNKNOWN.value
    assert fields["float_shares"]["provider_field"] == "Float"
    assert fields["float_shares"]["selection_reason"] == "ONLY_AVAILABLE"
    assert fields["float_shares"]["research_admissibility"] == "RESEARCH_ADMISSIBLE"


def test_finviz_float_flows_through_canonical_phase3a_evaluator():
    baseline = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("AAA",)),
        symbols_per_cycle=5,
    )
    _refreshed(baseline)
    before = {
        rule["rule_id"] for rule in baseline.detail("AAA")["rules"]
        if rule["outcome"] in ("PASS", "FAIL")
    }
    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("AAA",)),
        external_providers=fake_external_providers(),
        symbols_per_cycle=5,
    )
    _refreshed(session)
    detail = session.detail("AAA")
    float_rule = next(rule for rule in detail["rules"] if rule["rule_id"] == "FLOAT_MAXIMUM")
    assert float_rule["outcome"] == "PASS"
    assert float_rule["observed_value"] == "8000000"
    assert float_rule["evidence_ids"]
    after = {
        rule["rule_id"] for rule in detail["rules"]
        if rule["outcome"] in ("PASS", "FAIL")
    }
    assert after - before == {"FLOAT_MAXIMUM"}
    assert detail["evidence_coverage"]["supported"] == len(before) + 1


def test_sentiment_is_not_configured(session):
    rows = _refreshed(session)
    assert rows[0]["fields"]["sentiment"]["status"] == ValueStatus.NOT_CONFIGURED.value


# ------------------------------------------------- current Phase 3A evaluation


def test_current_evaluation_uses_the_canonical_evaluator(session):
    rows = _refreshed(session)
    counts = rows[0]["phase3a"]["counts"]
    assert rows[0]["phase3a"]["total_rules"] == 25
    assert sum(counts.values()) == 25
    # The current screen genuinely evaluates rules; it is not all-UNKNOWN.
    assert counts["PASS"] > 0


def test_all_twenty_five_rules_are_visible_in_detail(session):
    _refreshed(session)
    detail = session.detail("AAA")
    assert len(detail["rules"]) == 25
    assert [rule["rule_id"] for rule in detail["rules"]] == list(session.policy.enabled_rule_ids)


def test_percentage_change_uses_the_canonical_metric(session):
    _refreshed(session)
    evaluation = session.states["AAA"].evaluation
    assert str(evaluation.metric.metric_name) == "PERCENTAGE_RETURN"
    assert evaluation.metric.calculation_policy_version == "close_to_close_completed.v1"
    rule = next(r for r in current_eval.rule_rows(evaluation, list(session.policy.enabled_rule_ids))
                if r["rule_id"] == "PERCENTAGE_CHANGE_MINIMUM")
    assert rule["outcome"] in ("PASS", "FAIL")


def test_relative_volume_stays_unknown_because_units_are_unresolved(session):
    _refreshed(session)
    detail = session.detail("AAA")
    rule = next(r for r in detail["rules"] if r["rule_id"] == "RELATIVE_VOLUME_MINIMUM")
    assert rule["outcome"] == "UNKNOWN"
    assert detail["market_data"]["relative_volume"]["status"] == "UNKNOWN"


def test_raw_provider_volume_is_labelled_unresolved_and_is_not_evidence():
    provider = SyntheticProvider(
        symbols=("AAA",), quote_factory=lambda s: quote(s, volume=123456.0)
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    rows = _refreshed(session)
    cell = rows[0]["fields"]["provider_volume"]
    assert cell["value"] == 123456.0
    assert cell["unit"] == "UNRESOLVED_PROVIDER_UNIT"
    assert cell["readiness"] == "NOT_ADMISSIBLE_UNRESOLVED_UNIT"
    # It never becomes a relative-volume value.
    assert rows[0]["fields"]["relative_volume"]["status"] == "UNKNOWN"


def test_price_range_evaluates_only_while_the_observation_is_current():
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    fresh = rising_bars(40, end=now)
    evaluation = current_eval.evaluate_current("AAA", fresh, now=now, retrieved_at=now)
    outcomes = {r.rule_id: str(r.outcome) for r in evaluation.rule_results}
    assert evaluation.provider_scope == ("IBKR",)
    assert outcomes["PRICE_RANGE"] in ("PASS", "FAIL")
    assert evaluation.price_scope_reason is None


def test_price_range_is_withheld_once_the_observation_is_stale():
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    stale_end = now - timedelta(hours=17)
    bars = rising_bars(40, end=stale_end)
    evaluation = current_eval.evaluate_current("AAA", bars, now=now, retrieved_at=now)
    outcomes = {r.rule_id: str(r.outcome) for r in evaluation.rule_results}
    assert evaluation.provider_scope == ()
    assert evaluation.price_scope_reason
    assert outcomes["PRICE_RANGE"] == "UNKNOWN"
    # A price ratio is still admissible, so the percentage rule keeps evaluating.
    assert outcomes["PERCENTAGE_CHANGE_MINIMUM"] in ("PASS", "FAIL")


def test_stale_observation_is_not_labelled_current():
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    provider = SyntheticProvider(
        symbols=("AAA",),
        bars_factory=lambda s: rising_bars(40, end=now - timedelta(hours=17)),
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    rows = _refreshed(session)
    assert rows[0]["freshness"] == "STALE"
    assert rows[0]["age_basis"] == "OBSERVATION_AS_OF_INSTANT"
    assert rows[0]["age_seconds"] > 3600


def test_too_few_bars_leaves_the_metric_missing_rather_than_fabricated():
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    one_bar = [
        CurrentBar(
            timestamp_utc=(now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            open=5.0, high=5.0, low=5.0, close=5.0,
        )
    ]
    evaluation = current_eval.evaluate_current("AAA", one_bar, now=now, retrieved_at=now)
    assert evaluation.metric is None
    assert evaluation.metric_unavailable_reason
    outcomes = {r.rule_id: str(r.outcome) for r in evaluation.rule_results}
    assert outcomes["PERCENTAGE_CHANGE_MINIMUM"] == "UNKNOWN"


def test_evidence_selection_does_not_change_outcomes():
    """The bounded evidence set must give exactly what the whole window would give."""
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    bars = rising_bars(40, end=now)
    evaluation = current_eval.evaluate_current("AAA", bars, now=now, retrieved_at=now)
    assert evaluation.evidence_bar_count == 2
    assert evaluation.included_bar_count == 40

    labels = tuple(
        datetime.fromisoformat(bar.timestamp_utc.replace("Z", "+00:00"))
        for bar in bars
    )
    assert current_eval.select_evidence_labels(labels) == (labels[0], labels[-1])


def test_no_forward_or_outcome_is_produced(session):
    rows = _refreshed(session)
    for row in rows:
        assert row["outcome"]["status"] == "NOT_APPLICABLE"
        assert row["case_id"] is None
        assert row["candidate_id"] is None
    detail = session.detail("AAA")
    assert detail["chart"]["forward_window_shown"] is False


def test_current_candidate_is_never_a_research_case(session):
    session.refresh_discovery("BROAD_MOVERS")
    payload = session.states["AAA"].candidate.as_dict()
    assert payload["case_id"] is None
    assert payload["outcome"] is None
    assert payload["research_registry_member"] is False


# --------------------------------------------------------------- refresh flow


def test_failed_refresh_retains_the_previous_snapshot_as_stale():
    provider = SyntheticProvider(symbols=("AAA",))
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    _refreshed(session)
    good = session.row_for(session.states["AAA"])
    assert good["fields"]["last"]["status"] == "KNOWN"

    provider.collect_fails = True
    session.refresh_all()
    after = session.row_for(session.states["AAA"])
    assert after["stale"] is True
    assert after["stale_reason"]
    # The working snapshot was kept, not erased.
    assert after["fields"]["last"]["value"] == good["fields"]["last"]["value"]
    assert after["freshness"] == "STALE"


def test_refresh_is_round_robin_and_bounded():
    provider = SyntheticProvider(symbols=("AAA", "BBB", "CCC", "DDD", "EEE"), budget=60)
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=2)
    session.refresh_discovery("BROAD_MOVERS")
    first = session.refresh_all(limit=2)
    second = session.refresh_all(limit=2)
    assert first["swept"] == 2 and second["swept"] == 2
    assert len(set(first["symbols"]) | set(second["symbols"])) >= 2


def test_pacing_budget_exhaustion_is_reported_not_exceeded():
    provider = SyntheticProvider(symbols=("AAA",), budget=1)
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    _refreshed(session)
    session.refresh_all()
    state = session.states["AAA"]
    assert state.stale is True
    assert "pacing budget" in (state.stale_reason or "")


def test_rule_transitions_are_recorded_as_research_state_changes():
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    provider = SyntheticProvider(
        symbols=("AAA",), bars_factory=lambda s: rising_bars(40, end=now, step=1.0001)
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    _refreshed(session)
    # A much stronger move flips PERCENTAGE_CHANGE_MINIMUM.
    provider.bars_factory = lambda s: rising_bars(40, end=now, step=1.01)
    session.refresh_all()
    transitions = session.states["AAA"].transitions
    assert any(t.rule_id == "PERCENTAGE_CHANGE_MINIMUM" for t in transitions)
    payload = transitions[-1].as_dict()
    assert payload["label"] == "Research-state change"
    assert payload["evidence_provider"] == "IBKR"
    assert payload["evidence_id"]
    assert payload["reason"]
    assert "signal" not in str(payload).lower()


def test_session_history_is_bounded():
    provider = SyntheticProvider(symbols=("AAA",))
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    session.refresh_discovery("BROAD_MOVERS")
    for _ in range(session_state.MAX_HISTORY_PER_SYMBOL + 12):
        provider.budget = 10
        session.refresh_all()
    assert len(session.states["AAA"].history) == session_state.MAX_HISTORY_PER_SYMBOL


def test_provider_reconnect_is_transparent():
    provider = SyntheticProvider(symbols=("AAA",))
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    _refreshed(session)
    provider.close()
    session.refresh_all()
    assert session.states["AAA"].evaluation is not None
    assert not session.states["AAA"].stale


# ---------------------------------------------------------------------- chart


def test_current_chart_uses_real_bars_and_no_detection_boundary(session):
    _refreshed(session)
    chart = session.detail("AAA")["chart"]
    assert chart["available"] is True
    assert chart["points"]
    assert chart["boundary_time"] is None
    assert chart["boundary_label"] is None
    assert chart["snapshot_label"] == "Snapshot Time"


def test_chart_downsamples_by_stride_only():
    now = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    bars = rising_bars(1200, end=now)
    chart = current_eval.chart_points(bars)
    assert chart["point_count_total"] == 1200
    assert chart["point_count_plotted"] <= current_eval.MAX_CHART_POINTS + 1
    closes = {round(bar.close, 6) for bar in bars}
    for point in chart["points"]:
        assert round(point["close"], 6) in closes


# -------------------------------------------------------------------- summary


def test_summary_keeps_current_separate_from_frozen(session):
    _refreshed(session)
    summary = session.summary()
    assert summary["candidate_count"] == 3
    assert "never added to the historical research statistics" in summary["note"]
    assert summary["evaluable_rule_count"] > 0


def test_missing_evidence_is_listed_explicitly(session):
    _refreshed(session)
    missing = session.detail("AAA")["missing_evidence"]
    assert missing
    for entry in missing:
        assert entry["reason"], entry["field"]


def test_row_data_quality_exposes_stable_diagnostics_shape(session):
    rows = _refreshed(session)
    data_quality = rows[0]["data_quality"]
    assert set(data_quality) == {
        "unevaluable",
        "evaluable_rule_count",
        "total_rule_count",
        "coverage_ratio",
        "cause_summaries",
        "missing_evidence_buckets",
    }
    assert isinstance(data_quality["unevaluable"], bool)
    assert isinstance(data_quality["evaluable_rule_count"], int)
    assert isinstance(data_quality["total_rule_count"], int)
    assert isinstance(data_quality["coverage_ratio"], (float, type(None)))
    assert isinstance(data_quality["cause_summaries"], list)
    assert isinstance(data_quality["missing_evidence_buckets"], list)
    if data_quality["missing_evidence_buckets"]:
        bucket = data_quality["missing_evidence_buckets"][0]
        assert set(bucket) == {"bucket", "missing_field_count", "top_reason_code"}
        assert isinstance(bucket["bucket"], str)
        assert isinstance(bucket["missing_field_count"], int)
        assert isinstance(bucket["top_reason_code"], (str, type(None)))


def test_summary_readiness_exposes_stable_diagnostics_shape(session):
    _refreshed(session)
    readiness = session.summary()["readiness"]
    assert set(readiness) == {
        "candidate_count",
        "actionable_candidate_count",
        "unevaluable_candidate_count",
        "actionable_ratio",
        "top_missing_evidence_buckets",
        "top_unevaluable_causes",
    }
    assert isinstance(readiness["candidate_count"], int)
    assert isinstance(readiness["actionable_candidate_count"], int)
    assert isinstance(readiness["unevaluable_candidate_count"], int)
    assert isinstance(readiness["actionable_ratio"], (float, type(None)))
    assert isinstance(readiness["top_missing_evidence_buckets"], list)
    assert isinstance(readiness["top_unevaluable_causes"], list)
    if readiness["top_missing_evidence_buckets"]:
        bucket = readiness["top_missing_evidence_buckets"][0]
        assert set(bucket) == {"bucket", "missing_field_count"}
        assert isinstance(bucket["bucket"], str)
        assert isinstance(bucket["missing_field_count"], int)
    if readiness["top_unevaluable_causes"]:
        cause = readiness["top_unevaluable_causes"][0]
        assert set(cause) == {"cause", "candidate_count"}
        assert isinstance(cause["cause"], str)
        assert isinstance(cause["candidate_count"], int)


def test_runtime_drift_guard_connected_transport_but_all_unevaluable():
    provider = SyntheticProvider(
        symbols=("AAA", "BBB", "CCC"),
        bars_factory=lambda s: [],
        quote_factory=lambda s: quote(s, market_data_type=1),
    )
    session = session_state.ScreenerSession(provider=provider, symbols_per_cycle=10)
    rows = _refreshed(session)
    summary = session.summary()
    readiness = summary["readiness"]

    assert len(rows) == 3
    assert all(row["market_data_mode"] == "REALTIME" for row in rows)
    assert all(row["research_detection"]["status"] == "UNEVALUABLE" for row in rows)
    assert all(row["stale"] is True for row in rows)
    assert readiness["candidate_count"] == 3
    assert readiness["actionable_candidate_count"] == 0
    assert readiness["unevaluable_candidate_count"] == 3
    assert readiness["actionable_ratio"] == 0.0
    top_causes = {item["cause"] for item in readiness["top_unevaluable_causes"]}
    assert "NO_EVALUABLE_RULES" in top_causes
