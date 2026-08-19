"""Family model registry — resolve plugin by FuturesFamily enum (F6)."""

from __future__ import annotations

from typing import Any

from ...contracts.futures import FuturesFamily
from .base import FAMILY_MODEL_VERSION, family_context_to_dict
from .equity_index import EquityIndexFamilyModel

_IMPLEMENTATIONS: dict[FuturesFamily, EquityIndexFamilyModel] = {
    FuturesFamily.EQUITY_INDEX: EquityIndexFamilyModel(),
}


def resolve_family_model(family: FuturesFamily) -> EquityIndexFamilyModel | None:
    """Return family plugin or None when unimplemented — fail-closed."""
    return _IMPLEMENTATIONS.get(family)


def resolve_family_for_symbol(instrument_family: str) -> FuturesFamily:
    """Map instrument family symbol to FuturesFamily taxonomy."""
    symbol = instrument_family.strip().upper()
    if symbol in {"ES", "NQ", "RTY", "YM"}:
        return FuturesFamily.EQUITY_INDEX
    if symbol in {"ZN", "ZB", "ZF", "ZT"}:
        return FuturesFamily.TREASURY
    if symbol in {"CL", "NG", "RB", "HO"}:
        return FuturesFamily.ENERGY
    if symbol in {"GC", "SI", "HG"}:
        return FuturesFamily.METALS
    return FuturesFamily.OTHER


def family_context_payload(
    instrument_family: str,
    workspace_context: dict[str, Any],
    *,
    macro_snapshot: dict[str, Any] | None = None,
    leverage_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build workspace family context payload with fail-closed semantics."""
    family = resolve_family_for_symbol(instrument_family)
    model = resolve_family_model(family)
    if model is None:
        return {
            "available": False,
            "reason": "FAMILY_MODEL_UNIMPLEMENTED",
            "futures_family_available": False,
            "family": family.value,
            "model_version": FAMILY_MODEL_VERSION,
        }

    missing = [
        cap
        for cap in model.required_capabilities()
        if not _capability_available(cap, workspace_context)
    ]
    if missing:
        snapshot = model.build_context_snapshot(
            workspace_context,
            macro_snapshot=macro_snapshot,
            leverage_snapshot=leverage_snapshot,
        )
        payload = family_context_to_dict(snapshot)
        payload["available"] = False
        payload["reason"] = "FAMILY_CAPABILITIES_MISSING"
        payload["missing_capabilities"] = missing
        return {
            "available": False,
            "reason": "FAMILY_CAPABILITIES_MISSING",
            "futures_family_available": False,
            "family_context_snapshot": payload,
            "missing_capabilities": missing,
            "model_version": FAMILY_MODEL_VERSION,
        }

    snapshot = model.build_context_snapshot(
        workspace_context,
        macro_snapshot=macro_snapshot,
        leverage_snapshot=leverage_snapshot,
    )
    payload = family_context_to_dict(snapshot)
    payload["available"] = True
    return {
        "available": True,
        "futures_family_available": True,
        "family_context_snapshot": payload,
        "model_version": FAMILY_MODEL_VERSION,
    }


def _capability_available(capability: str, workspace_context: dict[str, Any]) -> bool:
    mapping = {
        "futures_curve": workspace_context.get("futures_curve_available"),
        "futures_positioning": workspace_context.get("futures_positioning_available"),
        "futures_baselines": workspace_context.get("futures_baselines_available"),
    }
    return bool(mapping.get(capability, False))


__all__ = [
    "family_context_payload",
    "resolve_family_for_symbol",
    "resolve_family_model",
]
