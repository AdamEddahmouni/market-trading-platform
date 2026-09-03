import json

from squeeze_core.analysis import AnalysisCohortType, AnalysisUnit
from squeeze_core.analysis.runner import run_research_analysis
from squeeze_core.analysis.serialization import (
    deserialize_analysis_result,
    serialize_analysis_collection,
    serialize_analysis_model,
)
from tests.analysis.helpers import analysis_request, load_dataset


def _historical_result(analysis_unit=AnalysisUnit.CASE_BOUNDARY):
    dataset = load_dataset()
    request = analysis_request(
        AnalysisCohortType.HISTORICAL_COMPLETED_CASES,
        analysis_unit,
        dataset=dataset,
        included_statistics=(
            "CONFUSION_MATRIX",
            "DETECTION_PREVALENCE",
            "MISSINGNESS",
            "OUTCOME_PREVALENCE",
            "RESEARCH_CLASSIFICATION_PREVALENCE",
            "RULE_OUTCOME_PREVALENCE",
        ),
    )
    return run_research_analysis(request, dataset=dataset)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_analysis_json_is_repeated_byte_identical_and_round_trips():
    result = _historical_result()
    first = serialize_analysis_model(result)
    second = serialize_analysis_model(result)
    assert first == second
    assert deserialize_analysis_result(first) == result
    assert b"\r" not in first
    assert b"NaN" not in first and b"Infinity" not in first


def test_interval_bounds_preserve_fixed_twelve_place_serialization():
    result = _historical_result(AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY)
    serialized = serialize_analysis_model(result)
    assert b'"lower_bound":"0.206549314377"' in serialized
    assert b'"upper_bound":"1.000000000000"' in serialized
    assert b'"confidence_level":"0.95"' in serialized


def test_undefined_rates_remain_explicit_nulls_with_reasons():
    document = json.loads(serialize_analysis_model(_historical_result()))
    rates = document["confusion_matrix"]["descriptive_rates"]
    specificity = next(
        item for item in rates
        if item["metric_name"] == "specificity_descriptive_research_classification_rate"
    )
    assert specificity["defined"] is False
    assert specificity["decimal_value"] is None
    assert specificity["percentage_value"] is None
    assert specificity["undefined_reason"] == "ZERO_DENOMINATOR"


def test_source_ids_are_preserved_without_combined_source_identity():
    document = json.loads(serialize_analysis_model(_historical_result()))
    assert document["source_dataset_id"]
    assert document["source_registry_id"] is None
    assert "combined_source_id" not in set(_walk_keys(document))


def test_runtime_schema_contains_no_prohibited_output_fields():
    document = json.loads(serialize_analysis_model(_historical_result()))
    keys = set(_walk_keys(document))
    assert not keys.intersection({
        "candidate_score",
        "candidate_rank",
        "rule_importance_score",
        "threshold_recommendation",
        "trade_recommendation",
        "alert_priority",
        "expected_return",
        "pnl",
        "backtest",
    })


def test_collection_serialization_is_input_order_invariant():
    case_result = _historical_result(AnalysisUnit.CASE_BOUNDARY)
    symbol_result = _historical_result(
        AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY
    )
    assert serialize_analysis_collection((case_result, symbol_result)) == (
        serialize_analysis_collection((symbol_result, case_result))
    )

