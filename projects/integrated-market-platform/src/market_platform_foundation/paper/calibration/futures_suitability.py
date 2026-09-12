"""Advisory futures comparator suitability from Wave A audit artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

_DEFAULT_BROKER_AUDIT = (
    "artifacts/wave-a-findings/ibkr-tradier-alpaca-audit.json"
)
_DEFAULT_FUTURES_CONTEXT_AUDIT = (
    "artifacts/wave-a-findings/finviz-moomoo-audit.json"
)


class FuturesSuitabilityError(ValueError):
    """Wave A audit material unavailable or malformed."""


@dataclass(frozen=True, slots=True)
class FuturesComparatorSuitability:
    broker: str
    calibration_comparator_role: str
    calibration_comparator_note: str
    observational_es_support: str | None
    ftep_v1_001_readiness_today: str | None
    es_futures_quote_entitlement: str | None
    advisory_only: bool = True
    not_market_truth: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "calibration_comparator_role": self.calibration_comparator_role,
            "calibration_comparator_note": self.calibration_comparator_note,
            "observational_es_support": self.observational_es_support,
            "ftep_v1_001_readiness_today": self.ftep_v1_001_readiness_today,
            "es_futures_quote_entitlement": self.es_futures_quote_entitlement,
            "advisory_only": self.advisory_only,
            "not_market_truth": self.not_market_truth,
        }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FuturesSuitabilityError(f"FUTURES_SUITABILITY_AUDIT_MISSING:{path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise FuturesSuitabilityError(f"FUTURES_SUITABILITY_AUDIT_INVALID:{path}")
    return loaded


def _moomoo_es_entitlement(audit: Mapping[str, Any]) -> str | None:
    providers = audit.get("providers")
    if not isinstance(providers, dict):
        return None
    moomoo = providers.get("moomoo")
    if not isinstance(moomoo, dict):
        return None
    entitlements = moomoo.get("entitlements")
    if not isinstance(entitlements, dict):
        return None
    futures = entitlements.get("US_FUTURES_QUOTE")
    if isinstance(futures, dict):
        return str(futures.get("state") or futures.get("status") or "") or None
    return str(futures or "") or None


def assess_futures_comparator_suitability(
    *,
    broker: str,
    repository_root: Path,
    broker_audit_path: str | None = None,
    futures_context_audit_path: str | None = None,
) -> FuturesComparatorSuitability:
    broker_key = broker.strip().lower()
    broker_audit = _load_json(repository_root / (broker_audit_path or _DEFAULT_BROKER_AUDIT))
    futures_audit = _load_json(
        repository_root / (futures_context_audit_path or _DEFAULT_FUTURES_CONTEXT_AUDIT)
    )
    table = broker_audit.get("ftep_calibration_comparator_suitability", {}).get("table")
    if not isinstance(table, list):
        raise FuturesSuitabilityError("FUTURES_SUITABILITY_TABLE_MISSING")
    row = next(
        (
            item
            for item in table
            if isinstance(item, dict) and str(item.get("broker") or "").lower() == broker_key
        ),
        None,
    )
    if row is None:
        raise FuturesSuitabilityError(f"FUTURES_SUITABILITY_BROKER_UNKNOWN:{broker_key}")
    return FuturesComparatorSuitability(
        broker=broker_key,
        calibration_comparator_role=str(row.get("calibration_comparator_role") or ""),
        calibration_comparator_note=str(row.get("calibration_comparator_note") or ""),
        observational_es_support=str(row.get("observational_es_support") or "") or None,
        ftep_v1_001_readiness_today=str(row.get("ftep_v1_001_readiness_today") or "") or None,
        es_futures_quote_entitlement=_moomoo_es_entitlement(futures_audit),
    )


__all__ = [
    "FuturesComparatorSuitability",
    "FuturesSuitabilityError",
    "assess_futures_comparator_suitability",
]
