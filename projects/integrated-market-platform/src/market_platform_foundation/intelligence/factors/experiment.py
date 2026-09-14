"""Factor experiment manifest: searched family and temporal partitions.

The untouched test partition may not be used for hyperparameter,
preprocessing, universe, or factor-family choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    dataclass_field_names,
    normalize_unique_strings,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from .errors import FactorContractError
from .identity import EXPERIMENT_ID_PREFIX, IDENTITY_VERSION, factor_hash
from .promotion import assert_research_only


def experiment_identity_payload(
    *,
    schema_version: str,
    hypothesis_family_id: str,
    construction_spec_ids: tuple[str, ...],
    searched_family_size: int,
    discovery_start_ns: int,
    discovery_end_ns: int,
    validation_start_ns: int,
    validation_end_ns: int,
    untouched_test_start_ns: int,
    untouched_test_end_ns: int,
) -> dict[str, Any]:
    return {
        "identity_version": IDENTITY_VERSION,
        "schema_version": schema_version,
        "hypothesis_family_id": hypothesis_family_id,
        "construction_spec_ids": list(construction_spec_ids),
        "searched_family_size": searched_family_size,
        "discovery_start_ns": discovery_start_ns,
        "discovery_end_ns": discovery_end_ns,
        "validation_start_ns": validation_start_ns,
        "validation_end_ns": validation_end_ns,
        "untouched_test_start_ns": untouched_test_start_ns,
        "untouched_test_end_ns": untouched_test_end_ns,
    }


def derive_experiment_id_from_payload(payload: dict[str, Any]) -> str:
    return factor_hash(payload, prefix=EXPERIMENT_ID_PREFIX)


def _require_ordered_window(start_ns: int, end_ns: int, *, name: str) -> None:
    validate_timestamp_ns(start_ns, field_name=f"{name}_start_ns")
    validate_timestamp_ns(end_ns, field_name=f"{name}_end_ns")
    if end_ns <= start_ns:
        raise FactorContractError(f"FACTOR_{name.upper()}_WINDOW_INVALID")


@dataclass(frozen=True, slots=True)
class FactorExperimentManifestV1:
    """Registered search family plus frozen train/validation/test clocks."""

    experiment_id: str
    schema_version: str
    hypothesis_family_id: str
    construction_spec_ids: tuple[str, ...]
    searched_family_size: int
    discovery_start_ns: int
    discovery_end_ns: int
    validation_start_ns: int
    validation_end_ns: int
    untouched_test_start_ns: int
    untouched_test_end_ns: int

    def __post_init__(self) -> None:
        validate_id(self.experiment_id, field_name="experiment_id")
        validate_schema_version(self.schema_version)
        validate_id(self.hypothesis_family_id, field_name="hypothesis_family_id")
        object.__setattr__(
            self, "construction_spec_ids", normalize_unique_strings(self.construction_spec_ids)
        )
        if not self.construction_spec_ids:
            raise FactorContractError("FACTOR_EXPERIMENT_SPEC_REQUIRED")
        if not isinstance(self.searched_family_size, int) or self.searched_family_size < 1:
            raise FactorContractError("FACTOR_SEARCHED_FAMILY_SIZE_INVALID")
        if self.searched_family_size < len(self.construction_spec_ids):
            raise FactorContractError("FACTOR_SEARCHED_FAMILY_UNDERCOUNTED")
        _require_ordered_window(self.discovery_start_ns, self.discovery_end_ns, name="discovery")
        _require_ordered_window(self.validation_start_ns, self.validation_end_ns, name="validation")
        _require_ordered_window(
            self.untouched_test_start_ns, self.untouched_test_end_ns, name="untouched_test"
        )
        if self.validation_start_ns < self.discovery_end_ns:
            raise FactorContractError("FACTOR_VALIDATION_OVERLAPS_DISCOVERY")
        if self.untouched_test_start_ns < self.validation_end_ns:
            raise FactorContractError("FACTOR_TEST_OVERLAPS_VALIDATION")
        expected = derive_experiment_id_from_payload(
            experiment_identity_payload(
                schema_version=self.schema_version,
                hypothesis_family_id=self.hypothesis_family_id,
                construction_spec_ids=self.construction_spec_ids,
                searched_family_size=self.searched_family_size,
                discovery_start_ns=self.discovery_start_ns,
                discovery_end_ns=self.discovery_end_ns,
                validation_start_ns=self.validation_start_ns,
                validation_end_ns=self.validation_end_ns,
                untouched_test_start_ns=self.untouched_test_start_ns,
                untouched_test_end_ns=self.untouched_test_end_ns,
            )
        )
        if self.experiment_id != expected:
            raise FactorContractError("FACTOR_EXPERIMENT_IDENTITY_MISMATCH")
        assert_research_only()


def build_experiment_manifest(
    *,
    hypothesis_family_id: str,
    construction_spec_ids: tuple[str, ...],
    searched_family_size: int,
    discovery_start_ns: int,
    discovery_end_ns: int,
    validation_start_ns: int,
    validation_end_ns: int,
    untouched_test_start_ns: int,
    untouched_test_end_ns: int,
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION,
) -> FactorExperimentManifestV1:
    specs = tuple(normalize_unique_strings(construction_spec_ids))
    payload = experiment_identity_payload(
        schema_version=schema_version,
        hypothesis_family_id=hypothesis_family_id,
        construction_spec_ids=specs,
        searched_family_size=searched_family_size,
        discovery_start_ns=discovery_start_ns,
        discovery_end_ns=discovery_end_ns,
        validation_start_ns=validation_start_ns,
        validation_end_ns=validation_end_ns,
        untouched_test_start_ns=untouched_test_start_ns,
        untouched_test_end_ns=untouched_test_end_ns,
    )
    return FactorExperimentManifestV1(
        experiment_id=derive_experiment_id_from_payload(payload),
        schema_version=schema_version,
        hypothesis_family_id=hypothesis_family_id,
        construction_spec_ids=specs,
        searched_family_size=searched_family_size,
        discovery_start_ns=discovery_start_ns,
        discovery_end_ns=discovery_end_ns,
        validation_start_ns=validation_start_ns,
        validation_end_ns=validation_end_ns,
        untouched_test_start_ns=untouched_test_start_ns,
        untouched_test_end_ns=untouched_test_end_ns,
    )


_EXP_ALLOWED = dataclass_field_names(FactorExperimentManifestV1)


def experiment_manifest_to_dict(record: FactorExperimentManifestV1) -> dict[str, Any]:
    return {
        "experiment_id": record.experiment_id,
        "schema_version": record.schema_version,
        "hypothesis_family_id": record.hypothesis_family_id,
        "construction_spec_ids": list(record.construction_spec_ids),
        "searched_family_size": record.searched_family_size,
        "discovery_start_ns": record.discovery_start_ns,
        "discovery_end_ns": record.discovery_end_ns,
        "validation_start_ns": record.validation_start_ns,
        "validation_end_ns": record.validation_end_ns,
        "untouched_test_start_ns": record.untouched_test_start_ns,
        "untouched_test_end_ns": record.untouched_test_end_ns,
    }


def experiment_manifest_from_dict(payload: dict[str, Any]) -> FactorExperimentManifestV1:
    reject_unknown_keys(payload, _EXP_ALLOWED)
    return FactorExperimentManifestV1(
        experiment_id=str(payload["experiment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        hypothesis_family_id=str(payload["hypothesis_family_id"]),
        construction_spec_ids=tuple(payload.get("construction_spec_ids") or ()),
        searched_family_size=int(payload["searched_family_size"]),
        discovery_start_ns=int(payload["discovery_start_ns"]),
        discovery_end_ns=int(payload["discovery_end_ns"]),
        validation_start_ns=int(payload["validation_start_ns"]),
        validation_end_ns=int(payload["validation_end_ns"]),
        untouched_test_start_ns=int(payload["untouched_test_start_ns"]),
        untouched_test_end_ns=int(payload["untouched_test_end_ns"]),
    )


__all__ = [
    "FactorExperimentManifestV1",
    "build_experiment_manifest",
    "derive_experiment_id_from_payload",
    "experiment_identity_payload",
    "experiment_manifest_from_dict",
    "experiment_manifest_to_dict",
]
