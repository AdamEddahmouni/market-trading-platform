from squeeze_core.research.matrices import build_rule_outcome_matrix
from squeeze_core.research.models import OrderingPolicy

from .test_batch import complete_entry, request, write_registry
from squeeze_core.research.batch import run_research_batch


def test_matrix_preserves_one_textual_outcome_per_phase_3a_rule(tmp_path):
    registry_path = write_registry(tmp_path, (complete_entry(),))
    batch = run_research_batch(request(ordering=OrderingPolicy.REQUEST_ORDER), registry_path)
    matrix = build_rule_outcome_matrix(batch)
    case = batch.case_results[0]
    assert matrix.rule_ids == tuple(item.rule_id for item in case.phase_3a_rule_results)
    assert matrix.rows[0].case_id == case.case_id
    assert tuple(matrix.rows[0].rule_outcomes) == matrix.rule_ids
    assert set(matrix.rows[0].rule_outcomes.values()) <= {
        "PASS", "FAIL", "UNKNOWN", "CONFLICTED", "INSUFFICIENT_DATA", "NOT_APPLICABLE"
    }
    assert matrix.deterministic_id == build_rule_outcome_matrix(batch).deterministic_id
