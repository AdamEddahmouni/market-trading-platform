"""FRED policy-rate, credit, and financial-conditions context for fixed income.

Reuses the existing FRED V1 client, Tier 1 registry, and V1 normalization, so
each value keeps its ALFRED knowledge interval (``realtime_start``) and
usage-rights label. These are broad market context series: a corporate
index spread is never assigned to an individual bond, and nothing here is a
security price.

Opt-in exactly like the rest of the FRED stack: ``IMP_FRED_LIVE=1`` and a
``FRED_API_KEY``. Without them the state is ``NOT_CONFIGURED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from ..fred.live import api_key_present, live_enabled, transport_from_env
from ..fred.normalize import normalize_v1_observation_row
from ..fred.redaction import sanitize_error
from ..fred.registry import MacroRegistryEntry, lookup_canonical

SOURCE = "FRED"
LOOKBACK_DAYS = 45
#: (group, canonical indicator). Only Tier 1 registry entries.
CONTEXT_SERIES: tuple[tuple[str, str], ...] = (
    ("POLICY", "US_POLICY_RATE_UPPER"),
    ("POLICY", "US_EFFECTIVE_FED_FUNDS_RATE"),
    ("POLICY", "US_SOFR"),
    ("INFLATION", "US_10Y_BREAKEVEN"),
    ("CREDIT", "US_IG_SPREAD"),
    ("CREDIT", "US_HY_SPREAD"),
    ("CONDITIONS", "US_NFCI"),
)


@dataclass(frozen=True, slots=True)
class ContextValue:
    group: str
    canonical_indicator_id: str
    series_id: str
    title: str
    value: float | None
    units: str
    observation_date: str | None
    knowledge_start_date: str | None
    frequency: str
    source_agency: str
    usage_rights: str
    quality_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"group": self.group, "id": self.canonical_indicator_id, "series_id": self.series_id,
                "title": self.title, "value": self.value, "units": self.units,
                "observation_date": self.observation_date, "knowledge_start_date": self.knowledge_start_date,
                "frequency": self.frequency, "source_agency": self.source_agency,
                "usage_rights": self.usage_rights, "quality_flags": list(self.quality_flags), "class": "OBSERVED"}


def configuration_state() -> tuple[str, str | None]:
    if not api_key_present():
        return "NOT_CONFIGURED", "FRED_API_KEY_MISSING"
    if not live_enabled():
        return "NOT_CONFIGURED", "IMP_FRED_LIVE_NOT_SET"
    return "CONFIGURED", None


def _latest(client: Any, entry: MacroRegistryEntry, *, today: date, retrieved: str) -> tuple[float | None, Any]:
    payload = client.series_observations(entry.fred_series_id,
                                         observation_start=(today - timedelta(days=LOOKBACK_DAYS)).isoformat(),
                                         sort_order="desc", limit=10)
    rows = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("MALFORMED_RESPONSE")
    for row in rows:
        observation = normalize_v1_observation_row(row, entry=entry, retrieved_time=retrieved, observed_time=retrieved)
        if observation.normalized_value is not None:
            return observation.normalized_value, observation
    return None, None


def load_fred_context(*, today: date, retrieved: str,
                      client_factory: Callable[[], Any] = lambda: transport_from_env()[0]) -> dict[str, Any]:
    """Latest non-missing value of each context series; one failing series never hides the rest."""

    state, reason = configuration_state()
    if state != "CONFIGURED":
        return {"state": state, "reason": reason, "items": []}
    try:
        client = client_factory()
    except Exception as exc:  # noqa: BLE001 — credentials never echoed
        return {"state": "UNAVAILABLE", "reason": sanitize_error(exc)[:80], "items": []}
    items, failures = [], 0
    for group, canonical in CONTEXT_SERIES:
        entry = lookup_canonical(canonical)
        if entry is None:
            continue
        try:
            value, observation = _latest(client, entry, today=today, retrieved=retrieved)
        except Exception:  # noqa: BLE001 — per-series failure
            failures += 1
            value, observation = None, None
        items.append(ContextValue(
            group=group, canonical_indicator_id=canonical, series_id=entry.fred_series_id, title=entry.title,
            value=value, units=entry.units, observation_date=observation.observation_date if observation else None,
            knowledge_start_date=(observation.knowledge_start_date or None) if observation else None,
            frequency=entry.frequency, source_agency=entry.original_source, usage_rights=entry.usage_rights,
            quality_flags=tuple(observation.quality_flags) if observation else ("UNAVAILABLE",)).to_dict())
    present = sum(1 for item in items if item["value"] is not None)
    state = "UNAVAILABLE" if not present else "PARTIAL" if present < len(items) or failures else "PUBLICATION_CURRENT"
    return {"state": state, "reason": None if present else "NO_OBSERVATIONS", "items": items}
