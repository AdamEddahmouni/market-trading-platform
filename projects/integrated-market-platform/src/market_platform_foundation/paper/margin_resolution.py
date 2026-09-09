"""Futures margin fact resolution for Paper preview/submit (G13).

Resolves explicit client-supplied margin facts or admitted fixture rows.
Never invents brokerage formulas — returns ``None`` when no authoritative
row exists so pre-trade fails closed at the execution boundary.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..risk.margin_facts import MarginRequirementFacts, margin_facts_from_fixture_row


def _family_symbol(instrument: Mapping[str, Any], instrument_id: str) -> str:
    family = str(instrument.get("family_root") or "").strip().upper()
    if family:
        return family
    symbol = str(instrument.get("symbol") or instrument_id).upper()
    match = re.match(r"^([A-Z]+)", symbol)
    return match.group(1) if match else symbol


def resolve_futures_margin_facts(
    instrument: Mapping[str, Any],
    *,
    instrument_id: str,
    observation_time_ns: int,
    explicit: Any = None,
) -> MarginRequirementFacts | None:
    """Return admitted margin facts for a futures contract, or ``None``."""
    if str(instrument.get("instrument_kind", "")).upper() != "FUTURE_CONTRACT":
        return None
    if explicit is not None:
        if isinstance(explicit, MarginRequirementFacts):
            return explicit
        return MarginRequirementFacts.from_dict(explicit)

    from ..providers.adapters.fixture_futures_margin import FixtureFuturesMarginProvider

    provider = FixtureFuturesMarginProvider()
    family = _family_symbol(instrument, instrument_id)
    result = provider.fetch_margin(family, as_of_time_ns=observation_time_ns)
    if result.status != "available" or not result.events:
        return None

    rows = [row for row in result.events if isinstance(row, dict)]
    if not rows:
        return None
    contract_rows = [
        row
        for row in rows
        if str(row.get("contract_id", "")).upper() == str(instrument_id).upper()
    ]
    row = contract_rows[-1] if contract_rows else rows[-1]
    return margin_facts_from_fixture_row(
        instrument_id=instrument_id,
        row=row,
        observation_time_ns=observation_time_ns,
        currency=str(instrument.get("currency", "USD")),
    )


__all__ = ["resolve_futures_margin_facts"]
