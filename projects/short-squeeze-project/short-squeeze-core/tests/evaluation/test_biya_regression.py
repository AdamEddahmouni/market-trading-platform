from squeeze_core.contracts import EventType
from squeeze_core.evaluation import RuleCategory, RuleOutcome, serialize_candidate_evaluation
from squeeze_core.evaluation.evaluator import evaluate_candidate

from .biya_helpers import EARLIEST, LATEST, POLICY, by_rule, request


def _evaluate(as_of):
    return evaluate_candidate(request(as_of), POLICY)


def test_biya_both_boundaries_build_and_are_distinct_and_deterministic():
    earliest = _evaluate(EARLIEST)
    latest = _evaluate(LATEST)
    assert earliest.deterministic_id != latest.deterministic_id
    assert serialize_candidate_evaluation(earliest) == serialize_candidate_evaluation(_evaluate(EARLIEST))
    assert serialize_candidate_evaluation(latest) == serialize_candidate_evaluation(_evaluate(LATEST))


def test_biya_momentum_is_evaluated_only_where_historical_inputs_support_it():
    for boundary in (EARLIEST, LATEST):
        rules = by_rule(_evaluate(boundary))
        assert rules["PRICE_RANGE"].outcome in {RuleOutcome.PASS, RuleOutcome.FAIL}
        assert rules["MARKET_DATA_AVAILABLE"].outcome is RuleOutcome.PASS
        assert rules["COMPLETED_BAR_AVAILABLE"].outcome is RuleOutcome.PASS
        assert rules["PERCENTAGE_CHANGE_MINIMUM"].outcome is RuleOutcome.PASS
        assert rules["RELATIVE_VOLUME_MINIMUM"].outcome is RuleOutcome.FAIL
        assert rules["FLOAT_MAXIMUM"].outcome is RuleOutcome.PASS
        assert rules["FLOAT_MAXIMUM"].input_observation_ids


def test_biya_short_pressure_missingness_never_becomes_failure_or_zero():
    for boundary in (EARLIEST, LATEST):
        pressure = tuple(
            item for item in _evaluate(boundary).rule_results
            if item.category is RuleCategory.SHORT_PRESSURE_CONFIRMATION
        )
        assert pressure
        published_si = next(item for item in pressure if item.rule_id == "PUBLISHED_SHORT_INTEREST_AVAILABLE")
        assert published_si.outcome is RuleOutcome.PASS
        assert published_si.input_observation_ids
        days_to_cover = next(item for item in pressure if item.rule_id == "DAYS_TO_COVER_MINIMUM")
        assert days_to_cover.outcome is RuleOutcome.UNKNOWN
        assert days_to_cover.observed_value is None
        assert not days_to_cover.input_observation_ids
        borrow_rules = tuple(
            item for item in pressure
            if item.rule_id.startswith("BORROW_")
        )
        assert borrow_rules
        assert all(
            item.outcome in {RuleOutcome.UNKNOWN, RuleOutcome.INSUFFICIENT_DATA}
            for item in borrow_rules
        )


def test_biya_news_timing_and_reverse_split_context_are_preserved():
    for boundary in (EARLIEST, LATEST):
        evaluation = _evaluate(boundary)
        rules = by_rule(evaluation)
        assert rules["NEWS_AVAILABLE_BEFORE_AS_OF"].outcome is RuleOutcome.PASS
        assert rules["NEWS_AVAILABLE_BEFORE_AS_OF"].input_observation_ids
        assert rules["CORPORATE_ACTION_CONTEXT_AVAILABLE"].outcome is RuleOutcome.PASS
        input_by_id = {
            str(item.observation_id): item for item in request(boundary).input_observations
        }
        supported_news = tuple(
            input_by_id[item_id]
            for item_id in rules["NEWS_AVAILABLE_BEFORE_AS_OF"].input_observation_ids
        )
        assert all(item.source_timestamp <= boundary for item in supported_news)
        assert any(
            item.event_type is EventType.NEWS_ITEM and item.source_timestamp > boundary
            for item in request(boundary).input_observations
        )


def test_biya_post_boundary_market_outcomes_cannot_change_rule_results():
    for boundary in (EARLIEST, LATEST):
        baseline_request = request(boundary)
        assert all(
            item.event_type is not EventType.BAR or item.source_timestamp <= boundary
            for item in baseline_request.input_observations
        )
        baseline = evaluate_candidate(baseline_request, POLICY)
        # The acquired fixture contains later movement, but it is not part of the request.
        repeated = evaluate_candidate(request(boundary), POLICY)
        assert serialize_candidate_evaluation(baseline) == serialize_candidate_evaluation(repeated)


def test_biya_phase_2v_conclusion_and_candidate_label_are_absent_from_phase_3a():
    for boundary in (EARLIEST, LATEST):
        rendered = serialize_candidate_evaluation(_evaluate(boundary))
        assert b"OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED" not in rendered
        assert b"candidate_label" not in rendered
        assert b"Prime" not in rendered

