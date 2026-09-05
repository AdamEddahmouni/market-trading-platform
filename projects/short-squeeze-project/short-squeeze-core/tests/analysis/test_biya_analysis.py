from squeeze_core.analysis import AnalysisCohortType, AnalysisUnit, SampleSizeState
from squeeze_core.analysis.reports import render_markdown_report
from squeeze_core.analysis.runner import run_research_analysis
from tests.analysis.helpers import analysis_request, load_dataset

_PEER_HISTORICAL_SYMBOLS = ("BIYA", "KLRS", "LBGJ", "SG", "SLS", "TRVI")


def _run(analysis_unit):
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


def test_biya_case_boundary_analysis_reports_both_dependent_results():
    dataset_rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    assert tuple(row.case_id for row in dataset_rows) == (
        "BIYA_ARTIFACT_DISCOVERY",
        "BIYA_EARLIEST_BOUNDARY",
        "BIYA_LATEST_BOUNDARY",
    )
    assert {row.research_detection_status.value for row in dataset_rows} == {
        "DETECTED", "UNEVALUABLE",
    }
    assert {row.outcome_label.value for row in dataset_rows} == {
        "SUBSTANTIAL_UPWARD_MOVE", "SUBSTANTIAL_DOWNWARD_MOVE",
    }
    assert {row.research_classification.value for row in dataset_rows} == {
        "TRUE_POSITIVE", "UNEVALUABLE",
    }

    result = _run(AnalysisUnit.CASE_BOUNDARY)
    assert result.case_count == 31
    assert result.symbol_dependence_summary.dependence_detected
    assert not result.symbol_dependence_summary.independence_assumption_satisfied
    assert result.confusion_matrix.true_positive_count == 2
    assert result.confusion_matrix.unevaluable_count == 29
    missing_by_domain = {
        item.domain_id: item for item in result.domain_missingness_summary
    }
    assert missing_by_domain["PUBLISHED_SHORT_INTEREST"].missing_count == 0
    assert missing_by_domain["BORROW_FEE"].missing_count == 31
    report = render_markdown_report(result).decode("utf-8")
    assert "dependent observations of the same symbol" in report
    assert "not independent performance samples" in report
    assert "partial 24-hour observation windows" in report


_PEER_HISTORICAL_SYMBOLS = ("BIYA", "KLRS", "LBGJ", "SG", "SLS", "TRVI")


def test_biya_unique_symbol_analysis_is_outcome_blind_sample_of_one():
    result = _run(AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY)
    assert result.case_count == 29
    assert result.boundary_selection.selected_case_ids == (
        "ADVB_ARTIFACT_DISCOVERY",
        "APVO_ARTIFACT_DISCOVERY",
        "ATAI_ARTIFACT_DISCOVERY",
        "AVTX_ARTIFACT_DISCOVERY",
        "BHVN_ARTIFACT_DISCOVERY",
        "BIYA_EARLIEST_BOUNDARY",
        "CADL_ARTIFACT_DISCOVERY",
        "CELZ_ARTIFACT_DISCOVERY",
        "CGEM_ARTIFACT_DISCOVERY",
        "GDC_ARTIFACT_DISCOVERY",
        "GOAI_ARTIFACT_DISCOVERY",
        "GPRE_ARTIFACT_DISCOVERY",
        "IOVA_ARTIFACT_DISCOVERY",
        "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY",
        "LMNX_ARTIFACT_DISCOVERY",
        "MGNX_ARTIFACT_DISCOVERY",
        "NXXT_ARTIFACT_DISCOVERY",
        "OBE_ARTIFACT_DISCOVERY",
        "PESI_ARTIFACT_DISCOVERY",
        "PMAX_ARTIFACT_DISCOVERY",
        "SG_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY",
        "SSPC_ARTIFACT_DISCOVERY",
        "STAK_ARTIFACT_DISCOVERY",
        "TRVI_ARTIFACT_DISCOVERY",
        "VMAR_ARTIFACT_DISCOVERY",
        "XNCR_ARTIFACT_DISCOVERY",
        "ZNTL_ARTIFACT_DISCOVERY",
    )
    assert result.boundary_selection.excluded_case_ids == (
        "BIYA_ARTIFACT_DISCOVERY",
        "BIYA_LATEST_BOUNDARY",
    )
    assert result.boundary_selection.outcome_blind
    assert result.boundary_selection.policy_version == "earliest_detection_boundary_per_symbol.v1"
    assert result.sample_size_assessments[0].state is SampleSizeState.LIMITED
    assert result.confusion_matrix.true_positive_count == 1
    report = render_markdown_report(result).decode("utf-8")
    assert (
        "BIYA demonstrates that the deterministic pipeline can preserve a detected case "
        "and a later substantial move without injecting outcome information into the original evaluation."
    ) in report
    assert "It does not validate squeeze causation or general predictive performance." in report
