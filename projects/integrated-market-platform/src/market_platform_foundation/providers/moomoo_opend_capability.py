"""Moomoo OpenD observational capability registration (G7 hop L1).

Registers ``moomoo.opend.observational`` through ``ProviderRegistry`` as
implemented ``US_EQUITY_L1``. Yahoo delayed overlay is intentionally not
registered here — it is never hop L1. Execution capability is never
registered. OpenD-down remains fail-closed at fetch and, until a hop stamps
runtime health, at G7 selection.
"""

from __future__ import annotations

from .registry import CapabilityDescriptor, ProviderDescriptor, ProviderRegistry

MOOMOO_OPEND_PROVIDER_ID = "moomoo.opend.observational"
US_EQUITY_L1_CAPABILITY = "US_EQUITY_L1"
MOOMOO_OPEND_NORMALIZER_VERSION = "market_data/moomoo/1.0.0"

#: Capabilities IMP never registers for OpenD (execution authority).
MOOMOO_OPEND_FORBIDDEN_CAPABILITIES = frozenset(
    {"MOOMOO_EXECUTION", "MOOMOO_ORDER_MANAGEMENT", "MOOMOO_ACCOUNT_TRADING"}
)


def register_moomoo_opend_observational(
    registry: ProviderRegistry | None = None,
) -> ProviderDescriptor:
    """Register (or return) the OpenD observational hop-L1 descriptor."""
    store = registry or ProviderRegistry()
    capabilities = (
        CapabilityDescriptor(
            capability_id=US_EQUITY_L1_CAPABILITY,
            asset_classes=("EQUITY",),
            venues=("US_EQUITY",),
            interfaces=("opend_quote",),
            supports_history=False,
            supports_pit=False,
            freshness_sla_ns=1_000_000_000,
            license_class="RESTRICTED",
            rate_policy_id="moomoo.opend.observational.quote",
            normalizer_version=MOOMOO_OPEND_NORMALIZER_VERSION,
        ),
    )
    descriptor = ProviderDescriptor(
        provider_id=MOOMOO_OPEND_PROVIDER_ID,
        display_name="Moomoo OpenD observational equity L1",
        capabilities=capabilities,
        health_state="UNKNOWN",
        credential_refs=(),
        schema_versions=(MOOMOO_OPEND_NORMALIZER_VERSION,),
        priority=80,
    )
    store.register(descriptor)
    return descriptor


__all__ = [
    "MOOMOO_OPEND_FORBIDDEN_CAPABILITIES",
    "MOOMOO_OPEND_NORMALIZER_VERSION",
    "MOOMOO_OPEND_PROVIDER_ID",
    "US_EQUITY_L1_CAPABILITY",
    "register_moomoo_opend_observational",
]
