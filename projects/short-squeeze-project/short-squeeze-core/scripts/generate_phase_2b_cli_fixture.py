"""Regenerates the Phase 2B CLI demonstration fixtures.

Not part of the runtime package; run manually with the project's .venv when the
fixture bars below change:

    .venv/Scripts/python.exe scripts/generate_phase_2b_cli_fixture.py

Deterministic: no wall clock, no randomness. Every bar below is a hand-specified
SYNTHETIC_EDGE_CASE record normalized through the same offline market-bar
normalizer Phase 1H uses, then serialized one canonical Observation per line.
Mirrors scripts/generate_phase_2a_cli_fixture.py's structure and conventions.
"""

import json
from datetime import datetime
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.contracts import EntitlementState, IngestionMethod, ReplayMode
from squeeze_core.replay import ReplayEngine
from squeeze_core.serialization.jsonl import serialize_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "fixtures" / "metrics"


def context(at: str, provider: str = "market-bars-offline") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone=None,
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="metrics-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2b-synthetic-fixture",
    )


def bar_record(**overrides) -> dict:
    values = {
        "source_record_id": "bar-1",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": "ALPACA_SHAPED",
        "provider_record_id": None,
        "symbol": "TESTB",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": "2026-01-15T00:00:00-05:00",
        "bar_end": "2026-01-16T00:00:00-05:00",
        "open": "10.00",
        "high": "1000.00",
        "low": "0.01",
        "close": "10.25",
        "volume": "100000",
        "trade_count": "500",
        "vwap": "10.20",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": "2026-01-15",
        "timezone": "America/New_York",
        "status": "COMPLETED",
        "publication_timestamp": "2026-01-15T16:01:00-05:00",
    }
    values.update(overrides)
    return values


def make_bar(*, ingested_at="2026-02-01T22:00:00Z", **overrides):
    result = normalize_market_bar_record(bar_record(**overrides), context(ingested_at))
    assert result.accepted, result.rejection
    return result.observations[0]


# Ten trailing daily bars (day 10-19) plus one target bar (day 20). Closes/volumes chosen so
# every Phase 2B metric produces a KNOWN_VALUE result with a non-trivial (non-zero, non-integer)
# statistic -- exercising real Decimal division/sqrt, not a degenerate edge case.
BAR_SPECS = [
    (10, "9.50", "9.60", "80000"),
    (11, "9.60", "9.75", "85000"),
    (12, "9.75", "9.65", "78000"),
    (13, "9.65", "9.90", "91000"),
    (14, "9.90", "10.00", "95000"),
    (15, "10.00", "10.10", "97000"),
    (16, "10.10", "9.95", "88000"),
    (17, "9.95", "10.20", "102000"),
    (18, "10.20", "10.30", "105000"),
    (19, "10.30", "10.25", "99000"),
    (20, "10.25", "11.50", "150000"),
]


def main() -> None:
    bars = [
        make_bar(
            source_record_id=f"cli2b-bar-{day}",
            bar_start=f"2026-01-{day:02d}T00:00:00-05:00",
            bar_end=f"2026-01-{day + 1:02d}T00:00:00-05:00",
            session_date=f"2026-01-{day:02d}",
            publication_timestamp=f"2026-01-{day:02d}T16:01:00-05:00",
            ingested_at=f"2026-01-{day:02d}T21:02:00Z",
            open=open_,
            close=close,
            volume=volume,
        )
        for day, open_, close, volume in BAR_SPECS
    ]

    ordered = ReplayEngine(mode=ReplayMode.NORMALIZED).replay(bars).observations
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "phase_2b_cli_demo_bars.jsonl").write_bytes(serialize_jsonl(ordered))

    common = {"symbol": "TESTB", "source_interval": "1_DAY"}
    spec = {
        "schema_version": "1.0.0",
        "description": "Phase 2B CLI demonstration cases for tests/fixtures/metrics/phase_2b_cli_demo_bars.jsonl. Fixture provenance: SYNTHETIC_EDGE_CASE.",
        "cases": [
            {
                **common,
                "metric_name": "RELATIVE_VOLUME",
                "target_bar_start": "2026-01-20T05:00:00Z",
                "target_bar_end": "2026-01-21T05:00:00Z",
                "window": {"requested_count": 5, "exclude_current_bar": True, "minimum_samples": 3},
            },
            {
                **common,
                "metric_name": "VOLUME_PERCENT_DEVIATION",
                "target_bar_start": "2026-01-20T05:00:00Z",
                "target_bar_end": "2026-01-21T05:00:00Z",
                "window": {"requested_count": 5, "exclude_current_bar": True, "minimum_samples": 3},
            },
            {
                **common,
                "metric_name": "VOLUME_Z_SCORE",
                "target_bar_start": "2026-01-20T05:00:00Z",
                "target_bar_end": "2026-01-21T05:00:00Z",
                "window": {"requested_count": 8, "exclude_current_bar": True, "minimum_samples": 2},
            },
            {
                **common,
                "metric_name": "MEAN_PERCENTAGE_RETURN_BASELINE",
                "target_bar_start": "2026-01-19T05:00:00Z",
                "window": {"requested_count": 5, "exclude_current_bar": True, "minimum_samples": 2},
                "price_field": "CLOSE",
            },
            {
                **common,
                "metric_name": "PERCENTAGE_RETURN_STANDARD_DEVIATION_BASELINE",
                "target_bar_start": "2026-01-19T05:00:00Z",
                "window": {"requested_count": 5, "exclude_current_bar": True, "minimum_samples": 2},
                "price_field": "CLOSE",
            },
            {
                **common,
                "metric_name": "PERCENTAGE_RETURN_Z_SCORE",
                "target_start_bar_start": "2026-01-19T05:00:00Z",
                "target_start_bar_end": "2026-01-20T05:00:00Z",
                "target_end_bar_start": "2026-01-20T05:00:00Z",
                "target_end_bar_end": "2026-01-21T05:00:00Z",
                "window": {"requested_count": 5, "exclude_current_bar": True, "minimum_samples": 2},
                "price_field": "CLOSE",
            },
        ],
    }
    (OUT_DIR / "phase_2b_normalized_metric_cases.json").write_text(
        json.dumps(spec, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
