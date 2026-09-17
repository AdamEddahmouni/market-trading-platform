"""IBKR observational capability registration (G6).

Registers IBKR capabilities through the existing provider capability registry
(``providers.registry.ProviderRegistry``). Execution capability is NEVER
registered: the registry is the single capability authority and IBKR is
observational only (CONTRACT_RESOLUTION / L1 / L2).
"""

from __future__ import annotations

from ..registry import CapabilityDescriptor, ProviderDescriptor, ProviderRegistry

IBKR_PROVIDER_ID = "ibkr.observational"

#: Capability ids registered for IBKR observational data.
IBKR_CAPABILITY_L1 = "IBKR_L1"
IBKR_CAPABILITY_L2 = "IBKR_L2"
IBKR_CAPABILITY_TRADES = "IBKR_TRADES"
IBKR_CAPABILITY_CONTRACT_RESOLUTION = "IBKR_CONTRACT_RESOLUTION"
IBKR_CAPABILITY_HISTORICAL_BARS = "IBKR_HISTORICAL_BARS"
IBKR_CAPABILITY_HISTORICAL_TRADES = "IBKR_HISTORICAL_TRADES"
IBKR_CAPABILITY_ACCOUNT_READ = "IBKR_ACCOUNT_READ"

#: Capabilities IMP never registers for IBKR (execution authority).
IBKR_FORBIDDEN_CAPABILITIES = frozenset(
    {"IBKR_EXECUTION", "IBKR_ORDER_MANAGEMENT", "IBKR_ACCOUNT_TRADING"}
)


def register_ibkr_observational(
    registry: ProviderRegistry | None = None,
) -> ProviderDescriptor:
    """Register (or return) the IBKR observational provider descriptor."""
    store = registry or ProviderRegistry()
    capabilities = (
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_TRADES,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_tws",),
            supports_history=False,
            supports_pit=False,
            freshness_sla_ns=1_000_000_000,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.local_cap",
            normalizer_version="ibkr_observational/trade_print/1.0.0",
        ),
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_CONTRACT_RESOLUTION,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_tws",),
            supports_history=False,
            supports_pit=False,
            freshness_sla_ns=None,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.local_cap",
            normalizer_version="ibkr_observational/v1",
        ),
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_L1,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_tws",),
            supports_history=False,
            supports_pit=False,
            freshness_sla_ns=1_000_000_000,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.local_cap",
            normalizer_version="ibkr_observational/v1",
        ),
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_L2,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_tws",),
            supports_history=False,
            supports_pit=False,
            freshness_sla_ns=1_000_000_000,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.local_cap",
            normalizer_version="ibkr_observational/v1",
        ),
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_HISTORICAL_BARS,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_rest", "ibkr_tws"),
            supports_history=True,
            supports_pit=True,
            freshness_sla_ns=None,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.history",
            normalizer_version="ibkr_observational/historical_bars/1.0.0",
        ),
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_HISTORICAL_TRADES,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_tws",),
            supports_history=True,
            supports_pit=True,
            freshness_sla_ns=None,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.history",
            normalizer_version="ibkr_observational/historical_trades/1.0.0",
        ),
        CapabilityDescriptor(
            capability_id=IBKR_CAPABILITY_ACCOUNT_READ,
            asset_classes=("EQUITY", "FUTURE", "OPTION"),
            venues=("SMART",),
            interfaces=("ibkr_rest",),
            supports_history=False,
            supports_pit=False,
            freshness_sla_ns=None,
            license_class="RESTRICTED",
            rate_policy_id="ibkr.pacing.rest",
            normalizer_version="ibkr_observational/account_read/1.0.0",
        ),
    )
    descriptor = ProviderDescriptor(
        provider_id=IBKR_PROVIDER_ID,
        display_name="IBKR TWS / IB Gateway observational market data",
        capabilities=capabilities,
        health_state="UNKNOWN",
        credential_refs=(),
        schema_versions=("ibkr_observational/v1",),
        priority=90,
    )
    store.register(descriptor)
    return descriptor


__all__ = [
    "IBKR_CAPABILITY_ACCOUNT_READ",
    "IBKR_CAPABILITY_CONTRACT_RESOLUTION",
    "IBKR_CAPABILITY_HISTORICAL_BARS",
    "IBKR_CAPABILITY_HISTORICAL_TRADES",
    "IBKR_CAPABILITY_L1",
    "IBKR_CAPABILITY_L2",
    "IBKR_CAPABILITY_TRADES",
    "IBKR_FORBIDDEN_CAPABILITIES",
    "IBKR_PROVIDER_ID",
    "register_ibkr_observational",
]