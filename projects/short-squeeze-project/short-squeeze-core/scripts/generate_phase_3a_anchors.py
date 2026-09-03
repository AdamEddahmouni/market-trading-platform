"""Generate the additive Phase 3A fixtures and deterministic anchor manifest."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from squeeze_core.contracts import AssetClass, QualityState  # noqa: E402
from squeeze_core.evaluation import (  # noqa: E402
    RuleCategory, RuleEvaluationRequest, evaluate_candidate,
    serialize_candidate_evaluation, serialize_rule_result,
)
from squeeze_core.evaluation.policies import DEFAULT_POLICY_PATH, lookup_rule  # noqa: E402
from squeeze_core.evaluation.rules import (  # noqa: E402
    evaluate_catalyst_rule, evaluate_evidence_validity_rule, evaluate_momentum_rule,
    evaluate_short_pressure_rule,
)
from squeeze_core.metrics import MetricName, MetricUnit  # noqa: E402
from squeeze_core.serialization import canonical_hash, canonical_json_bytes  # noqa: E402
from tests.evaluation.biya_helpers import (  # noqa: E402
    EARLIEST, LATEST, POLICY, request as biya_request,
)
from tests.evaluation.helpers import (  # noqa: E402
    AS_OF, bar, borrow_availability, borrow_fee, news, normalized_metric,
    pressure_metric, short_interest,
)
from tests.evaluation.test_evidence_validity import coverage, conflicts, sufficiency  # noqa: E402
from squeeze_core.evidence import CoverageDomain  # noqa: E402


OUT = ROOT / "tests" / "fixtures" / "evaluation"


def _request(rule_id, *, observations=(), metrics=(), readiness=(), defaults=(), providers=("provider-a", "news-a")):
    return RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=(rule_id,),
        provider_scope=providers, input_observations=observations, input_metrics=metrics,
        input_readiness_results=readiness, default_substitution_fields=defaults,
    )


def _rule(rule_id, **kwargs):
    definition = lookup_rule(POLICY, rule_id)
    evaluator = {
        RuleCategory.MOMENTUM_DISCOVERY: evaluate_momentum_rule,
        RuleCategory.SHORT_PRESSURE_CONFIRMATION: evaluate_short_pressure_rule,
        RuleCategory.CATALYST_EVIDENCE: evaluate_catalyst_rule,
        RuleCategory.EVIDENCE_VALIDITY: evaluate_evidence_validity_rule,
    }[definition.category]
    return evaluator(_request(rule_id, **kwargs), definition)


def build_anchor_results():
    results = {
        "price_range_pass": _rule("PRICE_RANGE", observations=(bar("8"),)),
        "price_range_fail": _rule("PRICE_RANGE", observations=(bar("25"),)),
        "price_range_unknown": _rule("PRICE_RANGE"),
        "percentage_change_pass": _rule("PERCENTAGE_CHANGE_MINIMUM", metrics=(normalized_metric(MetricName.PERCENTAGE_RETURN, "12", MetricUnit.PERCENT),)),
        "percentage_change_fail": _rule("PERCENTAGE_CHANGE_MINIMUM", metrics=(normalized_metric(MetricName.PERCENTAGE_RETURN, "3", MetricUnit.PERCENT),)),
        "relative_volume_pass": _rule("RELATIVE_VOLUME_MINIMUM", metrics=(normalized_metric(MetricName.RELATIVE_VOLUME, "6", MetricUnit.RATIO),)),
        "relative_volume_fail": _rule("RELATIVE_VOLUME_MINIMUM", metrics=(normalized_metric(MetricName.RELATIVE_VOLUME, "2", MetricUnit.RATIO),)),
        "relative_volume_insufficient": _rule("RELATIVE_VOLUME_MINIMUM", metrics=(normalized_metric(MetricName.RELATIVE_VOLUME, None, MetricUnit.RATIO, state=QualityState.MISSING),)),
        "float_unknown": _rule("FLOAT_MAXIMUM"),
        "short_interest_available": _rule("PUBLISHED_SHORT_INTEREST_AVAILABLE", observations=(short_interest(),)),
        "short_interest_unknown": _rule("PUBLISHED_SHORT_INTEREST_AVAILABLE"),
        "short_interest_change_pass": _rule("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM", metrics=(pressure_metric(MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE, "12", MetricUnit.PERCENT),)),
        "short_interest_change_fail": _rule("SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM", metrics=(pressure_metric(MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE, "3", MetricUnit.PERCENT),)),
        "days_to_cover_pass": _rule("DAYS_TO_COVER_MINIMUM", metrics=(pressure_metric(MetricName.DAYS_TO_COVER, "3", MetricUnit.DAYS),)),
        "days_to_cover_fail": _rule("DAYS_TO_COVER_MINIMUM", metrics=(pressure_metric(MetricName.DAYS_TO_COVER, "1", MetricUnit.DAYS),)),
        "days_to_cover_insufficient": _rule("DAYS_TO_COVER_MINIMUM", metrics=(pressure_metric(MetricName.DAYS_TO_COVER, None, MetricUnit.DAYS, state=QualityState.MISSING),)),
        "borrow_fee_pass": _rule("BORROW_FEE_MINIMUM", observations=(borrow_fee("12"),)),
        "borrow_fee_unknown": _rule("BORROW_FEE_MINIMUM"),
        "borrow_availability_zero_known": _rule("BORROW_AVAILABILITY_MAXIMUM", observations=(borrow_availability(0),)),
        "borrow_availability_unknown": _rule("BORROW_AVAILABILITY_MAXIMUM"),
        "news_before_as_of_pass": _rule("NEWS_AVAILABLE_BEFORE_AS_OF", observations=(news(),)),
        "news_after_as_of_fail": _rule("NEWS_AVAILABLE_BEFORE_AS_OF", observations=(news(published_at=AS_OF.replace(year=2027)),)),
        "news_timestamp_unknown": _rule("NEWS_TIMESTAMP_KNOWN", observations=(news(published_at=None, source_time=AS_OF.replace(minute=22)),)),
        "required_domains_pass": _rule("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(present=(CoverageDomain.MARKET_BARS,)),)),
        "required_domain_missing": _rule("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(missing=(CoverageDomain.MARKET_BARS,)),)),
        "required_domain_conflicted": _rule("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(conflicted=(CoverageDomain.MARKET_BARS,)),)),
        "required_history_insufficient": _rule("REQUIRED_HISTORY_SUFFICIENT", readiness=(sufficiency(insufficient=("volume-history",)),)),
        "no_default_substitution_pass": _rule("NO_DEFAULT_SUBSTITUTION"),
        "default_substitution_detected": _rule("NO_DEFAULT_SUBSTITUTION", defaults=("price",)),
    }
    earliest = evaluate_candidate(biya_request(EARLIEST), POLICY)
    latest = evaluate_candidate(biya_request(LATEST), POLICY)
    for prefix, evaluation in (("biya_earliest", earliest), ("biya_latest", latest)):
        for category, suffix in (
            (RuleCategory.MOMENTUM_DISCOVERY, "momentum_results"),
            (RuleCategory.SHORT_PRESSURE_CONFIRMATION, "short_pressure_results"),
            (RuleCategory.CATALYST_EVIDENCE, "catalyst_results"),
            (RuleCategory.EVIDENCE_VALIDITY, "validity_results"),
        ):
            results[f"{prefix}_{suffix}"] = tuple(
                item for item in evaluation.rule_results if item.category is category
            )
        results[f"{prefix}_complete_evaluation"] = evaluation
    results["mixed_phase_3a_output"] = tuple(results[name] for name in sorted(results))
    results["serialized_phase_3a_collection"] = canonical_json_bytes(
        [results[name] for name in sorted(results)]
    )
    return results


def _hash(value):
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return canonical_hash(value)


def generate():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DEFAULT_POLICY_PATH, OUT / "phase_3a_default_policy.json")
    evidence = canonical_json_bytes({
        "record_type": "observation", "data": bar("8").model_dump(mode="json")
    }) + b"\n"
    (OUT / "phase_3a_synthetic_evidence.jsonl").write_bytes(evidence)

    results = build_anchor_results()
    earliest = results["biya_earliest_complete_evaluation"]
    latest = results["biya_latest_complete_evaluation"]
    (OUT / "biya_earliest_boundary_evaluation.json").write_bytes(serialize_candidate_evaluation(earliest))
    (OUT / "biya_latest_boundary_evaluation.json").write_bytes(serialize_candidate_evaluation(latest))
    for label, boundary in (("earliest", EARLIEST), ("latest", LATEST)):
        request = biya_request(boundary)
        records = [
            canonical_json_bytes({"record_type": "observation", "data": item.model_dump(mode="json")})
            for item in request.input_observations
        ] + [
            canonical_json_bytes({"record_type": "readiness", "data": item.model_dump(mode="json")})
            for item in request.input_readiness_results
        ]
        (OUT / f"biya_{label}_evidence.jsonl").write_bytes(b"\n".join(records) + b"\n")

    cli_request = RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=POLICY.enabled_rule_ids,
        provider_scope=("provider-a",), input_observations=(bar("8"),),
    )
    cli_result = evaluate_candidate(cli_request, POLICY)
    cli_bytes = serialize_candidate_evaluation(cli_result)
    (OUT / "phase_3a_cli_output.json").write_bytes(cli_bytes)
    results["phase_3a_cli_output"] = cli_bytes

    rule_names = tuple(name for name, value in results.items() if hasattr(value, "rule_id"))
    (OUT / "phase_3a_rule_cases.json").write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0", "classification": "SYNTHETIC_EDGE_CASE",
        "case_names": rule_names,
    }))
    (OUT / "phase_3a_candidate_cases.json").write_bytes(canonical_json_bytes({
        "schema_version": "1.0.0",
        "cases": {
            "biya_earliest": "SANITIZED_PUBLIC_HISTORICAL_DATA",
            "biya_latest": "SANITIZED_PUBLIC_HISTORICAL_DATA",
            "mixed_phase_3a_output": "SYNTHETIC_EDGE_CASE",
        },
    }))
    metadata = {
        "schema_version": "1.0.0",
        "policy_version": POLICY.policy_version,
        "hash_algorithm": "sha256-canonical-json",
        "anchors": {name: _hash(value) for name, value in sorted(results.items())},
    }
    (OUT / "expected_phase_3a_evaluation_metadata.json").write_bytes(canonical_json_bytes(metadata))
    files = tuple(sorted(path.name for path in OUT.iterdir() if path.is_file()))
    fixture_metadata = {
        "schema_version": "1.0.0",
        "classifications": {
            "biya_earliest_boundary_evaluation.json": "SANITIZED_PUBLIC_HISTORICAL_DATA",
            "biya_earliest_evidence.jsonl": "SANITIZED_PUBLIC_HISTORICAL_DATA",
            "biya_latest_boundary_evaluation.json": "SANITIZED_PUBLIC_HISTORICAL_DATA",
            "biya_latest_evidence.jsonl": "SANITIZED_PUBLIC_HISTORICAL_DATA",
            "expected_phase_3a_evaluation_metadata.json": "SANITIZED_LOCAL_ARTIFACT",
            "phase_3a_candidate_cases.json": "SANITIZED_LOCAL_ARTIFACT",
            "phase_3a_cli_output.json": "SYNTHETIC_EDGE_CASE",
            "phase_3a_default_policy.json": "SANITIZED_LOCAL_ARTIFACT",
            "phase_3a_fixture_metadata.json": "SANITIZED_LOCAL_ARTIFACT",
            "phase_3a_rule_cases.json": "SYNTHETIC_EDGE_CASE",
            "phase_3a_synthetic_evidence.jsonl": "SYNTHETIC_EDGE_CASE",
        },
        "files": files,
        "historical_sources_by_reference": [
            "tests/fixtures/validation/outcome_amendment/biya_market_bars_intraday.jsonl",
            "tests/fixtures/validation/outcome_amendment/biya_news.jsonl",
            "tests/fixtures/validation/outcome_amendment/biya_corporate_actions.jsonl",
        ],
    }
    (OUT / "phase_3a_fixture_metadata.json").write_bytes(canonical_json_bytes(fixture_metadata))
    return metadata


if __name__ == "__main__":
    print(json.dumps(generate(), sort_keys=True, separators=(",", ":")))
