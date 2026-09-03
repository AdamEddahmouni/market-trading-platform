"""Broker capability certification (BUILD 28 zero-submit)."""

from __future__ import annotations

from .broker_inventory import BROKER_INVENTORY, BrokerInventoryEntry
from .identity import derive_certification_id
from .types import (
    LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    BrokerCapabilityCertificationV1,
    BrokerCapabilityStatus,
    BrokerCertificationDisposition,
    CertificationMode,
    CERTIFIED_ASSET_CLASSES,
)


def certify_broker(entry: BrokerInventoryEntry) -> BrokerCapabilityCertificationV1:
    """Produce zero-submit capability certification for one broker."""
    limitations: list[str] = []
    tested: list[str] = []
    untested: list[str] = []

    if entry.market_data:
        tested.append("market_data")
    if entry.paper:
        tested.append("paper")
    if entry.cancel:
        tested.append("cancel_dry_run")
    else:
        untested.append("cancel")

    if entry.replace:
        untested.append("replace_not_certified")
    else:
        limitations.append("REPLACE_NOT_CERTIFIED")

    if entry.preview_what_if:
        tested.append("preview")
    else:
        untested.append("broker_preview_what_if")
        limitations.append("BROKER_PREVIEW_NOT_IMPLEMENTED")

    if entry.live_capable_code:
        untested.append("live_transport")
        limitations.append("LIVE_TRANSPORT_DISABLED")
    else:
        tested.append("dry_run_translation")

    if entry.current_status == BrokerCapabilityStatus.MARKET_DATA_ONLY:
        disposition = BrokerCertificationDisposition.ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS
        limitations.append("MARKET_DATA_ONLY_NO_EXECUTION")
    elif entry.current_status == BrokerCapabilityStatus.UNSUPPORTED:
        disposition = BrokerCertificationDisposition.INSUFFICIENT_BROKER_CAPABILITY
    elif entry.current_status == BrokerCapabilityStatus.UNAVAILABLE:
        disposition = BrokerCertificationDisposition.ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS
        limitations.append("BROKER_UNAVAILABLE_LOCALLY")
    elif entry.current_status in {
        BrokerCapabilityStatus.LIVE_CERTIFIABLE_DRY_RUN,
        BrokerCapabilityStatus.PAPER_ONLY,
    }:
        disposition = BrokerCertificationDisposition.ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS
    else:
        disposition = BrokerCertificationDisposition.ZERO_SUBMIT_SAFETY_CERTIFIED_WITH_LIMITATIONS

    cert = BrokerCapabilityCertificationV1(
        certification_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        broker=entry.broker,
        adapter_version="build28-inventory-v1",
        asset_classes=CERTIFIED_ASSET_CLASSES if entry.paper or entry.live_capable_code else (),
        supports_market_data=entry.market_data,
        supports_order_preview=entry.preview_what_if,
        supports_what_if=False,
        supports_paper=entry.paper,
        supports_live_transport=entry.live_capable_code,
        supports_cancel=entry.cancel,
        supports_replace=entry.replace,
        account_environment=entry.default_environment,
        account_identity_available=False,
        client_order_id_support=entry.paper or entry.live_capable_code,
        idempotency_support=entry.paper or entry.live_capable_code,
        certification_mode=CertificationMode.ZERO_SUBMIT,
        tested_capabilities=tuple(tested),
        untested_capabilities=tuple(untested),
        limitations=tuple(limitations),
        disposition=disposition,
        implementation_version=LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
        lineage={"inventory_module": entry.adapter_module},
        metadata={"notes": entry.notes},
    )
    object.__setattr__(cert, "certification_id", derive_certification_id(cert))
    return cert


def certify_all_brokers() -> tuple[BrokerCapabilityCertificationV1, ...]:
    return tuple(certify_broker(entry) for entry in BROKER_INVENTORY)
