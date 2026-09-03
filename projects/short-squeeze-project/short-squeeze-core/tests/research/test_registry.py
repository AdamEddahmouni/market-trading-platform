import pytest
from pydantic import ValidationError

from squeeze_core.research.models import OrderingPolicy
from squeeze_core.research.registry import (
    ResearchRegistryError,
    build_case_registry,
    resolve_registry_cases,
)

from .test_models import entry


def test_registry_rejects_duplicate_case_ids():
    with pytest.raises(ValidationError, match="RESEARCH_CASE_DUPLICATE"):
        build_case_registry("phase_3b_case_registry.v1", (entry(), entry()))


def test_registry_resolves_only_explicit_ids_in_declared_order():
    registry = build_case_registry(
        "phase_3b_case_registry.v1",
        (entry(case_id="CASE-B"), entry(case_id="CASE-A", symbol="TESTA")),
    )
    requested = resolve_registry_cases(
        registry, ("CASE-B", "CASE-A"), OrderingPolicy.REQUEST_ORDER
    )
    canonical = resolve_registry_cases(
        registry, ("CASE-B", "CASE-A"), OrderingPolicy.CANONICAL_CASE_ID
    )
    assert [item.case_id for item in requested] == ["CASE-B", "CASE-A"]
    assert [item.case_id for item in canonical] == ["CASE-A", "CASE-B"]
    with pytest.raises(ResearchRegistryError) as error:
        resolve_registry_cases(registry, ("CASE-C",), OrderingPolicy.REQUEST_ORDER)
    assert error.value.code == "RESEARCH_CASE_UNKNOWN"


def test_registry_rejects_duplicate_requested_case_ids():
    registry = build_case_registry("phase_3b_case_registry.v1", (entry(),))
    with pytest.raises(ResearchRegistryError) as error:
        resolve_registry_cases(registry, ("CASE-A", "CASE-A"), OrderingPolicy.REQUEST_ORDER)
    assert error.value.code == "RESEARCH_CASE_DUPLICATE"
