"""OF-03 operator capabilities. Inspection only — no workflow executor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import OF03Error, OF03ErrorCode
from .loader import LoadedRegistry, inspect_capability, load_registry, snapshot_payload
from .status import status_payload

CAPABILITY_IDS = frozenset(
    {
        "OF03.OP.STATUS",
        "OF03.OP.VALIDATE",
        "OF03.OP.LIST_CAPABILITIES",
        "OF03.OP.LIST_SOPS",
        "OF03.OP.LIST_WORKFLOWS",
        "OF03.OP.SHOW_DEFINITION",
        "OF03.OP.SNAPSHOT",
        "OF03.OP.VERIFY_BINDINGS",
        "OF03.OP.CHECK_DRIFT",
    }
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    outcome_code: str
    capability_id: str
    verification: Mapping[str, Any]


def execute(
    capability_id: str,
    *,
    registry: LoadedRegistry | None = None,
    arguments: Mapping[str, Any] | None = None,
) -> OperationResult:
    if capability_id not in CAPABILITY_IDS:
        raise OF03Error(OF03ErrorCode.UNKNOWN_CAPABILITY, "unknown operator capability", {"capability_id": capability_id})
    arguments = dict(arguments or {})
    if capability_id == "OF03.OP.VALIDATE":
        try:
            loaded = registry or load_registry(fail_closed=True)
        except OF03Error as exc:
            return OperationResult("INVALID", capability_id, {"error": exc.message, "details": dict(exc.details)})
        payload = status_payload(loaded)
        return OperationResult("OK" if payload["valid"] else "INVALID", capability_id, payload)
    loaded = registry or load_registry(fail_closed=True)
    if capability_id == "OF03.OP.STATUS":
        return OperationResult("OK", capability_id, status_payload(loaded))
    if capability_id == "OF03.OP.LIST_CAPABILITIES":
        rows = [
            {
                "capability_id": cap.capability_id,
                "definition_version": cap.definition_version,
                "definition_hash": cap.definition_hash,
                "active": loaded.active_capabilities.get(cap.capability_id) == cap.definition_version,
                "owner_subsystem": cap.owner_subsystem,
                "automation_policy": cap.automation_policy.value,
                "effect_class": cap.effect_class.value,
                "binding_kind": cap.binding.binding_kind.value,
                **inspect_capability(loaded, cap),
            }
            for cap in loaded.capabilities
        ]
        return OperationResult("OK", capability_id, {"capabilities": rows})
    if capability_id == "OF03.OP.LIST_SOPS":
        rows = [
            {
                "sop_id": sop.sop_id,
                "definition_version": sop.definition_version,
                "definition_hash": sop.definition_hash,
                "active": loaded.active_sops.get(sop.sop_id) == sop.definition_version,
                "maturity": sop.maturity.value,
                "document_path": sop.document_path,
            }
            for sop in loaded.sops
        ]
        return OperationResult("OK", capability_id, {"sops": rows})
    if capability_id == "OF03.OP.LIST_WORKFLOWS":
        rows = [
            {
                "workflow_id": wf.workflow_id,
                "definition_version": wf.definition_version,
                "definition_hash": wf.definition_hash,
                "active": loaded.active_workflows.get(wf.workflow_id) == wf.definition_version,
                "entry_step_id": wf.entry_step_id,
                "step_count": len(wf.steps),
            }
            for wf in loaded.workflows
        ]
        return OperationResult("OK", capability_id, {"workflows": rows})
    if capability_id == "OF03.OP.SHOW_DEFINITION":
        return OperationResult("OK", capability_id, _show(loaded, arguments))
    if capability_id == "OF03.OP.SNAPSHOT":
        payload = snapshot_payload(loaded)
        payload["registry_snapshot_hash"] = loaded.snapshot_hash
        return OperationResult("OK", capability_id, payload)
    if capability_id == "OF03.OP.VERIFY_BINDINGS":
        reports = [inspect_capability(loaded, cap) for cap in loaded.capabilities]
        return OperationResult("OK", capability_id, {"bindings": reports, "invoked": False})
    if capability_id == "OF03.OP.CHECK_DRIFT":
        drift = [f for f in loaded.findings if "drift" in str(f.get("message", "")).lower() or "missing" in str(f.get("message", "")).lower()]
        return OperationResult("OK", capability_id, {"findings": drift})
    raise OF03Error(OF03ErrorCode.UNKNOWN_CAPABILITY, "unhandled capability", {"capability_id": capability_id})


def _show(registry: LoadedRegistry, arguments: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(arguments.get("kind", ""))
    ident = str(arguments.get("id", ""))
    version = arguments.get("version")
    if arguments.get("use_active") and version is None:
        if kind == "capability":
            item = registry.active_capability(ident)
            return {"kind": kind, "definition": dict(item.raw), "definition_hash": item.definition_hash}
        if kind == "sop":
            version = registry.active_sops[ident]
            item = registry.sop(ident, version)
            return {"kind": kind, "definition": dict(item.raw), "definition_hash": item.definition_hash}
        if kind == "workflow":
            version = registry.active_workflows[ident]
            item = registry.workflow(ident, version)
            return {"kind": kind, "definition": dict(item.raw), "definition_hash": item.definition_hash}
    if not isinstance(version, int):
        raise OF03Error(OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED, "exact version required (or --active)", {"kind": kind, "id": ident})
    if kind == "capability":
        item = registry.capability(ident, version)
        return {"kind": kind, "definition": dict(item.raw), "definition_hash": item.definition_hash}
    if kind == "sop":
        item = registry.sop(ident, version)
        return {"kind": kind, "definition": dict(item.raw), "definition_hash": item.definition_hash}
    if kind == "workflow":
        item = registry.workflow(ident, version)
        return {"kind": kind, "definition": dict(item.raw), "definition_hash": item.definition_hash}
    raise OF03Error(OF03ErrorCode.INVALID_COMMAND, "unknown definition kind", {"kind": kind})
