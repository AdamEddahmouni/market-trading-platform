"""OF-01/OF-02 provenance reference helpers. Not a second ledger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .loader import LoadedRegistry


@dataclass(frozen=True, slots=True)
class CapabilityReference:
    capability_id: str
    definition_version: int
    definition_hash: str
    registry_snapshot_hash: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "definition_version": self.definition_version,
            "definition_hash": self.definition_hash,
            "registry_snapshot_hash": self.registry_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class WorkflowReference:
    workflow_id: str
    workflow_version: int
    workflow_definition_hash: str
    registry_snapshot_hash: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "workflow_definition_hash": self.workflow_definition_hash,
            "registry_snapshot_hash": self.registry_snapshot_hash,
        }


def capability_reference(registry: LoadedRegistry, capability_id: str, version: int) -> CapabilityReference:
    cap = registry.capability(capability_id, version)
    return CapabilityReference(
        capability_id=cap.capability_id,
        definition_version=cap.definition_version,
        definition_hash=cap.definition_hash,
        registry_snapshot_hash=registry.snapshot_hash,
    )


def workflow_reference(registry: LoadedRegistry, workflow_id: str, version: int) -> WorkflowReference:
    workflow = registry.workflow(workflow_id, version)
    return WorkflowReference(
        workflow_id=workflow.workflow_id,
        workflow_version=workflow.definition_version,
        workflow_definition_hash=workflow.definition_hash,
        registry_snapshot_hash=registry.snapshot_hash,
    )


def registry_snapshot_extra(registry: LoadedRegistry) -> dict[str, Any]:
    return {
        "of03_registry_schema_version": registry.schema_version,
        "registry_snapshot_hash": registry.snapshot_hash,
    }
