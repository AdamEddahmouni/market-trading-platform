"""Static broker adapter inventory for BUILD 28 zero-submit certification."""

from __future__ import annotations

from dataclasses import dataclass

from .types import AccountEnvironment, BrokerCapabilityStatus


@dataclass(frozen=True)
class BrokerInventoryEntry:
    broker: str
    adapter_module: str
    market_data: bool
    paper: bool
    live_capable_code: bool
    preview_what_if: bool
    cancel: bool
    replace: bool
    current_status: BrokerCapabilityStatus
    credential_dependency: str
    default_environment: AccountEnvironment
    notes: str = ""


BROKER_INVENTORY: tuple[BrokerInventoryEntry, ...] = (
    BrokerInventoryEntry(
        broker="tradier.paper",
        adapter_module="market_platform_foundation.providers.adapters.tradier_paper",
        market_data=False,
        paper=True,
        live_capable_code=False,
        preview_what_if=False,
        cancel=True,
        replace=False,
        current_status=BrokerCapabilityStatus.LIVE_CERTIFIABLE_DRY_RUN,
        credential_dependency="IMP_TRADIER_TOKEN",
        default_environment=AccountEnvironment.SANDBOX,
        notes="Sandbox fixture-only; production endpoint blocked",
    ),
    BrokerInventoryEntry(
        broker="moomoo.paper",
        adapter_module="market_platform_foundation.providers.adapters.moomoo_paper",
        market_data=False,
        paper=True,
        live_capable_code=False,
        preview_what_if=False,
        cancel=True,
        replace=False,
        current_status=BrokerCapabilityStatus.LIVE_CERTIFIABLE_DRY_RUN,
        credential_dependency="IMP_MOOMOO_PAPER_TRADE_ENV",
        default_environment=AccountEnvironment.SIMULATED,
        notes="Simulated trade env only; live brokerage env blocked",
    ),
    BrokerInventoryEntry(
        broker="moomoo.observational",
        adapter_module="market_platform_foundation.market_data.live_runtime",
        market_data=True,
        paper=False,
        live_capable_code=False,
        preview_what_if=False,
        cancel=False,
        replace=False,
        current_status=BrokerCapabilityStatus.MARKET_DATA_ONLY,
        credential_dependency="IMP_MOOMOO_LIVE",
        default_environment=AccountEnvironment.UNKNOWN,
        notes="Read-only observational market data",
    ),
    BrokerInventoryEntry(
        broker="ibkr.observational",
        adapter_module="tools.ibkr.client",
        market_data=True,
        paper=False,
        live_capable_code=False,
        preview_what_if=False,
        cancel=False,
        replace=False,
        current_status=BrokerCapabilityStatus.MARKET_DATA_ONLY,
        credential_dependency="IMP_IBKR_LIVE",
        default_environment=AccountEnvironment.UNKNOWN,
        notes="Observational only; no execution adapter in src/",
    ),
    BrokerInventoryEntry(
        broker="tastytrade",
        adapter_module="",
        market_data=False,
        paper=False,
        live_capable_code=False,
        preview_what_if=False,
        cancel=False,
        replace=False,
        current_status=BrokerCapabilityStatus.UNSUPPORTED,
        credential_dependency="",
        default_environment=AccountEnvironment.UNKNOWN,
        notes="No adapter present",
    ),
    BrokerInventoryEntry(
        broker="internal.simulator",
        adapter_module="market_platform_foundation.paper.execution",
        market_data=False,
        paper=True,
        live_capable_code=False,
        preview_what_if=True,
        cancel=True,
        replace=False,
        current_status=BrokerCapabilityStatus.PAPER_ONLY,
        credential_dependency="IMP_PAPER_EXECUTION",
        default_environment=AccountEnvironment.PAPER,
        notes="Internal bar-conservative simulator; not a broker",
    ),
)

LIVE_SUBMIT_OPERATIONS: tuple[str, ...] = (
    "place_order",
    "submit_order",
    "modify_order",
    "replace_order",
    "cancel_order",
)


def inventory_by_broker(broker: str) -> BrokerInventoryEntry | None:
    for entry in BROKER_INVENTORY:
        if entry.broker == broker:
            return entry
    return None
