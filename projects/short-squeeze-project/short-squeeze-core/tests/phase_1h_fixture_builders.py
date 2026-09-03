from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from phase_1g_fixture_builders import build_phase_1g_artifacts
from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.contracts import (
    EntitlementState,
    IngestionMethod,
    ReplayMode,
)
from squeeze_core.evidence import (
    BarSeriesPolicy,
    PointInTimeEvidencePolicy,
    build_bar_series,
    build_point_in_time_evidence,
)
from squeeze_core.replay import ReplayEngine
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
BAR_ROOT = FIXTURE_ROOT / "providers" / "market_bars"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"


def _base(**updates: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "source_record_id": "bar-base",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "provider": "SCHWAB_SHAPED",
        "provider_record_id": "bar-base",
        "symbol": "TESTA",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_MINUTE",
        "bar_start": "2026-01-15T09:30:00-05:00",
        "bar_end": "2026-01-15T09:31:00-05:00",
        "open": "10.10",
        "high": "10.30",
        "low": "10.00",
        "close": "10.25",
        "volume": "1000",
        "trade_count": "25",
        "vwap": "10.20",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": "2026-01-15",
        "timezone": "-05:00",
        "status": "COMPLETED",
        "publication_timestamp": "2026-01-15T09:31:01-05:00",
    }
    raw.update(updates)
    return raw


def _metadata(
    fixture_id: str,
    record: dict[str, Any],
    expected: str,
    *,
    origin: str | None = None,
    source_shape_basis: str = "DOCUMENTED_PROVIDER_SHAPE",
    interval_status: str = "EXPLICIT",
    session_status: str = "EXPLICIT",
    bar_boundary_status: str = "EXACT",
    publication_timestamp_status: str = "EXACT",
    capture_timestamp_status: str = "MISSING",
    revision_status: str = "NOT_APPLICABLE",
) -> dict[str, Any]:
    chosen_origin = origin or str(record["fixture_origin"])
    return {
        "fixture_id": fixture_id,
        "origin": chosen_origin,
        "sanitization_status": "SANITIZED",
        "source_shape_basis": source_shape_basis,
        "contains_credentials": False,
        "contains_account_data": False,
        "contains_real_symbols": False,
        "contains_live_urls": False,
        "provider": str(record.get("provider", "UNKNOWN")),
        "provider_record_type": str(record.get("record_type", "UNKNOWN")),
        "interval_status": interval_status,
        "session_status": session_status,
        "bar_boundary_status": bar_boundary_status,
        "publication_timestamp_status": publication_timestamp_status,
        "capture_timestamp_status": capture_timestamp_status,
        "received_timestamp_status": "CONTEXT_SUPPLIED",
        "completion_status": str(record.get("status", "UNKNOWN")),
        "revision_status": revision_status,
        "expected_normalization_result": expected,
    }


def _case(fixture_id: str, record: dict[str, Any], expected: str, **metadata: Any) -> dict[str, Any]:
    raw = deepcopy(record)
    raw["source_record_id"] = fixture_id
    if raw.get("provider_record_id") == "bar-base":
        raw["provider_record_id"] = fixture_id
    return {"metadata": _metadata(fixture_id, raw, expected, **metadata), "record": raw}


def _provider_documents() -> dict[str, dict[str, Any]]:
    representative = [
        _case("bar-complete-one-minute", _base(), "ACCEPT_COMPLETE"),
        _case("bar-complete-five-minute", _base(interval="5_MINUTES", bar_end="2026-01-15T09:35:00-05:00", publication_timestamp="2026-01-15T09:35:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-complete-fifteen-minute", _base(interval="15_MINUTES", bar_end="2026-01-15T09:45:00-05:00", publication_timestamp="2026-01-15T09:45:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-complete-one-hour", _base(interval="1_HOUR", bar_end="2026-01-15T10:30:00-05:00", publication_timestamp="2026-01-15T10:30:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-complete-daily", _base(interval="1_DAY", bar_start="2026-01-15T09:30:00-05:00", bar_end="2026-01-15T16:00:00-05:00", publication_timestamp="2026-01-15T16:00:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-missing-volume", _base(volume=None), "ACCEPT_PARTIAL"),
        _case("bar-zero-volume", _base(volume="0"), "ACCEPT_COMPLETE"),
        _case("bar-missing-trade-count", _base(trade_count=None), "ACCEPT_PARTIAL"),
        _case("bar-zero-trade-count", _base(trade_count="0"), "ACCEPT_COMPLETE"),
        _case("bar-missing-vwap", _base(vwap=None), "ACCEPT_PARTIAL"),
        _case("bar-time-only-intraday", _base(bar_start="09:30:00", bar_end="09:31:00"), "ACCEPT_COMPLETE", bar_boundary_status="TIME_ONLY_WITH_SESSION_DATE_AND_OFFSET"),
        _case("bar-regular-session", _base(), "ACCEPT_COMPLETE"),
        _case("bar-sanitized-provider-metadata", _base(provider_metadata={"feed": "representative", "entitlement": "not-applicable"}), "ACCEPT_COMPLETE"),
    ]
    edge = [
        _case("bar-negative-volume", _base(volume="-1", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-fractional-volume", _base(volume="1.5", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-invalid-ohlc", _base(high="9.99", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-missing-open", _base(open=None, fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-missing-high", _base(high=None, fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-missing-low", _base(low=None, fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-missing-close", _base(close=None, fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-date-only-daily", _base(interval="1_DAY", bar_start=None, bar_end=None, provider_timestamp="2026-01-15", timestamp_meaning="LABEL", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE", bar_boundary_status="DATE_ONLY_LABEL"),
        _case("bar-missing-timezone", _base(bar_start="2026-01-15T09:30:00", bar_end="2026-01-15T09:31:00", publication_timestamp="2026-01-15T09:31:01", timezone=None, fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE", bar_boundary_status="NAIVE_REJECTED"),
        _case("bar-unsupported-interval", _base(interval="2_HOURS", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE", interval_status="UNSUPPORTED"),
    ]
    lifecycle = [
        _case("bar-partial", _base(status="PARTIAL", provider_record_id="lifecycle-partial", publication_timestamp="2026-01-15T09:30:30-05:00", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_PARTIAL", origin="SYNTHETIC_EDGE_CASE", revision_status="PARTIAL"),
        _case("bar-partial-to-complete", _base(provider_record_id="lifecycle-complete", supersedes_provider_record_id="lifecycle-partial", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="SUPERSEDES_PARTIAL"),
        _case("bar-corrected-completed", _base(provider_record_id="lifecycle-corrected", status="CORRECTED", close="10.26", supersedes_provider_record_id="lifecycle-complete", revision_number=1, publication_timestamp="2026-01-15T09:35:00-05:00", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="CORRECTED"),
        _case("bar-cancelled", _base(status="CANCELLED", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="CANCELLED"),
        _case("bar-exact-duplicate", _base(fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="DUPLICATE_BATCH_CASE"),
        _case("bar-same-id-changed-content", _base(provider_record_id="shared-id", close="10.26", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="CONFLICT_BATCH_CASE"),
        _case("bar-same-boundary-provider-conflict", _base(provider="IBKR_SHAPED", close="10.26", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="CROSS_PROVIDER_CONFLICT"),
        _case("bar-publication-after-as-of", _base(publication_timestamp="2026-01-15T10:00:00-05:00", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", publication_timestamp_status="AFTER_TARGET_AS_OF"),
        _case("bar-receipt-after-as-of", _base(fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="RECEIPT_CONTEXT_AFTER_AS_OF"),
        _case("bar-correction-after-as-of", _base(status="CORRECTED", supersedes_provider_record_id="prior", publication_timestamp="2026-01-15T10:00:00-05:00", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", revision_status="AFTER_TARGET_AS_OF"),
    ]
    session = [
        _case("bar-unknown-session", _base(session="UNKNOWN", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_PARTIAL", origin="SYNTHETIC_EDGE_CASE", session_status="UNKNOWN"),
        _case("bar-premarket", _base(session="PREMARKET", bar_start="2026-01-15T08:00:00-05:00", bar_end="2026-01-15T08:01:00-05:00", publication_timestamp="2026-01-15T08:01:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-after-hours", _base(session="AFTER_HOURS", bar_start="2026-01-15T16:01:00-05:00", bar_end="2026-01-15T16:02:00-05:00", publication_timestamp="2026-01-15T16:02:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-overnight", _base(session="OVERNIGHT", bar_start="2026-01-15T03:00:00-05:00", bar_end="2026-01-15T03:01:00-05:00", publication_timestamp="2026-01-15T03:01:01-05:00"), "ACCEPT_COMPLETE"),
        _case("bar-different-boundaries", _base(bar_start="2026-01-15T09:31:00-05:00", bar_end="2026-01-15T09:32:00-05:00", publication_timestamp="2026-01-15T09:32:01-05:00", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-out-of-order", _base(bar_start="2026-01-15T09:29:00-05:00", bar_end="2026-01-15T09:30:00-05:00", publication_timestamp="2026-01-15T09:30:01-05:00", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", bar_boundary_status="OUT_OF_ORDER_BATCH_CASE"),
        _case("bar-multiple-symbols", _base(symbol="TESTB", fixture_origin="SYNTHETIC_EDGE_CASE"), "ACCEPT_COMPLETE", origin="SYNTHETIC_EDGE_CASE", source_shape_basis="MULTI_SYMBOL_BATCH_CASE"),
        _case("bar-unsupported-asset-class", _base(asset_class="ETF", volume_unit="SHARES", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE"),
        _case("bar-session-date-mismatch", _base(session_date="2026-01-16", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE", session_status="MISMATCH"),
        _case("bar-dst-ambiguity", _base(bar_start="2026-11-01T01:30:00", bar_end="2026-11-01T01:31:00", publication_timestamp="2026-11-01T01:31:01", session_date="2026-11-01", timezone="America/New_York", fixture_origin="SYNTHETIC_EDGE_CASE"), "REJECT", origin="SYNTHETIC_EDGE_CASE", bar_boundary_status="DST_AMBIGUOUS_OR_TZDATA_UNAVAILABLE"),
    ]
    documents = {
        "representative_cases.json": {"schema_version": "1.0.0", "cases": representative},
        "edge_cases.json": {"schema_version": "1.0.0", "cases": edge},
        "lifecycle_cases.json": {"schema_version": "1.0.0", "cases": lifecycle},
        "session_cases.json": {"schema_version": "1.0.0", "cases": session},
    }
    assert sum(len(document["cases"]) for document in documents.values()) == 43
    return documents


def _context(ingested_at: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(ingested_at.replace("Z", "+00:00")),
        source_timezone=None,
        provider="market-bars-offline",
        adapter_version="1.0.0",
        normalization_version="market-bars-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="sanitized-market-bar-fixture",
    )


def _normalize(raw: dict[str, Any], received: str):
    result = normalize_market_bar_record(raw, _context(received))
    if not result.accepted or len(result.observations) != 1:
        raise RuntimeError(f"Phase 1H fixture normalization drifted: {raw['source_record_id']}")
    return result.observations[0]


TIMELINE = {
    "partial_published": "2026-01-31T09:30:30-05:00",
    "partial_received": "2026-01-31T14:30:31Z",
    "completed_published": "2026-01-31T09:31:01-05:00",
    "completed_received": "2026-01-31T14:31:02Z",
    "correction_published": "2026-01-31T09:35:00-05:00",
    "correction_received": "2026-01-31T14:35:01Z",
    "as_of": {
        "before_partial_publication": "2026-01-31T14:30:29Z",
        "after_partial_receipt": "2026-01-31T14:30:31Z",
        "before_completed_receipt": "2026-01-31T14:31:01.500000Z",
        "after_completed_receipt": "2026-01-31T14:31:02Z",
        "before_correction_receipt": "2026-01-31T14:35:00.500000Z",
        "after_correction_receipt": "2026-01-31T14:35:01Z",
    },
}


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
    )


def build_phase_1h_artifacts() -> dict[str, Any]:
    partial_raw = _base(
        source_record_id="phase1h-partial",
        provider_record_id="phase1h-partial",
        status="PARTIAL",
        session_date="2026-01-31",
        bar_start="2026-01-31T09:30:00-05:00",
        bar_end="2026-01-31T09:31:00-05:00",
        close="10.15",
        volume="400",
        publication_timestamp=TIMELINE["partial_published"],
        fixture_origin="SYNTHETIC_EDGE_CASE",
    )
    complete_raw = _base(
        source_record_id="phase1h-complete",
        provider_record_id="phase1h-complete",
        session_date="2026-01-31",
        bar_start="2026-01-31T09:30:00-05:00",
        bar_end="2026-01-31T09:31:00-05:00",
        publication_timestamp=TIMELINE["completed_published"],
        supersedes_provider_record_id="phase1h-partial",
        fixture_origin="SYNTHETIC_EDGE_CASE",
    )
    corrected_raw = _base(
        source_record_id="phase1h-corrected",
        provider_record_id="phase1h-corrected",
        status="CORRECTED",
        revision_number=1,
        session_date="2026-01-31",
        bar_start="2026-01-31T09:30:00-05:00",
        bar_end="2026-01-31T09:31:00-05:00",
        close="10.26",
        publication_timestamp=TIMELINE["correction_published"],
        supersedes_provider_record_id="phase1h-complete",
        fixture_origin="SYNTHETIC_EDGE_CASE",
    )
    cancelled_raw = _base(
        source_record_id="phase1h-cancelled",
        provider_record_id="phase1h-cancelled",
        status="CANCELLED",
        session_date="2026-01-31",
        bar_start="2026-01-31T09:30:00-05:00",
        bar_end="2026-01-31T09:31:00-05:00",
        publication_timestamp="2026-01-31T09:36:00-05:00",
        supersedes_provider_record_id="phase1h-corrected",
        fixture_origin="SYNTHETIC_EDGE_CASE",
    )
    bar_observations = (
        _normalize(partial_raw, TIMELINE["partial_received"]),
        _normalize(complete_raw, TIMELINE["completed_received"]),
        _normalize(corrected_raw, TIMELINE["correction_received"]),
    )
    cancelled_observation = _normalize(cancelled_raw, "2026-01-31T14:36:01Z")
    phase_1g = build_phase_1g_artifacts()
    observations = tuple(sorted(phase_1g["observations"] + bar_observations, key=observation_order_key))
    jsonl_bytes = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    timeline_bundles = {
        label: build_point_in_time_evidence("TESTA", replay.observations, _policy(raw_as_of))
        for label, raw_as_of in TIMELINE["as_of"].items()
    }
    final_bundle = timeline_bundles["after_correction_receipt"]
    bar_series = build_bar_series(
        replay.observations,
        BarSeriesPolicy(
            symbol="TESTA",
            as_of=datetime.fromisoformat(TIMELINE["as_of"]["after_correction_receipt"].replace("Z", "+00:00")),
            interval="1_MINUTE",
        ),
    )
    phase_1g_metadata = phase_1g["metadata"]
    metadata = {
        "schema_version": "1.0.0",
        **{
            f"provider_{filename.removesuffix('.json')}_sha256": canonical_hash(document)
            for filename, document in sorted(_provider_documents().items())
        },
        "partial_bar_raw_record_sha256": canonical_hash(partial_raw),
        "completed_bar_raw_record_sha256": canonical_hash(complete_raw),
        "corrected_bar_raw_record_sha256": canonical_hash(corrected_raw),
        "cancelled_bar_raw_record_sha256": canonical_hash(cancelled_raw),
        "partial_bar_observation_sha256": canonical_hash(bar_observations[0]),
        "completed_bar_observation_sha256": canonical_hash(bar_observations[1]),
        "corrected_bar_observation_sha256": canonical_hash(bar_observations[2]),
        "cancelled_bar_observation_sha256": canonical_hash(cancelled_observation),
        "mixed_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
        **{f"{label}_bundle_sha256": bundle.bundle_hash for label, bundle in timeline_bundles.items()},
        "final_bar_series_sha256": bar_series.series_hash,
        "serialized_final_bundle_sha256": canonical_hash(final_bundle),
        "final_bundle_sha256": final_bundle.bundle_hash,
        "phase_1g_mixed_jsonl_sha256": phase_1g_metadata["mixed_jsonl_sha256"],
        "phase_1g_strict_replay_sha256": phase_1g_metadata["strict_replay_sha256"],
        "phase_1g_final_bundle_sha256": phase_1g_metadata["final_bundle_sha256"],
        "phase_1g_serialized_final_bundle_sha256": phase_1g_metadata["serialized_final_bundle_sha256"],
    }
    return {
        "jsonl_bytes": jsonl_bytes,
        "metadata": metadata,
        "observations": observations,
        "bar_observations": bar_observations,
        "replay": replay,
        "timeline_bundles": timeline_bundles,
        "final_bundle": final_bundle,
        "bar_series": bar_series,
    }


def _mixed_cases() -> dict[str, Any]:
    names = [
        "bars-present-snapshot-missing",
        "snapshot-present-bars-missing",
        "partial-bar-only",
        "completed-after-as-of",
        "correction-after-as-of",
        "news-and-bars-uninterpreted",
        "active-halt-with-pre-halt-bars",
        "quote-resumption-no-post-bar",
        "trading-resumed-later-bar",
        "stale-short-interest-recent-bars",
        "sec-filing-and-bars",
        "zero-volume-bar",
        "conflicting-provider-bars",
        "different-intervals-same-symbol",
        "no-market-bar-domain",
    ]
    return {
        "schema_version": "1.0.0",
        "contains_credentials": False,
        "contains_account_data": False,
        "contains_real_symbols": False,
        "calculates_indicators": False,
        "calculates_relative_volume": False,
        "strategy_interpretation": False,
        "cases": [{"case_id": name, "objective_only": True} for name in names],
    }


def write_artifacts() -> None:
    BAR_ROOT.mkdir(parents=True, exist_ok=True)
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    documents = _provider_documents()
    for filename, document in documents.items():
        (BAR_ROOT / filename).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    fixture_metadata = {
        "schema_version": "1.0.0",
        "recorded_sample_found": False,
        "archive_findings": "Only provider-shape code and mocks were found; no bar row has defensible publication, capture, and receipt provenance.",
        "allowed_origins": ["SANITIZED_REPRESENTATIVE_SAMPLE", "SYNTHETIC_EDGE_CASE"],
        "case_count": 43,
    }
    (BAR_ROOT / "fixture_metadata.json").write_text(json.dumps(fixture_metadata, indent=2) + "\n", encoding="utf-8")
    (BAR_ROOT / "context.json").write_bytes(canonical_json_bytes(_context("2026-01-15T14:40:00Z")) + b"\n")
    (EVIDENCE_ROOT / "market_bar_availability_timeline.json").write_text(json.dumps(TIMELINE, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE_ROOT / "mixed_phase_1h_cases.json").write_text(json.dumps(_mixed_cases(), indent=2) + "\n", encoding="utf-8")
    artifacts = build_phase_1h_artifacts()
    (EVIDENCE_ROOT / "normalized_phase_1h_point_in_time.jsonl").write_bytes(artifacts["jsonl_bytes"])
    (EVIDENCE_ROOT / "expected_phase_1h_bundle_metadata.json").write_bytes(canonical_json_bytes(artifacts["metadata"]) + b"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1h_artifacts()["jsonl_bytes"].decode("utf-8"), end="")
