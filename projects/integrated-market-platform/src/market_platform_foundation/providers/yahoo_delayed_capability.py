"""Yahoo delayed overlay capability registration (G7).

Registers ``yahoo.finance.delayed`` through ``ProviderRegistry`` as implemented
``US_EQUITY_SNAPSHOT`` — a delayed/historical overlay lane, never hop L1 and
never ``REAL_TIME``. Execution capability is never registered. Yahoo as
``OBSERVATIONAL_L1`` remains ``UNKNOWN_PROVIDER``.
"""

from __future__ import annotations

from .adapters.yahoo_delayed_equity_quote import (
    YAHOO_CAPABILITY,
    YAHOO_PROVIDER_ID,
    YAHOO_TIMELINESS,
)
from .registry import CapabilityDescriptor, ProviderDescriptor, ProviderRegistry

YAHOO_NORMALIZER_VERSION = "yahoo.finance.delayed/1.0.0"
YAHOO_LICENSE_CLASS = "RESEARCH_ONLY"

#: Capabilities IMP never registers for the Yahoo delayed overlay (execution).
YAHOO_FORBIDDEN_CAPABILITIES = frozenset(
    {"YAHOO_EXECUTION", "YAHOO_ORDER_MANAGEMENT", "YAHOO_ACCOUNT_TRADING"}
)


def register_yahoo_delayed_capability(
    registry: ProviderRegistry | None = None,
) -> ProviderDescriptor:
    """Register (or return) the Yahoo delayed overlay descriptor."""
    store = registry or ProviderRegistry()
    capabilities = (
        CapabilityDescriptor(
            capability_id=YAHOO_CAPABILITY,
            asset_classes=("EQUITY",),
            venues=("US_EQUITY",),
            interfaces=("yahoo_chart",),
            supports_history=True,
            supports_pit=False,
            freshness_sla_ns=None,
            license_class=YAHOO_LICENSE_CLASS,
            rate_policy_id="yahoo.finance.delayed.chart",
            normalizer_version=YAHOO_NORMALIZER_VERSION,
        ),
    )
    descriptor = ProviderDescriptor(
        provider_id=YAHOO_PROVIDER_ID,
        display_name="Yahoo Finance delayed equity overlay",
        capabilities=capabilities,
        health_state="UNKNOWN",
        credential_refs=(),
        schema_versions=(YAHOO_NORMALIZER_VERSION,),
        priority=200,
    )
    store.register(descriptor)
    return descriptor


__all__ = [
    "YAHOO_CAPABILITY",
    "YAHOO_FORBIDDEN_CAPABILITIES",
    "YAHOO_LICENSE_CLASS",
    "YAHOO_NORMALIZER_VERSION",
    "YAHOO_PROVIDER_ID",
    "YAHOO_TIMELINESS",
    "register_yahoo_delayed_capability",
]
