"""Regenerates the Phase 2A CLI demonstration fixtures.

Not part of the runtime package; run manually with the project's .venv when the
fixture bars below change:

    .venv/Scripts/python.exe scripts/generate_phase_2a_cli_fixture.py

Deterministic: no wall clock, no randomness. Every bar below is a hand-specified
SYNTHETIC_EDGE_CASE record normalized through the same offline market-bar
normalizer Phase 1H uses, then serialized one canonical Observation per line.
"""

import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.replay import ReplayEngine
from squeeze_core.serialization.jsonl import serialize_jsonl
from squeeze_core.contracts import ReplayMode

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "fixtures" / "metrics"


def context(at: str, provider: str = "market-bars-offline") -> AdapterContext:
    from datetime import datetime

    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone=None,
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="metrics-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2a-synthetic-fixture",
    )


def bar_record(**overrides) -> dict:
    values = {
        "source_record_id": "bar-1",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": "ALPACA_SHAPED",
        "provider_record_id": None,
        "symbol": "TESTA",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": "2026-01-15T00:00:00-05:00",
        "bar_end": "2026-01-16T00:00:00-05:00",
        "open": "10.00",
        "high": "10.50",
        "low": "9.90",
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


def make_bar(*, ingested_at="2026-01-20T22:00:00Z", **overrides):
    result = normalize_market_bar_record(bar_record(**overrides), context(ingested_at))
    assert result.accepted, result.rejection
    return result.observations[0]


def main() -> None:
    bars = [
        make_bar(
            source_record_id=f"cli-bar-{day}",
            bar_start=f"2026-01-{day:02d}T00:00:00-05:00",
            bar_end=f"2026-01-{day + 1:02d}T00:00:00-05:00",
            session_date=f"2026-01-{day:02d}",
            publication_timestamp=f"2026-01-{day:02d}T16:01:00-05:00",
            ingested_at=f"2026-01-{day:02d}T21:02:00Z",
            close=close,
            open=open_,
            high=high,
            low=low,
            volume=volume,
        )
        for day, open_, high, low, close, volume in [
            (10, "9.50", "9.80", "9.40", "9.60", "80000"),
            (11, "9.60", "9.90", "9.50", "9.75", "85000"),
            (12, "9.75", "10.05", "9.65", "9.90", "90000"),
            (13, "9.90", "10.10", "9.80", "10.00", "95000"),
            (14, "10.00", "10.20", "9.95", "10.10", "100000"),
            (15, "10.10", "10.50", "9.90", "10.25", "120000"),
        ]
    ]

    ordered = ReplayEngine(mode=ReplayMode.NORMALIZED).replay(bars).observations
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cli_demo_bars.jsonl").write_bytes(serialize_jsonl(ordered))

    spec = {
        "schema_version": "1.0.0",
        "description": "Phase 2A CLI demonstration cases for tests/fixtures/metrics/cli_demo_bars.jsonl. Fixture provenance: SYNTHETIC_EDGE_CASE.",
        "cases": [
            {
                "metric_name": "ABSOLUTE_RETURN",
                "source_interval": "1_DAY",
                "start_bar_start": "2026-01-14T05:00:00Z",
                "start_bar_end": "2026-01-15T05:00:00Z",
                "end_bar_start": "2026-01-15T05:00:00Z",
                "end_bar_end": "2026-01-16T05:00:00Z",
                "price_field": "CLOSE",
            },
            {
                "metric_name": "PERCENTAGE_RETURN",
                "source_interval": "1_DAY",
                "start_bar_start": "2026-01-14T05:00:00Z",
                "start_bar_end": "2026-01-15T05:00:00Z",
                "end_bar_start": "2026-01-15T05:00:00Z",
                "end_bar_end": "2026-01-16T05:00:00Z",
                "price_field": "CLOSE",
            },
            {
                "metric_name": "ABSOLUTE_SESSION_GAP",
                "source_interval": "1_DAY",
                "prior_bar_start": "2026-01-14T05:00:00Z",
                "prior_bar_end": "2026-01-15T05:00:00Z",
                "current_bar_start": "2026-01-15T05:00:00Z",
                "current_bar_end": "2026-01-16T05:00:00Z",
            },
            {
                "metric_name": "ABSOLUTE_BAR_RANGE",
                "source_interval": "1_DAY",
                "target_bar_start": "2026-01-15T05:00:00Z",
                "target_bar_end": "2026-01-16T05:00:00Z",
            },
            {
                "metric_name": "PERCENTAGE_BAR_RANGE",
                "source_interval": "1_DAY",
                "target_bar_start": "2026-01-15T05:00:00Z",
                "target_bar_end": "2026-01-16T05:00:00Z",
            },
            {
                "metric_name": "MEAN_VOLUME_BASELINE",
                "source_interval": "1_DAY",
                "target_bar_start": "2026-01-15T05:00:00Z",
                "target_bar_end": "2026-01-16T05:00:00Z",
                "window": {"requested_count": 5, "exclude_current_bar": True, "minimum_samples": 3},
            },
        ],
    }
    (OUT_DIR / "phase_2a_metric_cases.json").write_text(
        json.dumps(spec, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
