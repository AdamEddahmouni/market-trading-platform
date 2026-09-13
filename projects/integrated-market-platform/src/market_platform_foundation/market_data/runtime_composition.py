"""G7 — runtime composition boundary.

Defines the outer layer where concrete provider transports are injected into
canonical src adapters. Preserves G6 dependency direction: src MUST NOT import
tools/ibkr implementation logic.

Composition pattern:
    transport (injected / fake / replay)
        ↓
    IbkrObservationalAdapter (src)
        ↓
    ObservationalStateStore
        ↓
    ObservationalLaneRuntime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..providers.contracts import EquityContextProvider
from ..providers.ibkr_observational.adapter import (
    IbkrObservationalAdapter,
    IbkrObservationalConfig,
)
from ..providers.ibkr_observational.capability import IBKR_PROVIDER_ID
from ..providers.ibkr_observational.query_provider import (
    AccountObservationResult,
    ContractResolutionResult,
    HistoricalBarsResult,
    IbkrObservationalQueryService,
    IbkrReadOnlyQueryProvider,
)
from ..providers.runtime_capability import (
    CAP_L1,
    CAP_L2,
    DataTimeliness,
    EntitlementState,
    ProviderHealth,
    ProviderRuntimeState,
    RuntimeCapabilityRegistry,
)
from ..providers.runtime_selection import (
    ObservationalProviderSelector,
    ObservationalSelectionRequest,
    SelectionOutcome,
)
from ..providers.stubs import UnconfiguredEquityContextProvider
from .observational_lanes import ObservationalLaneRuntime
from .observational_state import ObservationalStateStore


class ObservationalTransport(Protocol):
    """Minimal transport surface — mirrors G6 IbkrTransport without tools import."""

    def connect(
        self, *, host: str, port: int, client_id: int, readonly: bool = True
    ) -> None: ...

    def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...


@dataclass
class ObservationalRuntimeComposition:
    """Provider-neutral observational runtime graph."""

    store: ObservationalStateStore = field(default_factory=ObservationalStateStore)
    capability_registry: RuntimeCapabilityRegistry = field(
        default_factory=RuntimeCapabilityRegistry
    )
    equity_context: EquityContextProvider = field(
        default_factory=UnconfiguredEquityContextProvider
    )
    selector: ObservationalProviderSelector = field(init=False)
    lanes: ObservationalLaneRuntime = field(init=False)
    ibkr_adapter: IbkrObservationalAdapter | None = None
    ibkr_query_service: IbkrObservationalQueryService | None = None
    active_provider_id: str | None = None
    _shutdown_complete: bool = False

    def __post_init__(self) -> None:
        self.selector = ObservationalProviderSelector(self.capability_registry)
        self.lanes = ObservationalLaneRuntime(self.store)

    def attach_ibkr_adapter(
        self,
        transport: ObservationalTransport,
        *,
        config: IbkrObservationalConfig | None = None,
        lookup: Any | None = None,
    ) -> IbkrObservationalAdapter:
        """Wire IBKR observational adapter with injected transport (no tools import)."""
        adapter = IbkrObservationalAdapter(
            config or IbkrObservationalConfig(live_enabled=False),
            transport=transport,
            store=self.store,
            lookup=lookup,
        )
        self.ibkr_adapter = adapter
        self.active_provider_id = "ibkr.observational"
        return adapter

    def attach_ibkr_query_service(
        self,
        provider: IbkrReadOnlyQueryProvider,
        *,
        lookup: Any | None = None,
    ) -> IbkrObservationalQueryService:
        """Wire read-only IBKR query service with injected outer provider."""
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=lookup,
            capability_registry=self.capability_registry,
        )
        self.ibkr_query_service = service
        if self.active_provider_id is None:
            self.active_provider_id = "ibkr.observational"
        self.sync_ibkr_runtime_state()
        return service

    def resolve_contract(
        self,
        instrument_id: str,
        *,
        contract_builder: Any | None = None,
        con_id: int | None = None,
    ) -> ContractResolutionResult:
        if self.ibkr_query_service is None:
            return ContractResolutionResult(
                accepted=False, reason="NO_QUERY_SERVICE"
            )
        return self.ibkr_query_service.resolve_contract(
            instrument_id,
            contract_builder=contract_builder,
            con_id=con_id,
        )

    def fetch_historical_bars(
        self,
        instrument_id: str,
        *,
        period: str = "1d",
        bar: str = "1h",
        con_id: int | None = None,
        received_time_ns: int | None = None,
        pit_cutoff_ns: int | None = None,
    ) -> HistoricalBarsResult:
        if self.ibkr_query_service is None:
            return HistoricalBarsResult(accepted=False, reason="NO_QUERY_SERVICE")
        return self.ibkr_query_service.fetch_historical_bars(
            instrument_id,
            period=period,
            bar=bar,
            con_id=con_id,
            received_time_ns=received_time_ns,
            pit_cutoff_ns=pit_cutoff_ns,
        )

    def fetch_account_observation(
        self,
        *,
        received_time_ns: int | None = None,
    ) -> AccountObservationResult:
        if self.ibkr_query_service is None:
            return AccountObservationResult(
                accepted=False, reason="NO_QUERY_SERVICE"
            )
        return self.ibkr_query_service.fetch_account_observation(
            received_time_ns=received_time_ns
        )

    def configure_replay_provider(
        self,
        provider_id: str = "replay.capture",
        *,
        timeliness: DataTimeliness = DataTimeliness.REAL_TIME,
    ) -> None:
        """Mark a replay/capture provider as runtime-ready for offline tests."""
        self.capability_registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=provider_id,
                health=ProviderHealth.HEALTHY,
                entitlement=EntitlementState.ENTITLED,
                timeliness=timeliness,
                live_verified=True,
                notes="REPLAY_PROVIDER",
            )
        )
        self.active_provider_id = provider_id

    def select_for_capability(
        self,
        capability_id: str,
        instrument_id: str,
        *,
        require_real_time: bool = False,
        instrument_kind: str | None = None,
    ) -> dict[str, Any]:
        result = self.selector.select(
            ObservationalSelectionRequest(
                capability_id=capability_id,
                instrument_id=instrument_id,
                require_real_time=require_real_time,
                instrument_kind=instrument_kind,
            )
        )
        return result.to_dict()

    def context_for(self, instrument_id: str) -> dict[str, Any]:
        """Screening/news context overlay (e.g. Finviz Elite). Not L1, not admission.

        Additive read: does not touch the canonical store, does not admit
        anything, and never replaces the L1 quote lane. Fail-closed to
        ``UNAVAILABLE`` when ``equity_context`` stays the unconfigured stub.
        """
        return self.lanes.build_context_payload(instrument_id, self.equity_context)

    def evidence_for(self, instrument_id: str) -> dict[str, Any]:
        bundle = self.lanes.build_evidence_bundle(instrument_id)
        bundle["context"] = self.context_for(instrument_id)
        return bundle

    def manifest(self) -> dict[str, Any]:
        return {
            "active_provider_id": self.active_provider_id,
            "capability_registry": self.capability_registry.manifest(),
            "context_provider_id": getattr(self.equity_context, "provider_id", ""),
            "has_ibkr_adapter": self.ibkr_adapter is not None,
            "has_ibkr_query_service": self.ibkr_query_service is not None,
            "logical_id": "market_data.runtime_composition",
            "store_metrics": self.store.metrics_report(),
        }

    def sync_ibkr_runtime_state(self) -> None:
        """Refresh G7 capability registry axes from adapter diagnostics."""
        adapter = self.ibkr_adapter
        if adapter is None:
            return
        diag = adapter.diagnostics()
        readiness = adapter.readiness()
        entitlement_raw = str(diag.get("entitlement_state") or diag.get("entitlement") or "UNKNOWN")
        try:
            entitlement = EntitlementState(entitlement_raw)
        except ValueError:
            entitlement = EntitlementState.UNKNOWN
        overall = str(readiness.get("overall") or "DEGRADED")
        health = ProviderHealth.HEALTHY
        if overall in {"UNAVAILABLE", "FAILED"}:
            health = ProviderHealth.DOWN
        elif overall != "READY":
            health = ProviderHealth.DEGRADED
        timeliness = (
            DataTimeliness.DELAYED
            if entitlement is EntitlementState.DELAYED
            else DataTimeliness.UNKNOWN
        )
        self.capability_registry.set_runtime_state(
            ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=health,
                entitlement=entitlement,
                timeliness=timeliness,
                live_verified=False,
                notes="LIVE_PROVIDER_UNVERIFIED",
            )
        )

    def subscribe_observational(
        self,
        instrument_id: str,
        *,
        l1: bool = True,
        l2: bool = False,
        con_id: int | None = None,
    ) -> dict[str, Any]:
        """Subscribe through the active IBKR adapter after capability selection."""
        if self.ibkr_adapter is None:
            return {"accepted": False, "reason": "NO_IBKR_ADAPTER"}
        results: dict[str, Any] = {}
        if l1:
            selection = self.select_for_capability(CAP_L1, instrument_id)
            if selection.get("outcome") not in {"SELECTED", "REPLAY_ONLY"}:
                results["l1"] = {"accepted": False, "selection": selection}
            else:
                results["l1"] = self.ibkr_adapter.subscribe_l1(
                    instrument_id=instrument_id, con_id=con_id
                ).as_dict()
        if l2:
            selection = self.select_for_capability(CAP_L2, instrument_id)
            if selection.get("outcome") not in {"SELECTED", "REPLAY_ONLY"}:
                results["l2"] = {"accepted": False, "selection": selection}
            else:
                results["l2"] = self.ibkr_adapter.subscribe_l2(
                    instrument_id=instrument_id, con_id=con_id
                ).as_dict()
        self.sync_ibkr_runtime_state()
        return results

    def shutdown(self) -> None:
        """Cancel subscriptions and disconnect injected transport (idempotent)."""
        if self._shutdown_complete:
            return
        query_service = self.ibkr_query_service
        if query_service is not None:
            query_service.shutdown()
            self.ibkr_query_service = None
        adapter = self.ibkr_adapter
        if adapter is None:
            self._shutdown_complete = True
            return
        for row in adapter.subscription_status().values():
            instrument = str(row.get("instrument_id") or "")
            capability = str(row.get("capability") or "")
            if capability == "L1":
                adapter.cancel_l1(instrument)
            elif capability == "L2":
                adapter.cancel_l2(instrument)
            elif capability == "TRADES":
                adapter.cancel_trades(instrument)
        adapter.shutdown()
        self.ibkr_adapter = None
        self.active_provider_id = None
        self._shutdown_complete = True


def build_replay_composition(
    *,
    transport: ObservationalTransport | None = None,
    lookup: Any | None = None,
) -> ObservationalRuntimeComposition:
    """Replay-first composition for offline G7 tests."""
    composition = ObservationalRuntimeComposition()
    composition.configure_replay_provider()
    if transport is not None:
        composition.attach_ibkr_adapter(transport, lookup=lookup)
    return composition


__all__ = [
    "ObservationalRuntimeComposition",
    "ObservationalTransport",
    "build_replay_composition",
]
