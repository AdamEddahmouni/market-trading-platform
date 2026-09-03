from datetime import timedelta

from squeeze_core.contracts import AssetClass
from squeeze_core.evaluation import RuleEvaluationRequest, RuleOutcome
from squeeze_core.evaluation.policies import lookup_policy, lookup_rule
from squeeze_core.evaluation.rules.catalyst import evaluate_catalyst_rule

from .helpers import AS_OF, corporate_action, news, sec_filing

POLICY = lookup_policy("phase_3a_transparent_candidate_policy.v1")


def evaluate(rule_id: str, *, observations=()):
    request = RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=(rule_id,),
        provider_scope=("news-a", "sec", "actions"), input_observations=observations,
    )
    return evaluate_catalyst_rule(request, lookup_rule(POLICY, rule_id))


def test_news_exists_before_as_of_and_support_ids_are_stable():
    item = news(published_at=AS_OF - timedelta(hours=1))
    available = evaluate("NEWS_AVAILABLE", observations=(item,))
    before = evaluate("NEWS_AVAILABLE_BEFORE_AS_OF", observations=(item,))
    assert available.outcome is RuleOutcome.PASS
    assert before.outcome is RuleOutcome.PASS
    assert available.input_observation_ids == (str(item.observation_id),)


def test_news_after_as_of_fails_only_the_explicit_before_rule():
    future = news(published_at=AS_OF + timedelta(minutes=5),
                  source_time=AS_OF + timedelta(minutes=5))
    assert evaluate("NEWS_AVAILABLE", observations=(future,)).outcome is RuleOutcome.UNKNOWN
    after = evaluate("NEWS_AVAILABLE_BEFORE_AS_OF", observations=(future,))
    assert after.outcome is RuleOutcome.FAIL
    assert after.input_observation_ids == (str(future.observation_id),)


def test_news_missing_unknown_timestamp_and_withdrawal_are_not_inferred():
    assert evaluate("NEWS_AVAILABLE").outcome is RuleOutcome.UNKNOWN
    unknown_time = news(published_at=None, source_time=AS_OF - timedelta(minutes=1))
    timestamp = evaluate("NEWS_TIMESTAMP_KNOWN", observations=(unknown_time,))
    assert timestamp.outcome is RuleOutcome.UNKNOWN
    withdrawn = news(published_at=AS_OF - timedelta(hours=1), status="WITHDRAWN")
    assert evaluate("NEWS_AVAILABLE", observations=(withdrawn,)).outcome is RuleOutcome.UNKNOWN
    assert not hasattr(timestamp, "sentiment")


def test_sec_filing_available_missing_and_future_publication():
    assert evaluate("SEC_FILING_AVAILABLE", observations=(sec_filing(),)).outcome is RuleOutcome.PASS
    assert evaluate("SEC_FILING_AVAILABLE").outcome is RuleOutcome.UNKNOWN
    future = sec_filing(filed_at=AS_OF + timedelta(minutes=1))
    assert evaluate("SEC_FILING_AVAILABLE", observations=(future,)).outcome is RuleOutcome.UNKNOWN


def test_corporate_action_context_is_presence_not_direction():
    action = corporate_action()
    result = evaluate("CORPORATE_ACTION_CONTEXT_AVAILABLE", observations=(action,))
    assert result.outcome is RuleOutcome.PASS
    assert result.input_observation_ids == (str(action.observation_id),)
    assert evaluate("CORPORATE_ACTION_CONTEXT_AVAILABLE").outcome is RuleOutcome.UNKNOWN
    assert "positive" not in result.explanation_code.lower()
    assert "negative" not in result.explanation_code.lower()
