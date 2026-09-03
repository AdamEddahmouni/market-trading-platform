from squeeze_core.analysis.missingness import build_registry_data_quality
from tests.analysis.helpers import load_registry


def _by_case(summary):
    return {item.case_id: item for item in summary.registry_cases}


def test_registry_quality_counts_complete_synthetic_partial_and_blocked_cases():
    summary = build_registry_data_quality(load_registry())
    assert summary.registered_case_count == 19
    assert summary.complete_case_count == 18
    assert summary.synthetic_case_count == 11
    assert summary.partial_case_count == 0
    assert summary.blocked_case_count == 1
    assert summary.conflicting_identity_count == 1
    assert summary.unknown_platform_status_count > 0


def test_incomplete_real_symbols_remain_visible_without_fabricated_evidence():
    cases = _by_case(build_registry_data_quality(load_registry()))
    assert set(cases) >= {
        "KLOS_IDENTITY_CONFLICT",
    }
    for case_id in (
        "KLOS_IDENTITY_CONFLICT",
    ):
        case = cases[case_id]
        assert not case.detection_time_evidence_available
        assert not case.evaluation_available
        assert not case.outcome_available
        assert case.exclusion_reason
        assert case.required_evidence
    assert cases["KLOS_IDENTITY_CONFLICT"].identity_conflict


def test_complete_historical_cases_remain_analyzable_but_limited():
    cases = _by_case(build_registry_data_quality(load_registry()))
    earliest = cases["BIYA_EARLIEST_BOUNDARY"]
    assert earliest.detection_time_evidence_available
    assert earliest.evaluation_available
    assert earliest.outcome_available
    assert earliest.exclusion_reason is None
    assert "published short interest" in " ".join(earliest.required_evidence).lower()


def test_registry_quality_is_order_invariant_and_deterministic():
    registry = load_registry()
    reversed_registry = registry.model_construct(
        schema_version=registry.schema_version,
        registry_version=registry.registry_version,
        entries=tuple(reversed(registry.entries)),
        deterministic_id=registry.deterministic_id,
    )
    first = build_registry_data_quality(registry)
    second = build_registry_data_quality(reversed_registry)
    assert first == second
    assert first.deterministic_id == second.deterministic_id

