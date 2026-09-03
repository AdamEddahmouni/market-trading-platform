"""As-of replay behaviour.

Every no-look-ahead assertion here is really a test that Phase 1's
build_point_in_time_evidence is being reused faithfully. If any of these start failing
because validation/replay.py grew its own timestamp handling, that is the bug they
exist to catch.
"""

import inspect
from datetime import UTC, datetime

from squeeze_core.validation import build_boundary_replays, build_rebuilt_as_of_snapshot
from squeeze_core.validation import replay as replay_module
from squeeze_core.validation import serialize_replay

from .conftest import make_bar, make_borrow, make_sec_filing, make_short_interest

SYMBOL = "TESTD"
EARLY = datetime(2026, 2, 10, 12, 0, tzinfo=UTC)
LATE = datetime(2026, 2, 12, 12, 0, tzinfo=UTC)


def _snapshot(observations, as_of, label="test", **kwargs):
    return build_rebuilt_as_of_snapshot(label, SYMBOL, observations, as_of, **kwargs)


def test_replay_at_an_exact_timestamp():
    result = _snapshot([make_short_interest()], LATE)
    assert result.as_of == LATE
    assert result.symbol == SYMBOL


def test_earliest_and_latest_boundary_replays_are_both_produced():
    observations = [make_short_interest()]
    results = build_boundary_replays(
        SYMBOL, observations, (("earliest", EARLY), ("latest", LATE))
    )
    assert [item.label for item in results] == ["earliest", "latest"]
    assert [item.as_of for item in results] == [EARLY, LATE]


def test_boundary_replays_are_returned_chronologically_regardless_of_input_order():
    observations = [make_short_interest()]
    forward = build_boundary_replays(
        SYMBOL, observations, (("earliest", EARLY), ("latest", LATE))
    )
    reverse = build_boundary_replays(
        SYMBOL, observations, (("latest", LATE), ("earliest", EARLY))
    )
    assert [item.deterministic_id for item in forward] == [
        item.deterministic_id for item in reverse
    ]


def test_a_future_observation_is_excluded():
    """The short-interest record publishes 2026-01-25; a replay before that must not
    see it."""

    observations = [make_short_interest()]
    before = _snapshot(observations, datetime(2026, 1, 20, tzinfo=UTC))
    after = _snapshot(observations, datetime(2026, 2, 1, tzinfo=UTC))
    assert len(before.eligible_observation_ids) < len(after.eligible_observation_ids)


def test_a_future_bar_is_excluded_and_a_past_bar_is_included():
    bar = make_bar()
    before = _snapshot([bar], datetime(2026, 2, 9, tzinfo=UTC))
    after = _snapshot([bar], datetime(2026, 2, 11, tzinfo=UTC))
    assert bar.observation_id not in before.eligible_observation_ids
    assert bar.observation_id in after.eligible_observation_ids


def test_a_borrow_update_after_detection_is_excluded():
    fee, availability = make_borrow()
    before = _snapshot([fee, availability], datetime(2026, 1, 9, tzinfo=UTC))
    after = _snapshot([fee, availability], datetime(2026, 1, 12, tzinfo=UTC))
    assert fee.observation_id not in before.eligible_observation_ids
    assert fee.observation_id in after.eligible_observation_ids


def test_a_filing_after_detection_is_excluded():
    filing = make_sec_filing()
    before = _snapshot([filing], datetime(2026, 1, 19, tzinfo=UTC))
    after = _snapshot([filing], datetime(2026, 1, 21, tzinfo=UTC))
    assert filing.observation_id not in before.eligible_observation_ids
    assert filing.observation_id in after.eligible_observation_ids


def test_later_evidence_changes_the_replay_identity():
    observations = [make_short_interest(), make_bar()]
    before = _snapshot(observations, datetime(2026, 1, 20, tzinfo=UTC), label="before")
    after = _snapshot(observations, datetime(2026, 3, 1, tzinfo=UTC), label="after")
    assert before.deterministic_id != after.deterministic_id


def test_input_order_does_not_change_the_result():
    observations = [make_short_interest(), make_bar(), make_sec_filing()]
    forward = _snapshot(observations, LATE)
    reverse = _snapshot(list(reversed(observations)), LATE)
    assert forward.deterministic_id == reverse.deterministic_id
    assert serialize_replay(forward) == serialize_replay(reverse)


def test_replay_is_byte_stable_across_runs():
    observations = [make_short_interest()]
    assert serialize_replay(_snapshot(observations, LATE)) == serialize_replay(
        _snapshot(observations, LATE)
    )


def test_replay_reuses_phase_2d_readiness_ids():
    result = _snapshot([make_short_interest()], LATE, operation="DAYS_TO_COVER")
    assert result.coverage_snapshot_id
    assert result.age_alignment_id
    assert result.conflict_summary_id
    assert result.missingness_summary_id
    assert result.sufficiency_result_id
    assert result.structural_state is not None


def test_replay_without_an_operation_claims_no_sufficiency_verdict():
    result = _snapshot([make_short_interest()], LATE)
    assert result.operation is None
    assert result.structural_state is None
    assert result.sufficiency_result_id is None


def test_insufficient_inputs_are_reported_not_defaulted():
    result = _snapshot([], LATE, operation="DAYS_TO_COVER")
    assert result.structural_state is not None
    # Nothing was available, so no metric id may appear.
    assert result.eligible_metric_ids == ()
    assert result.metric_results == ()


def test_unavailable_metrics_are_absent_rather_than_zero():
    result = _snapshot([make_short_interest()], LATE, operation="DAYS_TO_COVER")
    assert all(item != "" for item in result.eligible_metric_ids)


def test_replay_module_defines_no_second_point_in_time_engine():
    """Structural guard, not a behavioural one: the replay module must delegate as-of
    filtering rather than implement it."""

    source = inspect.getsource(replay_module)
    assert "build_point_in_time_evidence" in source
    # No comparison of an observation timestamp against as_of anywhere in this module.
    for forbidden in (
        "source_timestamp <",
        "source_timestamp >",
        "received_timestamp <",
        "received_timestamp >",
        "effective_timestamp <",
        "effective_timestamp >",
        "<= as_of",
        ">= as_of",
        "< as_of",
        "> as_of",
    ):
        assert forbidden not in source, f"replay.py appears to filter by time itself: {forbidden}"


def test_replay_symbol_is_normalized():
    result = build_rebuilt_as_of_snapshot("t", "  testd  ", [make_short_interest()], LATE)
    assert result.symbol == "TESTD"


def test_domains_are_reported_from_the_coverage_snapshot():
    result = _snapshot([make_short_interest()], LATE, operation="DAYS_TO_COVER")
    assert isinstance(result.present_domains, tuple)
    assert isinstance(result.missing_domains, tuple)
    assert result.present_domains == tuple(sorted(result.present_domains))
    assert result.missing_domains == tuple(sorted(result.missing_domains))
