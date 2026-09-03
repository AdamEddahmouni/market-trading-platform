"""Serialization for BUILD 28 live execution safety contracts."""

from __future__ import annotations

from typing import Any

from .types import LiveExecutionSafetySpecV1


def live_execution_safety_spec_v1_to_dict(spec: LiveExecutionSafetySpecV1) -> dict[str, Any]:
    return {
        "spec_id": spec.spec_id,
        "schema_version": spec.schema_version,
        "source_build27_ref": spec.source_build27_ref,
        "source_build26_ref": spec.source_build26_ref,
        "source_release_candidate_ref": spec.source_release_candidate_ref,
        "source_head": spec.source_head,
        "contract_inventory_hash": spec.contract_inventory_hash,
        "certification_mode": spec.certification_mode.value,
        "certified_asset_classes": list(spec.certified_asset_classes),
        "certified_order_types": list(spec.certified_order_types),
        "required_brokers": list(spec.required_brokers),
        "implementation_version": spec.implementation_version,
        "metadata": dict(spec.metadata),
    }
