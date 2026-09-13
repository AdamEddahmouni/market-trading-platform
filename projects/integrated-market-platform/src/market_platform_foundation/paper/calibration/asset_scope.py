"""Equity Paper/sandbox does not validate ES futures fill realism."""

from __future__ import annotations

from typing import Any, Mapping

EQUITY_PAPER_DOES_NOT_VALIDATE_ES = (
    "US-equity Paper and sandbox fills (including Tradier sandbox) do not validate "
    "ES futures fill realism, Globex liquidity, ES tick economics, or ES queue/impact. "
    "Cross-asset reuse of a calibration pass is prohibited."
)

_EQUITY_COMPARATORS = frozenset({"tradier", "tradier.paper", "alpaca", "alpaca.paper"})
_FUTURES_ASSET_CLASSES = frozenset({"FUTURES", "ES", "CME_ES", "US_FUTURES"})
_ES_MARKERS = ("ES", "ESH", "ESM", "ESU", "ESZ", "/ES")


class CalibrationAssetScopeError(ValueError):
    """Calibration unit mixed equity comparator with ES/futures scope."""


def _looks_like_es(instrument_id: str) -> bool:
    token = instrument_id.strip().upper()
    if not token:
        return False
    if token in {"ES", "MES"}:
        return True
    return any(token.startswith(marker) for marker in _ES_MARKERS)


def assert_calibration_unit_asset_scope(
    *,
    asset_class: str,
    instrument_id: str,
    comparator_id: str,
) -> None:
    """Refuse an equity Paper comparator as ES futures fill calibration."""
    asset = str(asset_class or "").strip().upper()
    comparator = str(comparator_id or "").strip().lower()
    instrument = str(instrument_id or "").strip()
    futures_scope = asset in _FUTURES_ASSET_CLASSES or _looks_like_es(instrument)
    equity_comparator = comparator in _EQUITY_COMPARATORS
    if futures_scope and equity_comparator:
        raise CalibrationAssetScopeError("EQUITY_COMPARATOR_CANNOT_CALIBRATE_ES")


def equity_es_firewall_payload() -> dict[str, Any]:
    return {
        "equity_paper_does_not_validate_es": True,
        "statement": EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
    }


def annotate_limitations(limitations: Mapping[str, Any] | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(limitations, Mapping):
        existing = [str(item) for item in limitations.values()]
    else:
        existing = [str(item) for item in limitations]
    if EQUITY_PAPER_DOES_NOT_VALIDATE_ES not in existing:
        existing.append(EQUITY_PAPER_DOES_NOT_VALIDATE_ES)
    return tuple(existing)


__all__ = [
    "EQUITY_PAPER_DOES_NOT_VALIDATE_ES",
    "CalibrationAssetScopeError",
    "annotate_limitations",
    "assert_calibration_unit_asset_scope",
    "equity_es_firewall_payload",
]
