from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.trades_quotes import normalize_trade_quote_record
from squeeze_core.contracts import ReplayMode
from squeeze_core.evidence import (
    PointInTimeEvidencePolicy,
    TradeQuoteSeriesPolicy,
    build_point_in_time_evidence,
    build_trade_quote_series,
)
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
PROVIDER_ROOT = FIXTURE_ROOT / "providers" / "trades_quotes"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"

TIMELINE = {
    "as_of": {
        "before_original_publication": "2026-01-31T14:30:00.150000Z",
        "after_publication_before_receipt": "2026-01-31T14:30:00.250000Z",
        "after_original_receipt": "2026-01-31T14:30:00.300000Z",
        "before_correction_receipt": "2026-01-31T14:31:00.500000Z",
        "after_correction_receipt": "2026-01-31T14:31:01Z",
        "before_cancellation_receipt": "2026-01-31T14:32:00.500000Z",
        "after_cancellation_receipt": "2026-01-31T14:32:01Z",
        "final": "2026-01-31T14:36:01Z"
    }
}


def _document(name: str) -> dict[str, Any]:
    return json.loads((PROVIDER_ROOT / name).read_text(encoding="utf-8"))


def _config() -> dict[str, Any]:
    values = json.loads((PROVIDER_ROOT / "context.json").read_text(encoding="utf-8"))
    values.pop("ingested_at", None)
    return values


def _context(ingested_at: str) -> AdapterContext:
    return AdapterContext(ingested_at=ingested_at, **_config())


def _trade_base() -> dict[str, Any]:
    return deepcopy(_document("trade_representative_cases.json")["cases"][0]["record"])


def _quote_base() -> dict[str, Any]:
    raw = _trade_base()
    raw.update(
        {
            "record_type": "QUOTE",
            "provider_record_id": "quote-base",
            "price": None,
            "size": None,
            "trade_conditions": [],
            "sale_condition": None,
            "bid_price": "10.24",
            "bid_size": 100,
            "ask_price": "10.26",
            "ask_size": 200,
            "bid_side_id": "bid-A",
            "ask_side_id": "ask-A",
            "quote_condition": "REGULAR",
            "quote_source": "VENUE_BOOK",
        }
    )
    return raw


def _normalize(raw: dict[str, Any], ingested_at: str):
    result = normalize_trade_quote_record(raw, _context(ingested_at))
    if not result.accepted or len(result.observations) != 1:
        raise RuntimeError(f"Phase 1I normalization drifted: {raw.get('provider_record_id')}")
    return result.observations[0]


def _lifecycle_observations() -> tuple:
    results = []
    for filename, base in (
        ("trade_lifecycle_cases.json", _trade_base()),
        ("quote_lifecycle_cases.json", _quote_base()),
    ):
        for case in _document(filename)["cases"]:
            raw = deepcopy(base)
            raw.update(case["updates"])
            results.append(_normalize(raw, case["ingested_at"]))
    return tuple(results)


def _representative_observations() -> tuple:
    results = []
    for case in _document("trade_representative_cases.json")["cases"]:
        results.append(_normalize(case["record"], case["ingested_at"]))
    quote_base = _quote_base()
    for index, case in enumerate(_document("quote_representative_cases.json")["cases"]):
        raw = deepcopy(quote_base)
        raw.update(
            {
                "provider_record_id": case["fixture_id"],
                "sequence_number": 400 + index,
                "market_scope": case["scope"],
                "bid_price": case["bid"],
                "bid_size": case["bid_size"],
                "ask_price": case["ask"],
                "ask_size": case["ask_size"],
            }
        )
        results.append(_normalize(raw, case["ingested_at"]))
    trade_unknown = _trade_base()
    trade_unknown.update(
        provider_record_id="mixed-trade-missing-sequence",
        fixture_origin="SYNTHETIC_EDGE_CASE",
        sequence_number=None,
        venue=None,
    )
    quote_unknown = _quote_base()
    quote_unknown.update(
        provider_record_id="mixed-quote-unknown-scope",
        fixture_origin="SYNTHETIC_EDGE_CASE",
        sequence_number=None,
        sequence_scope="UNKNOWN",
        market_scope="UNKNOWN",
        venue=None,
    )
    results.append(_normalize(trade_unknown, "2026-01-15T14:30:00.300000Z"))
    results.append(_normalize(quote_unknown, "2026-01-15T14:30:00.300000Z"))
    return tuple(results)


def _policy(raw_as_of: str) -> PointInTimeEvidencePolicy:
    return PointInTimeEvidencePolicy(
        as_of=datetime.fromisoformat(raw_as_of.replace("Z", "+00:00")),
        allow_stale=True,
        allow_delayed=True,
        allow_unknown_freshness=True,
        include_published_short_interest_domain=True,
        include_sec_filings_domain=True,
        include_trading_halts_domain=True,
        include_news_domain=True,
        include_market_bars_domain=True,
        include_trades_domain=True,
        include_quotes_domain=True,
    )


def build_phase_1i_artifacts() -> dict[str, Any]:
    phase_1h_observations = tuple(
        load_fixture(EVIDENCE_ROOT / "normalized_phase_1h_point_in_time.jsonl")
    )
    lifecycle = _lifecycle_observations()
    representative = _representative_observations()
    observations = tuple(
        sorted(phase_1h_observations + lifecycle + representative, key=observation_order_key)
    )
    jsonl_bytes = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    timeline_bundles = {
        label: build_point_in_time_evidence("TESTA", replay.observations, _policy(as_of))
        for label, as_of in TIMELINE["as_of"].items()
    }
    final_bundle = timeline_bundles["final"]
    series = build_trade_quote_series(
        replay.observations,
        TradeQuoteSeriesPolicy(
            symbol="TESTA",
            as_of=datetime.fromisoformat(TIMELINE["as_of"]["final"].replace("Z", "+00:00")),
        ),
    )
    phase_1h = json.loads(
        (EVIDENCE_ROOT / "expected_phase_1h_bundle_metadata.json").read_text(encoding="utf-8")
    )
    by_source = {item.source_record_id: item for item in lifecycle}
    provider_files = [
        "fixture_metadata.json", "context.json", "trade_representative_cases.json",
        "trade_edge_cases.json", "trade_lifecycle_cases.json", "quote_representative_cases.json",
        "quote_edge_cases.json", "quote_lifecycle_cases.json",
    ]
    metadata = {
        "schema_version": "1.0.0",
        **{
            f"provider_{name.removesuffix('.json')}_sha256": canonical_hash(_document(name))
            for name in provider_files if name != "context.json"
        },
        "provider_context_sha256": canonical_hash(_config()),
        "original_trade_observation_sha256": canonical_hash(by_source["phase1i-trade-original"]),
        "corrected_trade_observation_sha256": canonical_hash(by_source["phase1i-trade-corrected"]),
        "cancelled_trade_observation_sha256": canonical_hash(by_source["phase1i-trade-cancelled"]),
        "original_quote_observation_sha256": canonical_hash(by_source["phase1i-quote-original"]),
        "corrected_quote_observation_sha256": canonical_hash(by_source["phase1i-quote-corrected"]),
        "cancelled_quote_observation_sha256": canonical_hash(by_source["phase1i-quote-cancelled"]),
        "mixed_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
        **{f"{label}_bundle_sha256": bundle.bundle_hash for label, bundle in timeline_bundles.items()},
        "trade_quote_series_sha256": series.series_hash,
        "final_bundle_sha256": final_bundle.bundle_hash,
        "serialized_final_bundle_sha256": canonical_hash(final_bundle),
        "phase_1h_mixed_jsonl_sha256": phase_1h["mixed_jsonl_sha256"],
        "phase_1h_strict_replay_sha256": phase_1h["strict_replay_sha256"],
        "phase_1h_final_bundle_sha256": phase_1h["final_bundle_sha256"],
        "phase_1h_serialized_final_bundle_sha256": phase_1h["serialized_final_bundle_sha256"],
    }
    return {
        "jsonl_bytes": jsonl_bytes,
        "metadata": metadata,
        "observations": observations,
        "lifecycle_observations": lifecycle,
        "replay": replay,
        "timeline_bundles": timeline_bundles,
        "final_bundle": final_bundle,
        "series": series,
    }


def _mixed_cases() -> dict[str, Any]:
    names = [
        "missing-trades", "missing-quotes", "future-publication", "future-receipt",
        "correction-after-as-of", "cancellation-after-as-of", "locked-quote",
        "crossed-quote", "one-sided-quote", "missing-sequence", "out-of-order-sequence",
        "active-halt-interaction", "cross-provider-same-event", "conflicting-quote",
        "unknown-venue", "unknown-scope",
    ]
    return {
        "schema_version": "1.0.0",
        "contains_credentials": False,
        "contains_account_data": False,
        "contains_real_symbols": False,
        "contains_live_urls": False,
        "analytics": False,
        "strategy_interpretation": False,
        "cases": [{"case_id": name, "objective_only": True} for name in names],
    }


def write_artifacts() -> None:
    artifacts = build_phase_1i_artifacts()
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_ROOT / "trade_quote_availability_timeline.json").write_text(
        json.dumps(TIMELINE, indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE_ROOT / "mixed_phase_1i_cases.json").write_text(
        json.dumps(_mixed_cases(), indent=2) + "\n", encoding="utf-8"
    )
    (EVIDENCE_ROOT / "normalized_phase_1i_point_in_time.jsonl").write_bytes(
        artifacts["jsonl_bytes"]
    )
    (EVIDENCE_ROOT / "expected_phase_1i_bundle_metadata.json").write_bytes(
        canonical_json_bytes(artifacts["metadata"]) + b"\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1i_artifacts()["jsonl_bytes"].decode("utf-8"), end="")
