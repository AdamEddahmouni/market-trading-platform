from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import pytest

from squeeze_core.analysis import AnalysisUnit
from squeeze_core.analysis.identifiers import deterministic_analysis_id
from tests.analysis.test_models import _request


class IdentityEnum(StrEnum):
    VALUE = "VALUE"


@dataclass(frozen=True)
class Unsupported:
    value: str


def test_identity_is_stable_and_supports_contract_scalar_types():
    identity = {
        "decimal": Decimal("0.95"),
        "enum": IdentityEnum.VALUE,
        "timestamp": datetime(2026, 7, 22, tzinfo=timezone.utc),
    }
    assert deterministic_analysis_id(identity) == deterministic_analysis_id(identity)


def test_source_ids_and_policy_choices_are_independent_identity_inputs():
    base = {
        "source_dataset_id": "dataset-a",
        "source_registry_id": "registry-a",
        "analysis_unit": AnalysisUnit.CASE_BOUNDARY,
    }
    assert deterministic_analysis_id(base) != deterministic_analysis_id(
        {**base, "source_dataset_id": "dataset-b"}
    )
    assert deterministic_analysis_id(base) != deterministic_analysis_id(
        {**base, "source_registry_id": "registry-b"}
    )
    assert deterministic_analysis_id(base) != deterministic_analysis_id(
        {**base, "analysis_unit": AnalysisUnit.UNIQUE_SYMBOL}
    )


def test_request_identity_is_input_order_invariant_for_set_like_fields():
    first = _request(AnalysisUnit.CASE_BOUNDARY)
    values = first.model_dump(exclude={"deterministic_id"})
    values["included_statistics"] = tuple(reversed(values["included_statistics"]))
    values["excluded_statistics"] = tuple(reversed(values["excluded_statistics"]))
    second = type(first)(**values)
    assert first.deterministic_id == second.deterministic_id


def test_unique_symbol_units_have_distinct_request_identities():
    aggregate = _request(AnalysisUnit.UNIQUE_SYMBOL)
    selected = _request(AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY)
    assert aggregate.deterministic_id != selected.deterministic_id


def test_absolute_paths_and_unrestricted_types_are_not_identity_values():
    with pytest.raises(TypeError, match="unsupported analysis identity value"):
        deterministic_analysis_id({"path": Path("C:/private/source.json")})
    with pytest.raises(TypeError, match="unsupported analysis identity value"):
        deterministic_analysis_id({"object": Unsupported("value")})

