"""OF-03 strategy-family registry. Metadata only — not authorization or mint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from market_platform_foundation.canonical import load_json_strict

from .canonical import SCHEMA_VERSION, definition_hash_from_obj, snapshot_hash_from_obj
from .contracts import Binding
from .enums import BindingKind, RegistrationState
from .errors import OF03Error, OF03ErrorCode
from .loader import default_registry_root

REGISTRY_ID = "OF03.STRATEGY_FAMILY"
ADMISSION_KIND_METADATA_ONLY = "METADATA_ONLY"
ADMITTED_REASON = "METADATA_ONLY_ADMITTED"

CORE_CONTRACT_FIELDS: tuple[str, ...] = (
    "opportunity_id",
    "strategy_family",
    "strategy_version",
    "instrument_key",
    "asset_class",
    "decision_time",
    "information_cutoff",
    "direction_or_expression",
    "horizon",
    "mechanism",
    "summary",
    "evidence_class",
    "data_quality",
    "eligibility_state",
)

_ALLOWED_FAMILY_BINDINGS = frozenset({BindingKind.UNBOUND, BindingKind.DOCUMENTED_MANUAL_OPERATION})


def _req_str(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"missing {key}", {"key": key})
    return value.strip()


def _str_tuple(obj: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = obj.get(key, ())
    if value is None:
        return ()
    if not isinstance(value, list):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{key} must be a list", {"key": key})
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"invalid {key} item", {"key": key})
        out.append(item.strip())
    return tuple(out)


def _req_bool(obj: Mapping[str, Any], key: str, *, expected: bool) -> bool:
    value = obj.get(key)
    if not isinstance(value, bool):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{key} must be bool", {"key": key})
    if value is not expected:
        raise OF03Error(
            OF03ErrorCode.REGISTRY_INVALID,
            f"{key} must be {expected} for metadata-only families",
            {"key": key, "value": value},
        )
    return value


def _field_present(fixture: Mapping[str, Any], key: str) -> bool:
    if key not in fixture:
        return False
    value = fixture[key]
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (dict, list, tuple)) and len(value) == 0:
        return False
    return True


@dataclass(frozen=True, slots=True)
class StrategyFamilyDefinition:
    schema_version: int
    family_id: str
    definition_version: int
    title: str
    description: str
    owner_subsystem: str
    registration_state: RegistrationState
    binding: Binding
    required_contract_fields: tuple[str, ...]
    admission_kind: str
    production_evaluator: bool
    mints_opportunity_v1: bool
    mints_forecast_v1: bool
    definition_hash: str
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "StrategyFamilyDefinition":
        version = obj.get("definition_version")
        if not isinstance(version, int) or version < 1:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "invalid definition_version", {})
        schema = obj.get("schema_version", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "schema-version incompatibility", {"schema_version": schema})
        admission_kind = _req_str(obj, "admission_kind")
        if admission_kind != ADMISSION_KIND_METADATA_ONLY:
            raise OF03Error(
                OF03ErrorCode.REGISTRY_INVALID,
                "admission_kind must be METADATA_ONLY",
                {"admission_kind": admission_kind},
            )
        binding = Binding.from_mapping(obj.get("binding") or {})
        if binding.binding_kind not in _ALLOWED_FAMILY_BINDINGS:
            raise OF03Error(
                OF03ErrorCode.UNSAFE_BINDING,
                "strategy families may not bind PYTHON_API or CLI executors",
                {"binding_kind": binding.binding_kind.value},
            )
        fields = _str_tuple(obj, "required_contract_fields")
        missing_core = [name for name in CORE_CONTRACT_FIELDS if name not in fields]
        if missing_core:
            raise OF03Error(
                OF03ErrorCode.REGISTRY_INVALID,
                "required_contract_fields must include Opportunity Contract core fields",
                {"missing": missing_core},
            )
        computed = definition_hash_from_obj(obj)
        declared = obj.get("definition_hash")
        if declared is not None and declared != computed:
            raise OF03Error(
                OF03ErrorCode.REGISTRY_INVALID,
                "definition hash mismatch",
                {"family_id": obj.get("family_id")},
            )
        return cls(
            schema_version=SCHEMA_VERSION,
            family_id=_req_str(obj, "family_id"),
            definition_version=version,
            title=_req_str(obj, "title"),
            description=_req_str(obj, "description"),
            owner_subsystem=_req_str(obj, "owner_subsystem"),
            registration_state=RegistrationState(str(obj.get("registration_state", "DECLARED"))),
            binding=binding,
            required_contract_fields=fields,
            admission_kind=admission_kind,
            production_evaluator=_req_bool(obj, "production_evaluator", expected=False),
            mints_opportunity_v1=_req_bool(obj, "mints_opportunity_v1", expected=False),
            mints_forecast_v1=_req_bool(obj, "mints_forecast_v1", expected=False),
            definition_hash=computed,
            raw=dict(obj),
        )


@dataclass(frozen=True, slots=True)
class LoadedStrategyFamilyRegistry:
    schema_version: int
    registry_id: str
    root: Path
    families: tuple[StrategyFamilyDefinition, ...]
    active_families: Mapping[str, int]
    snapshot_hash: str

    def family(self, family_id: str, version: int) -> StrategyFamilyDefinition:
        for item in self.families:
            if item.family_id == family_id and item.definition_version == version:
                return item
        raise OF03Error(
            OF03ErrorCode.UNKNOWN_STRATEGY_FAMILY,
            "unknown strategy family version",
            {"family_id": family_id, "version": version},
        )

    def resolve_family(self, family_id: str, version: int | None) -> StrategyFamilyDefinition:
        if version is None:
            raise OF03Error(
                OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED,
                "exact family definition_version required",
                {"family_id": family_id},
            )
        return self.family(family_id, version)

    def active_family(self, family_id: str) -> StrategyFamilyDefinition:
        if family_id not in self.active_families:
            raise OF03Error(
                OF03ErrorCode.UNKNOWN_STRATEGY_FAMILY,
                "no active strategy family",
                {"family_id": family_id},
            )
        return self.family(family_id, self.active_families[family_id])


@dataclass(frozen=True, slots=True)
class StrategyFamilyAdmission:
    admitted: bool
    family_id: str
    definition_version: int
    definition_hash: str
    admission_kind: str
    reason_code: str
    strategy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "family_id": self.family_id,
            "definition_version": self.definition_version,
            "definition_hash": self.definition_hash,
            "admission_kind": self.admission_kind,
            "reason_code": self.reason_code,
            "strategy_version": self.strategy_version,
            "mints_opportunity_v1": False,
            "mints_forecast_v1": False,
            "production_evaluator": False,
        }


def default_strategy_family_path(root: Path | None = None) -> Path:
    return (root or default_registry_root()) / "strategy_families.json"


def strategy_family_snapshot_obj(registry: LoadedStrategyFamilyRegistry) -> dict[str, Any]:
    return {
        "registry_id": registry.registry_id,
        "registry_schema_version": registry.schema_version,
        "active_families": dict(sorted(registry.active_families.items())),
        "families": [
            {
                "family_id": item.family_id,
                "definition_version": item.definition_version,
                "definition_hash": item.definition_hash,
            }
            for item in sorted(registry.families, key=lambda row: (row.family_id, row.definition_version))
        ],
    }


def load_strategy_family_registry(
    root: Path | None = None,
    *,
    fail_closed: bool = True,
) -> LoadedStrategyFamilyRegistry:
    path = default_strategy_family_path(root)
    payload = load_json_strict(path)
    if not isinstance(payload, dict):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "strategy family registry must be an object", {})
    schema = payload.get("schema_version", SCHEMA_VERSION)
    if schema != SCHEMA_VERSION:
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "schema-version incompatibility", {"schema_version": schema})
    registry_id = _req_str(payload, "registry_id")
    if registry_id != REGISTRY_ID:
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "unexpected registry_id", {"registry_id": registry_id})
    raw_families = payload.get("families")
    if not isinstance(raw_families, list):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "families must be a list", {})
    families = tuple(StrategyFamilyDefinition.from_mapping(item) for item in raw_families)
    seen: set[tuple[str, int]] = set()
    for item in families:
        key = (item.family_id, item.definition_version)
        if key in seen:
            raise OF03Error(
                OF03ErrorCode.REGISTRY_INVALID,
                "duplicate strategy family version",
                {"family_id": item.family_id, "definition_version": item.definition_version},
            )
        seen.add(key)
    active_raw = payload.get("active_families")
    if not isinstance(active_raw, dict):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "active_families must be an object", {})
    active_families: dict[str, int] = {}
    for key, value in active_raw.items():
        if not isinstance(key, str) or not isinstance(value, int):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "invalid active_families entry", {"key": key})
        active_families[key] = value
    loaded = LoadedStrategyFamilyRegistry(
        schema_version=SCHEMA_VERSION,
        registry_id=REGISTRY_ID,
        root=path.parent,
        families=families,
        active_families=active_families,
        snapshot_hash="",
    )
    snapshot_hash = snapshot_hash_from_obj(strategy_family_snapshot_obj(loaded))
    loaded = LoadedStrategyFamilyRegistry(
        schema_version=loaded.schema_version,
        registry_id=loaded.registry_id,
        root=loaded.root,
        families=loaded.families,
        active_families=loaded.active_families,
        snapshot_hash=snapshot_hash,
    )
    findings: list[str] = []
    for family_id, version in active_families.items():
        try:
            loaded.family(family_id, version)
        except OF03Error:
            findings.append(f"active pointer missing:{family_id}:{version}")
    declared = payload.get("registry_snapshot_hash")
    if declared is not None and declared != snapshot_hash:
        findings.append("snapshot hash mismatch")
    if fail_closed and findings:
        raise OF03Error(
            OF03ErrorCode.REGISTRY_INVALID,
            "strategy family registry invalid",
            {"findings": findings, "snapshot_hash": snapshot_hash},
        )
    return loaded


def admit_strategy_family_fixture(
    fixture: Mapping[str, Any],
    *,
    registry: LoadedStrategyFamilyRegistry | None = None,
) -> StrategyFamilyAdmission:
    """Admit a strategy fixture as metadata. Does not mint OpportunityV1 or ForecastV1."""

    store = registry or load_strategy_family_registry(fail_closed=True)
    family_id = fixture.get("strategy_family")
    if not isinstance(family_id, str) or not family_id.strip():
        raise OF03Error(
            OF03ErrorCode.MISSING_CONTRACT_FIELD,
            "missing strategy_family",
            {"field": "strategy_family"},
        )
    family_id = family_id.strip()
    version = fixture.get("family_definition_version")
    if version is None:
        raise OF03Error(
            OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED,
            "exact family definition_version required",
            {"family_id": family_id},
        )
    if not isinstance(version, int):
        raise OF03Error(
            OF03ErrorCode.REGISTRY_INVALID,
            "family_definition_version must be int",
            {"family_id": family_id},
        )
    family = store.resolve_family(family_id, version)
    missing = [name for name in family.required_contract_fields if not _field_present(fixture, name)]
    if missing:
        raise OF03Error(
            OF03ErrorCode.MISSING_CONTRACT_FIELD,
            "strategy fixture missing required contract fields",
            {"family_id": family_id, "missing": missing},
        )
    strategy_version = str(fixture["strategy_version"]).strip()
    return StrategyFamilyAdmission(
        admitted=True,
        family_id=family.family_id,
        definition_version=family.definition_version,
        definition_hash=family.definition_hash,
        admission_kind=family.admission_kind,
        reason_code=ADMITTED_REASON,
        strategy_version=strategy_version,
    )


__all__ = [
    "ADMISSION_KIND_METADATA_ONLY",
    "ADMITTED_REASON",
    "CORE_CONTRACT_FIELDS",
    "LoadedStrategyFamilyRegistry",
    "REGISTRY_ID",
    "StrategyFamilyAdmission",
    "StrategyFamilyDefinition",
    "admit_strategy_family_fixture",
    "load_strategy_family_registry",
]
