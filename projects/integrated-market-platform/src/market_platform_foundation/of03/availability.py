"""Runtime availability. Does not mutate definition hashes."""

from __future__ import annotations

import os

from .contracts import CapabilityDefinition
from .enums import AvailabilityState, BindingKind, FeatureGateKind, RegistrationState


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def availability_for(capability: CapabilityDefinition, *, binding_ok: bool) -> AvailabilityState:
    if capability.deprecation.deprecated or capability.registration_state is RegistrationState.DEPRECATED:
        return AvailabilityState.DEPRECATED
    if capability.binding.binding_kind is BindingKind.UNBOUND or not binding_ok:
        return AvailabilityState.UNBOUND
    for gate in capability.feature_gates:
        if gate.kind is FeatureGateKind.ENV_TRUTHY and not _env_truthy(gate.name):
            return AvailabilityState.DISABLED
    extras = capability.raw.get("availability_probe")
    if extras == "LIVE_PROVIDER":
        if not _env_truthy("IMP_LIVE_PROVIDER_AVAILABLE"):
            return AvailabilityState.UNAVAILABLE
    return AvailabilityState.AVAILABLE
