"""G7 — unified runtime provider capability truth.

Converges ``providers.registry.ProviderRegistry`` (implemented capability
metadata) with per-provider runtime state axes. Never collapses:

- IMPLEMENTED_CAPABILITY (descriptor exists)
- CURRENT_RUNTIME_STATE (READY / DEGRADED / UNAVAILABLE / …)
- ENTITLEMENT_STATE (UNKNOWN / ENTITLED / NOT_ENTITLED / DELAYED)
- DATA_TIMELINESS (REAL_TIME / DELAYED / STALE / UNKNOWN)
- INSTRUMENT_SUPPORT
- PROVIDER_HEALTH
- OBSERVATIONAL authority (execution is never inferred from market data)

This module is the single runtime-capability facade; it does not replace
``ProviderRegistry`` — it reads from it and layers runtime dimensions.

Capability axes never collapse:

- supported (implemented descriptor)
- configured (credentials/session present)
- entitled (market-data entitlement)
- fresh (timeliness is REAL_TIME)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from .registry import CapabilityDescriptor, ProviderDescriptor, ProviderRegistry
from .ibkr_observational.capability import (
    IBKR_CAPABILITY_ACCOUNT_READ,
    IBKR_CAPABILITY_CONTRACT_RESOLUTION,
    IBKR_CAPABILITY_HISTORICAL_BARS,
    IBKR_CAPABILITY_L1,
    IBKR_CAPABILITY_L2,
    IBKR_CAPABILITY_TRADES,
    IBKR_FORBIDDEN_CAPABILITIES,
    IBKR_PROVIDER_ID,
    register_ibkr_observational,
)
from .moomoo_opend_capability import (
    MOOMOO_OPEND_FORBIDDEN_CAPABILITIES,
    MOOMOO_OPEND_PROVIDER_ID,
    register_moomoo_opend_observational,
)
from .yahoo_delayed_capability import (
    YAHOO_CAPABILITY,
    YAHOO_FORBIDDEN_CAPABILITIES,
    YAHOO_PROVIDER_ID,
    register_yahoo_delayed_capability,
)


class RuntimeCapabilityState(StrEnum):
    """Current runtime readiness for a capability — distinct from implemented."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    NOT_ENTITLED = "NOT_ENTITLED"
    DELAYED = "DELAYED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    UNSUPPORTED_INSTRUMENT = "UNSUPPORTED_INSTRUMENT"
    LIVE_PROVIDER_UNVERIFIED = "LIVE_PROVIDER_UNVERIFIED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FRESHNESS_UNKNOWN = "FRESHNESS_UNKNOWN"


class EntitlementState(StrEnum):
    UNKNOWN = "UNKNOWN"
    ENTITLED = "ENTITLED"
    NOT_ENTITLED = "NOT_ENTITLED"
    DELAYED = "DELAYED"
    ERROR = "ERROR"


class DataTimeliness(StrEnum):
    REAL_TIME = "REAL_TIME"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ProviderHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class ConfiguredState(StrEnum):
    """Distinct from entitlement and implemented support."""

    UNKNOWN = "UNKNOWN"
    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class ObservationalAuthority(StrEnum):
    """Market-data observation only — execution is never registered here."""

    OBSERVATIONAL = "OBSERVATIONAL"
    EXECUTION_FORBIDDEN = "EXECUTION_FORBIDDEN"


# Lane-facing capability ids (observational).
CAP_L1 = "OBSERVATIONAL_L1"
CAP_L2 = "OBSERVATIONAL_L2"
CAP_TRADES = "OBSERVATIONAL_TRADES"
CAP_OPTION_CONTRACT = "OBSERVATIONAL_OPTION_CONTRACT"
CAP_OPTION_CHAIN = "OBSERVATIONAL_OPTION_CHAIN"
CAP_FUTURE_CONTRACT = "OBSERVATIONAL_FUTURE_CONTRACT"
CAP_HISTORICAL_BARS = "OBSERVATIONAL_HISTORICAL_BARS"
CAP_REPLAY = "OBSERVATIONAL_REPLAY"
CAP_CONTRACT_RESOLUTION = "OBSERVATIONAL_CONTRACT_RESOLUTION"
CAP_ACCOUNT_READ = "OBSERVATIONAL_ACCOUNT_READ"
CAP_DELAYED_OVERLAY = "OBSERVATIONAL_DELAYED_OVERLAY"

# Map registry capability ids to lane-facing ids.
_REGISTRY_CAPABILITY_ALIASES: dict[str, str] = {
    IBKR_CAPABILITY_L1: CAP_L1,
    IBKR_CAPABILITY_L2: CAP_L2,
    IBKR_CAPABILITY_TRADES: CAP_TRADES,
    IBKR_CAPABILITY_CONTRACT_RESOLUTION: CAP_CONTRACT_RESOLUTION,
    IBKR_CAPABILITY_HISTORICAL_BARS: CAP_HISTORICAL_BARS,
    IBKR_CAPABILITY_ACCOUNT_READ: CAP_ACCOUNT_READ,
    "US_EQUITY_L1": CAP_L1,
    "US_EQUITY_DEPTH": CAP_L2,
    "US_EQUITY_TICKS": CAP_TRADES,
    "US_OPTIONS_QUOTE": CAP_OPTION_CONTRACT,
    "US_FUTURES_QUOTE": CAP_FUTURE_CONTRACT,
    "options_activity": CAP_OPTION_CHAIN,
    "futures_depth": CAP_FUTURE_CONTRACT,
    YAHOO_CAPABILITY: CAP_DELAYED_OVERLAY,
}

_LANE_TO_REGISTRY_CAPABILITIES: dict[str, tuple[str, ...]] = {
    CAP_L1: (IBKR_CAPABILITY_L1, "US_EQUITY_L1"),
    CAP_L2: (IBKR_CAPABILITY_L2, "US_EQUITY_DEPTH"),
    CAP_TRADES: (IBKR_CAPABILITY_TRADES, "US_EQUITY_TICKS"),
    CAP_OPTION_CONTRACT: ("US_OPTIONS_QUOTE",),
    CAP_OPTION_CHAIN: ("options_activity",),
    CAP_FUTURE_CONTRACT: ("US_FUTURES_QUOTE", "futures_depth"),
    CAP_CONTRACT_RESOLUTION: (IBKR_CAPABILITY_CONTRACT_RESOLUTION,),
    CAP_REPLAY: (IBKR_CAPABILITY_L1, IBKR_CAPABILITY_L2),
    CAP_HISTORICAL_BARS: (IBKR_CAPABILITY_HISTORICAL_BARS, "US_EQUITY_BARS"),
    "OBSERVATIONAL_ACCOUNT_READ": (IBKR_CAPABILITY_ACCOUNT_READ,),
    CAP_DELAYED_OVERLAY: (YAHOO_CAPABILITY,),
}

#: Lane and registry ids that mean hop L1. Yahoo overlay is never these.
_HOP_L1_CAPABILITY_IDS = frozenset(
    {CAP_L1, IBKR_CAPABILITY_L1, "US_EQUITY_L1"}
)


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityView:
    """One capability at one provider with all axes explicit."""

    provider_id: str
    capability_id: str
    lane_capability_id: str
    implemented: bool
    runtime_state: RuntimeCapabilityState
    entitlement: EntitlementState
    timeliness: DataTimeliness
    provider_health: ProviderHealth
    observational_authority: ObservationalAuthority
    instrument_id: str | None = None
    reason_code: str | None = None
    configured: ConfiguredState = ConfiguredState.UNKNOWN
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "configured": self.configured.value,
            "entitlement": self.entitlement.value,
            "implemented": self.implemented,
            "instrument_id": self.instrument_id,
            "lane_capability_id": self.lane_capability_id,
            "observational_authority": self.observational_authority.value,
            "provider_health": self.provider_health.value,
            "provider_id": self.provider_id,
            "provenance": dict(self.provenance),
            "reason_code": self.reason_code,
            "runtime_state": self.runtime_state.value,
            "timeliness": self.timeliness.value,
        }


@dataclass
class ProviderRuntimeState:
    """Mutable per-provider runtime dimensions (entitlement, health, timeliness)."""

    provider_id: str
    health: ProviderHealth = ProviderHealth.UNKNOWN
    entitlement: EntitlementState = EntitlementState.UNKNOWN
    timeliness: DataTimeliness = DataTimeliness.UNKNOWN
    live_verified: bool = False
    configured: ConfiguredState = ConfiguredState.UNKNOWN
    notes: str = ""


class RuntimeCapabilityRegistry:
    """Facade: implemented capabilities from ProviderRegistry + runtime axes."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        *,
        runtime_states: dict[str, ProviderRuntimeState] | None = None,
        capability_overrides: dict[tuple[str, str], Any] | None = None,
    ) -> None:
        self._registry = registry or ProviderRegistry()
        self._runtime_states: dict[str, ProviderRuntimeState] = runtime_states or {}
        self._capability_overrides: dict[tuple[str, str], Any] = capability_overrides or {}
        self._register_default_providers()

    def _register_default_providers(self) -> None:
        known_ids = {
            row.get("provider_id")
            for row in self._registry.manifest().get("providers", [])
        }
        if IBKR_PROVIDER_ID not in known_ids:
            try:
                register_ibkr_observational(self._registry)
            except Exception:
                pass  # already registered
        if MOOMOO_OPEND_PROVIDER_ID not in known_ids:
            try:
                register_moomoo_opend_observational(self._registry)
            except Exception:
                pass  # already registered
        if IBKR_PROVIDER_ID not in self._runtime_states:
            self._runtime_states[IBKR_PROVIDER_ID] = ProviderRuntimeState(
                provider_id=IBKR_PROVIDER_ID,
                health=ProviderHealth.UNKNOWN,
                entitlement=EntitlementState.UNKNOWN,
                timeliness=DataTimeliness.UNKNOWN,
                live_verified=False,
                configured=ConfiguredState.UNKNOWN,
                notes="LIVE_PROVIDER_UNVERIFIED",
            )
        if MOOMOO_OPEND_PROVIDER_ID not in self._runtime_states:
            # Fail closed until a hop stamps HEALTHY after a real OpenD fetch.
            self._runtime_states[MOOMOO_OPEND_PROVIDER_ID] = ProviderRuntimeState(
                provider_id=MOOMOO_OPEND_PROVIDER_ID,
                health=ProviderHealth.DOWN,
                entitlement=EntitlementState.UNKNOWN,
                timeliness=DataTimeliness.UNKNOWN,
                live_verified=False,
                configured=ConfiguredState.NOT_CONFIGURED,
                notes="OPEND_UNVERIFIED_FAIL_CLOSED",
            )
        if YAHOO_PROVIDER_ID not in known_ids:
            try:
                register_yahoo_delayed_capability(self._registry)
            except Exception:
                pass  # already registered
        if YAHOO_PROVIDER_ID not in self._runtime_states:
            self._runtime_states[YAHOO_PROVIDER_ID] = ProviderRuntimeState(
                provider_id=YAHOO_PROVIDER_ID,
                health=ProviderHealth.UNKNOWN,
                entitlement=EntitlementState.DELAYED,
                timeliness=DataTimeliness.DELAYED,
                live_verified=False,
                configured=ConfiguredState.CONFIGURED,
                notes="DELAYED_OVERLAY_NOT_HOP_L1",
            )
        else:
            self._runtime_states[YAHOO_PROVIDER_ID] = _coerce_yahoo_runtime_state(
                self._runtime_states[YAHOO_PROVIDER_ID]
            )

    def set_runtime_state(self, state: ProviderRuntimeState) -> None:
        if state.provider_id == YAHOO_PROVIDER_ID:
            state = _coerce_yahoo_runtime_state(state)
        self._runtime_states[state.provider_id] = state

    def set_capability_override(
        self,
        provider_id: str,
        capability_id: str,
        override: Any,
    ) -> None:
        """Set measured per-capability runtime axes (G11.1 live evidence)."""
        self._capability_overrides[(provider_id, capability_id)] = override

    def capability_override_for(
        self,
        provider_id: str,
        capability_id: str,
    ) -> Any | None:
        return self._capability_overrides.get((provider_id, capability_id))

    def runtime_state_for(self, provider_id: str) -> ProviderRuntimeState:
        return self._runtime_states.get(
            provider_id,
            ProviderRuntimeState(provider_id=provider_id),
        )

    def resolve_registry_capability(self, provider_id: str, capability_id: str) -> str:
        """Map a lane-facing id to the registry capability this provider implements.

        ``OBSERVATIONAL_L1`` is IBKR_L1 on IBKR and ``US_EQUITY_L1`` on OpenD.
        Yahoo delayed overlay is not registered for hop L1.
        """
        registry_caps = _LANE_TO_REGISTRY_CAPABILITIES.get(capability_id)
        if not registry_caps:
            return capability_id
        implemented_ids = {
            item.capability_id for item in self.implemented_capabilities(provider_id)
        }
        for cap in registry_caps:
            if cap in implemented_ids:
                return cap
        return registry_caps[0]

    def implemented_capabilities(self, provider_id: str) -> tuple[CapabilityDescriptor, ...]:
        for cap_id in (
            IBKR_CAPABILITY_L1,
            IBKR_CAPABILITY_L2,
            IBKR_CAPABILITY_TRADES,
            IBKR_CAPABILITY_CONTRACT_RESOLUTION,
            IBKR_CAPABILITY_HISTORICAL_BARS,
            IBKR_CAPABILITY_ACCOUNT_READ,
            "US_EQUITY_L1",
            "US_EQUITY_DEPTH",
            "US_EQUITY_TICKS",
            "options_activity",
            "futures_depth",
            YAHOO_CAPABILITY,
        ):
            for desc in self._registry.providers_for(cap_id):
                if desc.provider_id == provider_id:
                    return desc.capabilities
        return ()

    def view_capability(
        self,
        provider_id: str,
        capability_id: str,
        *,
        instrument_id: str | None = None,
        require_real_time: bool = False,
    ) -> RuntimeCapabilityView:
        """Evaluate all axes for one provider+capability pair."""
        if provider_id == YAHOO_PROVIDER_ID and _is_hop_l1_capability(capability_id):
            view = _yahoo_not_hop_l1_view(instrument_id)
            view = _with_yahoo_overlay_invariants(
                view, require_real_time=require_real_time
            )
            return _with_capability_axis_honesty(
                view, configured=self.runtime_state_for(view.provider_id).configured
            )
        view = self._evaluate_capability(
            provider_id,
            capability_id,
            instrument_id=instrument_id,
            require_real_time=require_real_time,
        )
        view = _with_yahoo_overlay_invariants(view, require_real_time=require_real_time)
        return _with_capability_axis_honesty(
            view, configured=self.runtime_state_for(view.provider_id).configured
        )

    def _evaluate_capability(
        self,
        provider_id: str,
        capability_id: str,
        *,
        instrument_id: str | None = None,
        require_real_time: bool = False,
    ) -> RuntimeCapabilityView:
        if (
            capability_id in IBKR_FORBIDDEN_CAPABILITIES
            or capability_id in MOOMOO_OPEND_FORBIDDEN_CAPABILITIES
            or capability_id in YAHOO_FORBIDDEN_CAPABILITIES
            or capability_id.endswith("_EXECUTION")
        ):
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=capability_id,
                implemented=False,
                runtime_state=RuntimeCapabilityState.UNAVAILABLE,
                entitlement=EntitlementState.NOT_ENTITLED,
                timeliness=DataTimeliness.UNKNOWN,
                provider_health=ProviderHealth.DOWN,
                observational_authority=ObservationalAuthority.EXECUTION_FORBIDDEN,
                instrument_id=instrument_id,
                reason_code="EXECUTION_CAPABILITY_FORBIDDEN",
            )

        capability_id = self.resolve_registry_capability(provider_id, capability_id)
        runtime = self.runtime_state_for(provider_id)
        override = self.capability_override_for(provider_id, capability_id)
        descriptors = self.implemented_capabilities(provider_id)
        descriptor = next(
            (item for item in descriptors if item.capability_id == capability_id),
            None,
        )
        implemented = descriptor is not None
        lane_cap = _REGISTRY_CAPABILITY_ALIASES.get(capability_id, capability_id)

        if override is not None and getattr(override, "runtime_state", None) is not None:
            timeliness = getattr(override, "timeliness", runtime.timeliness)
            runtime_state = override.runtime_state
            if (
                require_real_time
                and timeliness is DataTimeliness.DELAYED
            ):
                runtime_state = RuntimeCapabilityState.DELAYED
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=implemented,
                runtime_state=runtime_state,
                entitlement=getattr(override, "entitlement", runtime.entitlement),
                timeliness=timeliness,
                provider_health=getattr(override, "health", runtime.health),
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code=getattr(override, "reason_code", None),
                provenance={"live_verified": bool(getattr(override, "live_verified", False))},
            )

        if not implemented:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=False,
                runtime_state=RuntimeCapabilityState.UNAVAILABLE,
                entitlement=runtime.entitlement,
                timeliness=runtime.timeliness,
                provider_health=runtime.health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="CAPABILITY_NOT_IMPLEMENTED",
            )

        health = runtime.health
        entitlement = runtime.entitlement
        timeliness = runtime.timeliness

        if health == ProviderHealth.DOWN:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.PROVIDER_UNAVAILABLE,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="PROVIDER_HEALTH_DOWN",
            )

        if runtime.configured is ConfiguredState.NOT_CONFIGURED:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.NOT_CONFIGURED,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="NOT_CONFIGURED",
            )

        if entitlement == EntitlementState.NOT_ENTITLED:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.NOT_ENTITLED,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="NOT_ENTITLED",
            )

        if timeliness == DataTimeliness.STALE:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.STALE,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="DATA_STALE",
            )

        if timeliness == DataTimeliness.DELAYED:
            runtime_state = (
                RuntimeCapabilityState.DELAYED
                if require_real_time
                else RuntimeCapabilityState.DEGRADED
            )
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=runtime_state,
                entitlement=EntitlementState.DELAYED,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="DELAYED_DATA" if require_real_time else None,
            )

        if not runtime.live_verified and provider_id == IBKR_PROVIDER_ID:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="LIVE_PROVIDER_UNVERIFIED",
                provenance={"replay_eligible": True},
            )

        if require_real_time and entitlement is EntitlementState.UNKNOWN:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.NOT_ENTITLED,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="ENTITLEMENT_UNKNOWN",
            )

        if require_real_time and timeliness is DataTimeliness.UNKNOWN:
            return RuntimeCapabilityView(
                provider_id=provider_id,
                capability_id=capability_id,
                lane_capability_id=lane_cap,
                implemented=True,
                runtime_state=RuntimeCapabilityState.FRESHNESS_UNKNOWN,
                entitlement=entitlement,
                timeliness=timeliness,
                provider_health=health,
                observational_authority=ObservationalAuthority.OBSERVATIONAL,
                instrument_id=instrument_id,
                reason_code="FRESHNESS_UNKNOWN",
            )

        runtime_state = (
            RuntimeCapabilityState.DEGRADED
            if health == ProviderHealth.DEGRADED
            else RuntimeCapabilityState.READY
        )
        return RuntimeCapabilityView(
            provider_id=provider_id,
            capability_id=capability_id,
            lane_capability_id=lane_cap,
            implemented=True,
            runtime_state=runtime_state,
            entitlement=entitlement,
            timeliness=timeliness,
            provider_health=health,
            observational_authority=ObservationalAuthority.OBSERVATIONAL,
            instrument_id=instrument_id,
        )

    def providers_for_lane_capability(self, lane_capability_id: str) -> list[str]:
        """Return provider ids that implement a lane-facing capability."""
        registry_caps = _LANE_TO_REGISTRY_CAPABILITIES.get(
            lane_capability_id, (lane_capability_id,)
        )
        seen: set[str] = set()
        result: list[str] = []
        for registry_cap in registry_caps:
            for item in self._registry.providers_for(registry_cap):
                if item.provider_id not in seen:
                    seen.add(item.provider_id)
                    result.append(item.provider_id)
        return sorted(result)

    def manifest(self) -> dict[str, Any]:
        base = self._registry.manifest()
        base["runtime_capability_schema"] = "g7/v1"
        base["runtime_states"] = {
            pid: {
                "configured": state.configured.value,
                "entitlement": state.entitlement.value,
                "health": state.health.value,
                "live_verified": state.live_verified,
                "timeliness": state.timeliness.value,
            }
            for pid, state in sorted(self._runtime_states.items())
        }
        return base


def _is_hop_l1_capability(capability_id: str) -> bool:
    """True for hop L1 lane/registry ids. Overlay snapshot is not hop L1."""
    if capability_id in _HOP_L1_CAPABILITY_IDS:
        return True
    mapped = _LANE_TO_REGISTRY_CAPABILITIES.get(capability_id)
    return mapped is not None and mapped == _LANE_TO_REGISTRY_CAPABILITIES[CAP_L1]


def _yahoo_not_hop_l1_view(instrument_id: str | None) -> RuntimeCapabilityView:
    """Yahoo delayed overlay must not masquerade as hop L1 (OpenD/IBKR)."""
    provenance: dict[str, Any] = {
        "hop_l1": False,
        "live_verified": False,
        "overlay_role": "DELAYED_EOD",
        "timeliness": DataTimeliness.DELAYED.value,
    }
    if instrument_id:
        provenance["instrument_id"] = instrument_id
    return RuntimeCapabilityView(
        provider_id=YAHOO_PROVIDER_ID,
        capability_id=YAHOO_CAPABILITY,
        lane_capability_id=CAP_L1,
        implemented=False,
        runtime_state=RuntimeCapabilityState.UNAVAILABLE,
        entitlement=EntitlementState.DELAYED,
        timeliness=DataTimeliness.DELAYED,
        provider_health=ProviderHealth.UNKNOWN,
        observational_authority=ObservationalAuthority.OBSERVATIONAL,
        instrument_id=instrument_id,
        reason_code="DELAYED_OVERLAY_NOT_HOP_L1",
        provenance=provenance,
    )


def _coerce_yahoo_runtime_state(state: ProviderRuntimeState) -> ProviderRuntimeState:
    """Yahoo overlay is never REAL_TIME, never hop-verified, never ENTITLED as live."""
    timeliness = state.timeliness
    notes = state.notes or "DELAYED_OVERLAY_NOT_HOP_L1"
    if timeliness is DataTimeliness.REAL_TIME:
        timeliness = DataTimeliness.DELAYED
        if "DELAYED_OVERLAY_NOT_REAL_TIME" not in notes:
            notes = f"{notes};DELAYED_OVERLAY_NOT_REAL_TIME"
    elif timeliness is DataTimeliness.UNKNOWN:
        timeliness = DataTimeliness.DELAYED
    entitlement = state.entitlement
    if entitlement in {EntitlementState.ENTITLED, EntitlementState.UNKNOWN}:
        entitlement = EntitlementState.DELAYED
    return ProviderRuntimeState(
        provider_id=YAHOO_PROVIDER_ID,
        health=state.health,
        entitlement=entitlement,
        timeliness=timeliness,
        live_verified=False,
        configured=(
            ConfiguredState.CONFIGURED
            if state.configured is ConfiguredState.UNKNOWN
            else state.configured
        ),
        notes=notes,
    )


def _with_yahoo_overlay_invariants(
    view: RuntimeCapabilityView,
    *,
    require_real_time: bool,
) -> RuntimeCapabilityView:
    """Delayed overlay never reports REAL_TIME or hop L1, even if stamped."""
    if view.provider_id != YAHOO_PROVIDER_ID:
        return view
    if view.observational_authority is ObservationalAuthority.EXECUTION_FORBIDDEN:
        return view

    timeliness = view.timeliness
    reason_code = view.reason_code
    if timeliness is DataTimeliness.REAL_TIME:
        timeliness = DataTimeliness.DELAYED
        reason_code = "DELAYED_OVERLAY_NOT_REAL_TIME"
    elif timeliness is DataTimeliness.UNKNOWN:
        timeliness = DataTimeliness.DELAYED

    entitlement = view.entitlement
    if entitlement in {EntitlementState.ENTITLED, EntitlementState.UNKNOWN}:
        entitlement = EntitlementState.DELAYED

    runtime_state = view.runtime_state
    blocked = {
        RuntimeCapabilityState.UNAVAILABLE,
        RuntimeCapabilityState.PROVIDER_UNAVAILABLE,
        RuntimeCapabilityState.NOT_ENTITLED,
        RuntimeCapabilityState.STALE,
        RuntimeCapabilityState.NOT_CONFIGURED,
        RuntimeCapabilityState.FRESHNESS_UNKNOWN,
    }
    if view.implemented and runtime_state not in blocked:
        if require_real_time and timeliness is DataTimeliness.DELAYED:
            runtime_state = RuntimeCapabilityState.DELAYED
            if reason_code is None:
                reason_code = "DELAYED_DATA"
        elif timeliness is DataTimeliness.DELAYED and runtime_state is RuntimeCapabilityState.READY:
            runtime_state = RuntimeCapabilityState.DEGRADED

    provenance = dict(view.provenance)
    provenance["overlay_role"] = "DELAYED_EOD"
    provenance["hop_l1"] = False
    provenance["timeliness"] = timeliness.value
    provenance["live_verified"] = False
    if view.instrument_id:
        provenance["instrument_id"] = view.instrument_id

    return replace(
        view,
        entitlement=entitlement,
        provenance=provenance,
        reason_code=reason_code,
        runtime_state=runtime_state,
        timeliness=timeliness,
    )


def _with_capability_axis_honesty(
    view: RuntimeCapabilityView,
    *,
    configured: ConfiguredState,
) -> RuntimeCapabilityView:
    """Stamp supported ≠ configured ≠ entitled ≠ fresh without collapsing axes."""
    if view.provider_id == YAHOO_PROVIDER_ID and configured is ConfiguredState.UNKNOWN:
        configured = ConfiguredState.CONFIGURED
    provenance = dict(view.provenance)
    provenance["axes"] = {
        "configured": configured.value,
        "entitled": view.entitlement.value,
        "fresh": view.timeliness is DataTimeliness.REAL_TIME,
        "supported": view.implemented,
    }
    return replace(view, configured=configured, provenance=provenance)


__all__ = [
    "CAP_CONTRACT_RESOLUTION",
    "CAP_DELAYED_OVERLAY",
    "CAP_FUTURE_CONTRACT",
    "CAP_HISTORICAL_BARS",
    "CAP_L1",
    "CAP_L2",
    "CAP_OPTION_CHAIN",
    "CAP_OPTION_CONTRACT",
    "CAP_REPLAY",
    "CAP_TRADES",
    "ConfiguredState",
    "DataTimeliness",
    "EntitlementState",
    "ObservationalAuthority",
    "ProviderHealth",
    "ProviderRuntimeState",
    "RuntimeCapabilityRegistry",
    "RuntimeCapabilityState",
    "RuntimeCapabilityView",
]
