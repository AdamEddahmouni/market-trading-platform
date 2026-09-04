"""BUILD 28 live execution safety spec builder."""

from __future__ import annotations

from ..system_acceptance import contract_inventory_hash
from .broker_inventory import BROKER_INVENTORY
from .identity import derive_safety_spec_id
from .types import (
    LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    CERTIFIED_ASSET_CLASSES,
    CERTIFIED_ORDER_TYPES,
    CertificationMode,
    LiveExecutionSafetySpecV1,
)

BUILD27_BRANCH = "cloud/build-27-forward-paper-execution"
BUILD26_BRANCH = "cloud/build-26-forward-shadow-qualification"
BUILD25_RC_BRANCH = "cloud/build-25-system-acceptance-freeze"


def build_live_execution_safety_spec(
    *,
    source_build27_ref: str,
    source_build26_ref: str,
    source_release_candidate_ref: str,
    source_head: str,
) -> LiveExecutionSafetySpecV1:
    certifiable_brokers = tuple(
        entry.broker
        for entry in BROKER_INVENTORY
        if entry.current_status.value not in {"UNSUPPORTED"}
    )
    spec = LiveExecutionSafetySpecV1(
        spec_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        source_build27_ref=source_build27_ref,
        source_build26_ref=source_build26_ref,
        source_release_candidate_ref=source_release_candidate_ref,
        source_head=source_head,
        contract_inventory_hash=contract_inventory_hash(),
        certification_mode=CertificationMode.ZERO_SUBMIT,
        certified_asset_classes=CERTIFIED_ASSET_CLASSES,
        certified_order_types=CERTIFIED_ORDER_TYPES,
        required_brokers=certifiable_brokers,
        implementation_version=LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(spec, "spec_id", derive_safety_spec_id(spec))
    return spec
