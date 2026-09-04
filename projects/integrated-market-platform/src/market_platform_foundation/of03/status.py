"""Structured OF-03 registry status."""

from __future__ import annotations

from typing import Any

from .enums import AvailabilityState, FindingSeverity, RegistrationState
from .loader import LoadedRegistry, inspect_capability
from .validation import errors_only


def status_payload(registry: LoadedRegistry) -> dict[str, Any]:
    inspections = [inspect_capability(registry, cap) for cap in registry.capabilities]
    findings = list(registry.findings)
    warnings = [f for f in findings if f.get("severity") == FindingSeverity.WARNING.value]
    infos = [f for f in findings if f.get("severity") == FindingSeverity.INFO.value]
    avail_counts: dict[str, int] = {state.value: 0 for state in AvailabilityState}
    bound = 0
    unbound = 0
    deprecated = 0
    for item, cap in zip(inspections, registry.capabilities, strict=True):
        avail_counts[item["availability"]] += 1
        if item["bound"]:
            bound += 1
        else:
            unbound += 1
        if cap.deprecation.deprecated or cap.registration_state is RegistrationState.DEPRECATED:
            deprecated += 1
    sop_deprecated = sum(1 for s in registry.sops if s.deprecation.deprecated)
    wf_deprecated = sum(1 for w in registry.workflows if w.deprecation.deprecated)
    return {
        "schema_version": registry.schema_version,
        "snapshot_hash": registry.snapshot_hash,
        "valid": registry.is_valid(),
        "capability_count": len(registry.capabilities),
        "sop_count": len(registry.sops),
        "workflow_count": len(registry.workflows),
        "active_capabilities": len(registry.active_capabilities),
        "active_sops": len(registry.active_sops),
        "active_workflows": len(registry.active_workflows),
        "deprecated_capabilities": deprecated,
        "deprecated_sops": sop_deprecated,
        "deprecated_workflows": wf_deprecated,
        "bound_capabilities": bound,
        "unbound_capabilities": unbound,
        "available_capabilities": avail_counts[AvailabilityState.AVAILABLE.value],
        "disabled_capabilities": avail_counts[AvailabilityState.DISABLED.value],
        "unavailable_capabilities": avail_counts[AvailabilityState.UNAVAILABLE.value],
        "validation_errors": errors_only(findings),
        "validation_warnings": warnings,
        "validation_info": infos,
        "document_drift": [f for f in warnings if "drift" in str(f.get("message", "")).lower()],
        "binding_drift": [f for f in findings if "binding" in str(f.get("message", "")).lower()],
    }
