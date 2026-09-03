"""Load version-controlled OF-03 JSON. JSON is canonical; this module is the typed loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from market_platform_foundation.canonical import load_json_strict

from .availability import availability_for
from .bindings import verify_binding
from .canonical import SCHEMA_VERSION, snapshot_hash_from_obj
from .contracts import CapabilityDefinition, SopDefinition, WorkflowDefinition
from .enums import AvailabilityState, BindingKind, FindingSeverity, RegistrationState
from .errors import OF03Error, OF03ErrorCode
from .validation import errors_only, validate_loaded


def default_registry_root() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "of03"


def default_repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class LoadedRegistry:
    schema_version: int
    root: Path
    repository_root: Path
    capabilities: tuple[CapabilityDefinition, ...]
    sops: tuple[SopDefinition, ...]
    workflows: tuple[WorkflowDefinition, ...]
    active_capabilities: Mapping[str, int]
    active_sops: Mapping[str, int]
    active_workflows: Mapping[str, int]
    findings: tuple[dict[str, Any], ...]
    snapshot_hash: str

    def capability(self, capability_id: str, version: int) -> CapabilityDefinition:
        for item in self.capabilities:
            if item.capability_id == capability_id and item.definition_version == version:
                return item
        raise OF03Error(OF03ErrorCode.UNKNOWN_DEFINITION, "unknown capability version", {"capability_id": capability_id, "version": version})

    def sop(self, sop_id: str, version: int) -> SopDefinition:
        for item in self.sops:
            if item.sop_id == sop_id and item.definition_version == version:
                return item
        raise OF03Error(OF03ErrorCode.UNKNOWN_DEFINITION, "unknown SOP version", {"sop_id": sop_id, "version": version})

    def workflow(self, workflow_id: str, version: int) -> WorkflowDefinition:
        for item in self.workflows:
            if item.workflow_id == workflow_id and item.definition_version == version:
                return item
        raise OF03Error(OF03ErrorCode.UNKNOWN_DEFINITION, "unknown workflow version", {"workflow_id": workflow_id, "version": version})

    def active_capability(self, capability_id: str) -> CapabilityDefinition:
        if capability_id not in self.active_capabilities:
            raise OF03Error(OF03ErrorCode.UNKNOWN_DEFINITION, "no active capability", {"capability_id": capability_id})
        return self.capability(capability_id, self.active_capabilities[capability_id])

    def resolve_capability(self, capability_id: str, version: int | None) -> CapabilityDefinition:
        if version is None:
            raise OF03Error(OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED, "exact version required", {"capability_id": capability_id})
        return self.capability(capability_id, version)

    def is_valid(self) -> bool:
        return not errors_only(self.findings)


def load_registry(
    root: Path | None = None,
    *,
    repository_root: Path | None = None,
    verify_bindings: bool = True,
    fail_closed: bool = True,
) -> LoadedRegistry:
    root = root or default_registry_root()
    repository_root = repository_root or default_repository_root()
    manifest = _as_object(load_json_strict(root / "manifest.json"), "manifest")
    schema = manifest.get("registry_schema_version", SCHEMA_VERSION)
    if schema != SCHEMA_VERSION:
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "schema-version incompatibility", {"registry_schema_version": schema})
    capabilities = _load_defs(root / "capabilities.json", CapabilityDefinition.from_mapping, "capabilities")
    sops = _load_defs(root / "sops.json", SopDefinition.from_mapping, "sops")
    workflows = _load_defs(root / "workflows.json", WorkflowDefinition.from_mapping, "workflows")
    active_capabilities = _int_map(manifest.get("active_capabilities"), "active_capabilities")
    active_sops = _int_map(manifest.get("active_sops"), "active_sops")
    active_workflows = _int_map(manifest.get("active_workflows"), "active_workflows")
    findings = validate_loaded(
        capabilities=capabilities,
        sops=sops,
        workflows=workflows,
        active_capabilities=active_capabilities,
        active_sops=active_sops,
        active_workflows=active_workflows,
        repository_root=repository_root,
        verify_bindings=verify_bindings,
    )
    snapshot = _snapshot_obj(schema, capabilities, sops, workflows, active_capabilities, active_sops, active_workflows)
    snapshot_hash = snapshot_hash_from_obj(snapshot)
    declared = manifest.get("registry_snapshot_hash")
    if declared is not None and declared != snapshot_hash:
        findings.append({"severity": FindingSeverity.ERROR.value, "message": "snapshot hash mismatch"})
    loaded = LoadedRegistry(
        schema_version=SCHEMA_VERSION,
        root=root,
        repository_root=repository_root,
        capabilities=capabilities,
        sops=sops,
        workflows=workflows,
        active_capabilities=active_capabilities,
        active_sops=active_sops,
        active_workflows=active_workflows,
        findings=tuple(findings),
        snapshot_hash=snapshot_hash,
    )
    if fail_closed and errors_only(findings):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "registry invalid", {"findings": list(errors_only(findings)), "snapshot_hash": snapshot_hash})
    return loaded


def inspect_capability(registry: LoadedRegistry, capability: CapabilityDefinition) -> dict[str, Any]:
    report = verify_binding(capability, repository_root=registry.repository_root)
    avail = availability_for(capability, binding_ok=bool(report["ok"]) and capability.binding.binding_kind is not BindingKind.UNBOUND)
    if capability.registration_state is RegistrationState.DEPRECATED:
        avail = AvailabilityState.DEPRECATED
    bound = capability.binding.binding_kind is not BindingKind.UNBOUND and bool(report["ok"])
    return {
        "capability_id": capability.capability_id,
        "definition_version": capability.definition_version,
        "definition_hash": capability.definition_hash,
        "binding_ok": report["ok"],
        "binding_invoked": False,
        "bound": bound,
        "availability": avail.value,
        "binding_findings": report["findings"],
    }


def snapshot_payload(registry: LoadedRegistry) -> dict[str, Any]:
    return _snapshot_obj(
        registry.schema_version,
        registry.capabilities,
        registry.sops,
        registry.workflows,
        dict(registry.active_capabilities),
        dict(registry.active_sops),
        dict(registry.active_workflows),
    )


def _snapshot_obj(
    schema: int,
    capabilities: tuple[CapabilityDefinition, ...],
    sops: tuple[SopDefinition, ...],
    workflows: tuple[WorkflowDefinition, ...],
    active_capabilities: Mapping[str, int],
    active_sops: Mapping[str, int],
    active_workflows: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "registry_schema_version": schema,
        "active_capabilities": dict(sorted(active_capabilities.items())),
        "active_sops": dict(sorted(active_sops.items())),
        "active_workflows": dict(sorted(active_workflows.items())),
        "capabilities": [
            {"capability_id": c.capability_id, "definition_version": c.definition_version, "definition_hash": c.definition_hash}
            for c in sorted(capabilities, key=lambda x: (x.capability_id, x.definition_version))
        ],
        "sops": [
            {"sop_id": s.sop_id, "definition_version": s.definition_version, "definition_hash": s.definition_hash}
            for s in sorted(sops, key=lambda x: (x.sop_id, x.definition_version))
        ],
        "workflows": [
            {"workflow_id": w.workflow_id, "definition_version": w.definition_version, "definition_hash": w.definition_hash}
            for w in sorted(workflows, key=lambda x: (x.workflow_id, x.definition_version))
        ],
    }


def _load_defs(path: Path, factory: Any, context: str) -> tuple:
    payload = load_json_strict(path)
    if not isinstance(payload, list):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{context} must be a list", {})
    return tuple(factory(item) for item in payload)


def _as_object(payload: object, context: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{context} must be an object", {})
    return payload


def _int_map(raw: object, context: str) -> dict[str, int]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{context} must be an object", {})
    out: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, int):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"invalid {context} entry", {"key": key})
        out[key] = value
    return out
