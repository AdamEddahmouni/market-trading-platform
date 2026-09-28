"""FINRA fixed-income capability: TRACE aggregates only, credential-gated.

Probed 2026-09-27 against the FINRA Query API:

- ``/metadata/group/fixedIncomeMarket/name/<dataset>`` is public; every
  ``/data/group/fixedIncomeMarket/...`` request returns 401 without the FINRA
  OAuth credential that IMP already manages (``FINRA_CLIENT_ID`` /
  ``FINRA_CLIENT_SECRET``, opt-in with ``IMP_FINRA_LIVE=1``).
- The public fixed-income datasets are *aggregate* statistics (Treasury daily
  aggregates, corporate/agency market breadth, sentiment, capped volume).
  None is a per-security trade tape.
- Per-security TRACE trade prints (corporate, agency, securitized) are
  licensed FINRA TRACE data products, not part of the Query API. IMP has no
  such licence, so security-level TRACE is ``FINRA_TERMS_REQUIRED`` and no
  corporate or agency bond rows exist.

The aggregate adapter normalizes the documented ``treasuryDailyAggregates``
fields (shape taken from FINRA's published metadata). An aggregate is market
activity context, never a quote, order book, or security price.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Callable, Mapping

from ..finra.client_config import load_finra_credentials

SOURCE_AGGREGATES = "FINRA_TRACE_AGGREGATES"
SOURCE_TRACE = "FINRA_TRACE"
DATASET_GROUP = "fixedIncomeMarket"
TREASURY_AGGREGATES = "treasuryDailyAggregates"
LOOKBACK_DAYS = 10
MAX_RECORDS = 500
_NUMBERS = ("atsInterdealerCount", "atsInterdealerVolume", "dealerCustomerCount", "dealerCustomerVolume",
            "volumeWeightedAveragePrice")


def trace_capability() -> dict[str, Any]:
    """Security-level TRACE prints: not available through a permitted programmatic path."""

    return {"source": SOURCE_TRACE, "state": "FINRA_TERMS_REQUIRED",
            "reason": "Per-security TRACE trade data is a licensed FINRA data product; the public Query API offers aggregates only.",
            "corporate_coverage": "CORPORATE_COVERAGE_UNAVAILABLE", "agency_coverage": "UNAVAILABLE"}


def configuration_state(env: Mapping[str, str] = os.environ) -> tuple[str, str | None]:
    if env.get("IMP_FINRA_LIVE") != "1":
        return "NOT_CONFIGURED", "IMP_FINRA_LIVE_NOT_SET"
    if not load_finra_credentials().present():
        return "NOT_CONFIGURED", "FINRA_CREDENTIALS_MISSING"
    return "CONFIGURED", None


def _number(raw: Any) -> float | None:
    try:
        return float(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        return None


def normalize_treasury_aggregates(records: list[dict[str, Any]]) -> dict[str, Any]:
    """The latest trade date's rows; malformed rows are dropped and counted."""

    rows, dropped = [], 0
    for record in records:
        trade_date = str(record.get("tradeDate") or "")[:10]
        try:
            date.fromisoformat(trade_date)
        except ValueError:
            dropped += 1
            continue
        rows.append({"trade_date": trade_date, "product": str(record.get("productCategory") or "") or None,
                     "years_to_maturity": str(record.get("yearsToMaturity") or "") or None,
                     "benchmark": str(record.get("benchmark") or "") or None,
                     **{key: _number(record.get(key)) for key in _NUMBERS}})
    if not rows:
        return {"state": "UNAVAILABLE", "reason": "NO_RECORDS", "trade_date": None, "rows": [], "dropped": dropped}
    latest = max(row["trade_date"] for row in rows)
    return {"state": "PUBLICATION_CURRENT", "reason": None, "trade_date": latest, "dropped": dropped,
            "rows": [row for row in rows if row["trade_date"] == latest],
            "semantics": "Aggregate TRACE Treasury activity (counts and dollar volume by bucket); not quotes or prices."}


def load_treasury_aggregates(*, today: date, env: Mapping[str, str] = os.environ,
                             transport_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    state, reason = configuration_state(env) if transport_factory is None else ("CONFIGURED", None)
    if state != "CONFIGURED":
        return {"source": SOURCE_AGGREGATES, "state": state, "reason": reason, "trade_date": None, "rows": []}
    if transport_factory is None:
        from ..finra.live import transport_from_env
        transport_factory = transport_from_env
    try:
        transport = transport_factory()
        response = transport.post(f"/data/group/{DATASET_GROUP}/name/{TREASURY_AGGREGATES}", {
            "limit": MAX_RECORDS,
            "dateRangeFilters": [{"fieldName": "tradeDate", "startDate": (today - timedelta(days=LOOKBACK_DAYS)).isoformat(),
                                  "endDate": today.isoformat()}],
        })
        records = response.records
    except Exception as exc:  # noqa: BLE001 — stable code only, never response text
        text = str(exc)
        code = next((item for item in ("FINRA_CREDENTIALS_MISSING", "AUTH_FAILED", "FINRA_HTTP_429")
                     if item in text), "FINRA_UNAVAILABLE")
        return {"source": SOURCE_AGGREGATES, "state": "UNAVAILABLE", "reason": code, "trade_date": None, "rows": []}
    if not isinstance(records, list):
        return {"source": SOURCE_AGGREGATES, "state": "UNAVAILABLE", "reason": "MALFORMED_RESPONSE", "trade_date": None, "rows": []}
    return {"source": SOURCE_AGGREGATES, **normalize_treasury_aggregates([item for item in records if isinstance(item, dict)])}
