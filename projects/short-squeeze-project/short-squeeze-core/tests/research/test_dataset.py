from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.dataset import build_research_dataset, filter_research_dataset
from squeeze_core.research.models import ResearchCaseClassification

from .test_batch import complete_entry, request, write_registry


def test_dataset_preserves_case_policy_rules_provenance_and_stable_ids(tmp_path):
    batch = run_research_batch(request(), write_registry(tmp_path, (complete_entry(),)))
    first = build_research_dataset(batch)
    second = build_research_dataset(batch)
    assert first.deterministic_id == second.deterministic_id
    assert first.provenance.deterministic_id == second.provenance.deterministic_id
    assert len(first.rows) == 1
    row = first.rows[0]
    assert row.original_platform_status.value == "SURFACED"
    assert row.research_detection_status.value == "DETECTED"
    assert row.outcome_label.value == "SUBSTANTIAL_UPWARD_MOVE"
    assert len(row.rule_outcomes) == 25
    assert row.row_id


def test_classification_filters_preserve_canonical_rows(tmp_path):
    dataset = build_research_dataset(
        run_research_batch(request(), write_registry(tmp_path, (complete_entry(),)))
    )
    positive = filter_research_dataset(dataset, ResearchCaseClassification.TRUE_POSITIVE)
    false_positive = filter_research_dataset(dataset, ResearchCaseClassification.FALSE_POSITIVE)
    assert [row.case_id for row in positive.rows] == ["CASE-A"]
    assert false_positive.rows == ()
