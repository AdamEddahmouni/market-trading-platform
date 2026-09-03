"""Frozen Research mode must reproduce the Batch 08 freeze exactly.

Every assertion here is a meeting-critical claim: if one fails, the number the screener
shows a reader is not the number that was frozen.

These tests need the private artifact root. When it is absent they skip rather than
inventing fixtures, because a fixture would not prove the real artifacts are intact.
"""

from __future__ import annotations

import pytest

from apps.research_screener.frozen import FrozenResearchSource
from apps.research_screener.paths import FrozenLayout
from apps.research_screener.truth import MISSING_PLACEHOLDER

pytestmark = pytest.mark.skipif(
    not FrozenLayout().available, reason="private frozen artifact root not present"
)

EXPECTED_SYMBOLS = {
    "AVTX", "BHVN", "GPRE", "LBGJ", "LMNX", "MGNX", "OBE",
    "PESI", "SLS", "SSPC", "TRVI", "XNCR", "ZNTL",
}
PERCENTAGE_CHANGE_PASS = {"XNCR", "PESI", "SLS", "SSPC", "LBGJ", "TRVI"}
PERCENTAGE_CHANGE_FAIL = {"ZNTL", "GPRE", "LMNX", "MGNX", "BHVN", "OBE", "AVTX"}


@pytest.fixture(scope="module")
def source() -> FrozenResearchSource:
    frozen = FrozenResearchSource()
    frozen.load()
    return frozen


def test_exactly_thirteen_cases_load(source: FrozenResearchSource) -> None:
    rows = source.screener_rows()
    assert len(rows) == 13
    assert {row["symbol"] for row in rows} == EXPECTED_SYMBOLS


def test_every_case_exposes_all_twenty_five_rules(source: FrozenResearchSource) -> None:
    canonical = source.canonical_rule_order
    assert len(canonical) == 25
    for case in source.cases:
        table = source.rule_table(case["case_id"])
        assert [row["rule_id"] for row in table] == canonical


def test_outcome_totals_match_the_batch_08_freeze(source: FrozenResearchSource) -> None:
    totals = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    pairs = 0
    for case in source.cases:
        for rule in source.rule_table(case["case_id"]):
            totals[rule["outcome"]] = totals.get(rule["outcome"], 0) + 1
            pairs += 1
    assert pairs == 325
    assert totals == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}


def test_percentage_change_split_is_exactly_six_pass_seven_fail(
    source: FrozenResearchSource,
) -> None:
    outcomes: dict[str, str] = {}
    for case in source.cases:
        for rule in source.rule_table(case["case_id"]):
            if rule["rule_id"] == "PERCENTAGE_CHANGE_MINIMUM":
                outcomes[case["symbol"]] = rule["outcome"]
    assert {s for s, o in outcomes.items() if o == "PASS"} == PERCENTAGE_CHANGE_PASS
    assert {s for s, o in outcomes.items() if o == "FAIL"} == PERCENTAGE_CHANGE_FAIL


def test_availability_rules_pass_for_every_case(source: FrozenResearchSource) -> None:
    for case in source.cases:
        by_id = {rule["rule_id"]: rule for rule in source.rule_table(case["case_id"])}
        assert by_id["MARKET_DATA_AVAILABLE"]["outcome"] == "PASS"
        assert by_id["COMPLETED_BAR_AVAILABLE"]["outcome"] == "PASS"


def test_short_pressure_and_catalyst_totals_are_all_unknown(
    source: FrozenResearchSource,
) -> None:
    counts = {"SHORT_PRESSURE_CONFIRMATION": 0, "CATALYST_EVIDENCE": 0}
    for case in source.cases:
        for rule in source.rule_table(case["case_id"]):
            if rule["category"] in counts:
                assert rule["outcome"] == "UNKNOWN"
                counts[rule["category"]] += 1
    assert counts == {"SHORT_PRESSURE_CONFIRMATION": 91, "CATALYST_EVIDENCE": 65}


def test_rule_outcomes_match_the_frozen_result_files_byte_for_byte(
    source: FrozenResearchSource,
) -> None:
    """The table is a view of the frozen result, not a re-derivation of it."""
    for case in source.cases:
        frozen = source._results[case["case_id"]]
        by_id = {rule["rule_id"]: rule for rule in frozen["rule_results"]}
        for row in source.rule_table(case["case_id"]):
            original = by_id[row["rule_id"]]
            assert row["outcome"] == original["outcome"]
            assert row["observed_value"] == original["observed_value"]
            assert row["category"] == original["category"]


def test_xncr_is_present_and_drilldown_is_complete(source: FrozenResearchSource) -> None:
    detail = source.detail("XNCR")
    assert detail is not None
    assert detail["identity"]["case_id"] == "BATCH01_XNCR_20260718"
    assert len(detail["rules"]) == 25
    assert detail["research_detection"]["status"] == "UNEVALUABLE"
    assert detail["outcome"]["status"] == "INCOMPLETE"
    assert detail["provenance"]["global_preflight_status"] == "PREFLIGHT_REJECTED"


def test_research_detection_is_unevaluable_for_all_thirteen(
    source: FrozenResearchSource,
) -> None:
    statuses = [row["research_detection"]["status"] for row in source.screener_rows()]
    assert statuses == ["UNEVALUABLE"] * 13


def test_outcome_is_incomplete_for_all_thirteen(source: FrozenResearchSource) -> None:
    for row in source.screener_rows():
        assert row["outcome"]["status"] == "INCOMPLETE"
        assert row["outcome"]["reasons"], "an INCOMPLETE outcome must say why"


def test_global_preflight_is_displayed_truthfully(source: FrozenResearchSource) -> None:
    assert source.summary["global_preflight_verdict"] == "PREFLIGHT_REJECTED"
    for row in source.screener_rows():
        assert row["global_preflight_status"] == "PREFLIGHT_REJECTED"


def test_missing_values_never_become_zero(source: FrozenResearchSource) -> None:
    for row in source.screener_rows():
        for name, field in row["fields"].items():
            if field["status"] == "KNOWN":
                continue
            assert field["value"] is None, f"{row['symbol']}.{name} carries a value"
            assert field["display"] == MISSING_PLACEHOLDER
            assert field["missing_reason"], f"{row['symbol']}.{name} has no reason"


def test_unknown_rules_never_render_as_pass(source: FrozenResearchSource) -> None:
    for case in source.cases:
        for rule in source.rule_table(case["case_id"]):
            if rule["outcome"] == "UNKNOWN":
                assert rule["observed_value"] is None
                assert rule["observed_display"] == MISSING_PLACEHOLDER
                assert rule["reason"], "an UNKNOWN rule must state why"


def test_every_case_reports_no_forward_or_outcome_access(
    source: FrozenResearchSource,
) -> None:
    for case in source.cases:
        assert case["forward_ohlcv_accessed"] is False
        assert case["outcome_accessed"] is False
        assert case["phase3b_published"] is False
        assert case["phase3e_started"] is False


def test_schema_version_is_1_0_0(source: FrozenResearchSource) -> None:
    assert source.summary["schema_version"] == "1.0.0"
    for case in source.cases:
        assert case["schema_version"] == "1.0.0"


def test_chart_uses_detection_context_only(source: FrozenResearchSource) -> None:
    chart = source.chart("XNCR")
    assert chart["available"] is True
    assert chart["request_name"] == "DETECTION_CONTEXT_PRECEDING_24H"
    assert chart["forward_window_shown"] is False
    assert chart["points"], "the chart must plot real bars"
    assert chart["boundary_label"] == "Detection Boundary"


def test_professor_summary_matches_the_meeting_numbers(
    source: FrozenResearchSource,
) -> None:
    summary = source.professor_summary()
    assert summary["case_count"] == 13
    assert summary["evaluation_count"] == 13
    assert summary["rule_case_pairs"] == 325
    assert summary["outcome_totals"] == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}
    assert summary["by_category"]["SHORT_PRESSURE_CONFIRMATION"]["UNKNOWN"] == 91
    assert summary["by_category"]["CATALYST_EVIDENCE"]["UNKNOWN"] == 65
    assert summary["research_detection_counts"] == {"UNEVALUABLE": 13}
    assert summary["outcome_counts"] == {"INCOMPLETE": 13}
    assert summary["global_preflight_verdict"] == "PREFLIGHT_REJECTED"
    assert summary["phase3b_published"] is False
    assert summary["phase3e_started"] is False
    assert set(summary["percentage_change_split"]["PASS"]) == PERCENTAGE_CHANGE_PASS
    assert set(summary["percentage_change_split"]["FAIL"]) == PERCENTAGE_CHANGE_FAIL


def test_batch_09_preview_is_labelled_as_a_preview(source: FrozenResearchSource) -> None:
    banner = "REGISTRY REVISION PREVIEW — NOT CANONICALLY PUBLISHED"
    assert source.professor_summary()["preview_banner"] == banner
    for row in source.screener_rows():
        assert row["research_detection"]["preview_banner"] == banner
