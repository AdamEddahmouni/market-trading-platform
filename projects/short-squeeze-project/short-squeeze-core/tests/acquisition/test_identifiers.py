from datetime import UTC, datetime

from squeeze_core.acquisition.identifiers import deterministic_acquisition_id


def test_identity_is_order_invariant_for_mapping_keys_and_set_like_tuples():
    first = {
        "result_type": "PLAN",
        "criteria": {"date_range": ("2024-01-01", "2024-12-31"), "sources": ("B", "A")},
    }
    second = {
        "criteria": {"sources": ("A", "B"), "date_range": ("2024-01-01", "2024-12-31")},
        "result_type": "PLAN",
    }
    assert deterministic_acquisition_id(first) == deterministic_acquisition_id(second)


def test_identity_changes_when_semantic_criteria_change():
    first = deterministic_acquisition_id({"policy_version": "v1", "maximum_case_count": 20})
    second = deterministic_acquisition_id({"policy_version": "v1", "maximum_case_count": 21})
    assert first != second


def test_absolute_paths_and_informational_time_are_not_accepted_identity_inputs():
    value = {
        "artifact_id": "artifact-1",
        "relative_path": "raw/source.json",
        "absolute_path": "C:/private/source.json",
        "informational_created_at": datetime(2026, 7, 22, tzinfo=UTC),
    }
    identity = deterministic_acquisition_id(value)
    changed = {
        **value,
        "absolute_path": "D:/elsewhere/source.json",
        "informational_created_at": datetime(2030, 1, 1, tzinfo=UTC),
    }
    assert identity == deterministic_acquisition_id(changed)
