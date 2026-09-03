from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.research.diagnostics import (
    ResearchDiagnostic,
    ResearchDiagnosticCode,
    sort_diagnostics,
)


def test_required_diagnostic_vocabulary_is_present():
    required = {
        "RESEARCH_CASE_UNKNOWN", "RESEARCH_CASE_DUPLICATE",
        "RESEARCH_CASE_STATUS_INCOMPLETE", "RESEARCH_CASE_DETECTION_TIME_UNKNOWN",
        "RESEARCH_CASE_EVALUATION_MISSING", "RESEARCH_CASE_OUTCOME_MISSING",
        "RESEARCH_CASE_PLATFORM_STATUS_UNKNOWN", "RESEARCH_CASE_IDENTITY_CONFLICT",
        "RESEARCH_DETECTION_POLICY_UNSUPPORTED",
        "RESEARCH_DETECTION_REQUIRED_RULE_UNKNOWN",
        "RESEARCH_DETECTION_REQUIRED_RULE_FAILED",
        "RESEARCH_DETECTION_REQUIRED_RULE_CONFLICTED",
        "RESEARCH_DETECTION_REQUIRED_RULE_INSUFFICIENT",
        "RESEARCH_DETECTION_UNEVALUABLE", "RESEARCH_OUTCOME_POLICY_UNSUPPORTED",
        "RESEARCH_OUTCOME_UNKNOWN", "RESEARCH_OUTCOME_INSUFFICIENT",
        "RESEARCH_OUTCOME_PARTIAL", "RESEARCH_OUTCOME_MIXED", "RESEARCH_BATCH_EMPTY",
        "RESEARCH_BATCH_PARTIAL", "RESEARCH_BATCH_CASE_FAILED",
        "RESEARCH_BATCH_CASE_SKIPPED", "RESEARCH_BATCH_SMALL_SAMPLE",
        "RESEARCH_DATASET_EMPTY", "RESEARCH_DATASET_PARTIAL",
        "RESEARCH_DATASET_SYNTHETIC_ONLY", "RESEARCH_DATASET_MIXED_PROVENANCE",
        "RESEARCH_DATASET_PUBLIC_EXPORT_REDACTED",
    }
    assert required <= {item.value for item in ResearchDiagnosticCode}


def test_diagnostics_have_stable_semantic_order():
    later = ResearchDiagnostic(
        code=ResearchDiagnosticCode.RESEARCH_CASE_UNKNOWN,
        severity=DiagnosticSeverity.ERROR,
        case_id="B",
        rule_id="R",
        field_id="F",
        input_ids=("2", "1"),
    )
    earlier = ResearchDiagnostic(
        code=ResearchDiagnosticCode.RESEARCH_BATCH_EMPTY,
        severity=DiagnosticSeverity.WARNING,
        case_id="A",
    )
    assert sort_diagnostics((later, earlier)) == (earlier, later)
    assert later.input_ids == ("1", "2")
