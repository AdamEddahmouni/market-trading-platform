"""Historical profile adapters for Research Export v1 (fixture-backed, no Live I/O)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..normalization.equity_bars import iso_to_epoch_ns
from .dataset_manifest import materialize_dataset_rows
from .targets import build_target_rows, verify_label_availability

REPO_ROOT = Path(__file__).resolve().parents[3]

PROFILE_MARKET_TECHNICAL = "MARKET_TECHNICAL"
PROFILE_EVENT_MACRO = "EVENT_MACRO"

NVDA_BARS_FIXTURE = REPO_ROOT / "tests/fixtures/providers/distribution/nvda_bars_slice.json"
ES_MACRO_FIXTURE = REPO_ROOT / "tests/fixtures/providers/futures/es_macro_events_slice.json"


def _fixture_source_sha256(path: Path) -> str:
    from ..canonical import sha256_bytes

    return sha256_bytes(path.read_bytes()).upper()


def _bars_to_events(bars: list[dict[str, Any]], *, instrument_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for bar in bars:
        observed_ns = iso_to_epoch_ns(str(bar["date"]))
        events.append(
            {
                "available_time": observed_ns,
                "bar_payload": {
                    "close": str(bar["close"]),
                    "high": str(bar.get("high", bar["close"])),
                    "low": str(bar.get("low", bar["close"])),
                    "open": str(bar.get("open", bar["close"])),
                    "volume": str(bar.get("volume", "0")),
                },
                "event_type": "BAR_OHLCV_1M",
                "instrument_id": instrument_id,
            }
        )
    return events


def build_market_technical_tables(
    *,
    fixture_path: Path | None = None,
    horizon_ns: int = 1_000_000_000,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Profile A: admitted NVDA distribution bars + technical features + forward outcomes."""
    path = fixture_path or NVDA_BARS_FIXTURE
    payload = json.loads(path.read_text(encoding="utf-8"))
    instrument_id = str(payload.get("symbol") or "NVDA")
    admission_id = str(payload.get("admission_id") or "ADMITTED-DISTRIBUTION-NVDA-001")
    bars = list(payload.get("bars") or [])
    if len(bars) < 2:
        raise ValueError("INSUFFICIENT_BAR_HISTORY")

    instruments = [
        {
            "instrument_id": instrument_id,
            "admission_id": admission_id,
            "effective_from_ns": iso_to_epoch_ns(str(bars[0]["date"])),
            "effective_to_ns": iso_to_epoch_ns(str(bars[-1]["date"])) + horizon_ns,
            "universe_version": admission_id,
        }
    ]

    market_observations: list[dict[str, Any]] = []
    feature_snapshots: list[dict[str, Any]] = []
    audit_exclusions: list[dict[str, Any]] = []

    for index, bar in enumerate(bars):
        source_ns = iso_to_epoch_ns(str(bar["date"]))
        market_observations.append(
            {
                "instrument_id": instrument_id,
                "source_time_ns": source_ns,
                "observed_at_ns": source_ns,
                "provider_id": "ADMITTED_FIXTURE",
                "observation_kind": "BAR_CLOSE",
                "value": str(bar["close"]),
            }
        )
        feature_snapshots.append(
            {
                "feature_snapshot_id": f"fs-{instrument_id}-{source_ns}",
                "instrument_id": instrument_id,
                "decision_at_ns": source_ns,
                "earliest_usable_at_ns": source_ns,
                "feature_version": "bar_close_v1",
                "feature_values": {"bar_close": str(bar["close"])},
            }
        )
        if index == len(bars) - 1:
            audit_exclusions.append(
                {
                    "reason_code": "TERMINAL_BAR_NO_OUTCOME",
                    "row_ref": f"bar:{source_ns}",
                    "audit_version": "research_export_v1",
                }
            )

    events = _bars_to_events(bars, instrument_id=instrument_id)
    materialized = materialize_dataset_rows(events)
    target_rows = build_target_rows(materialized, horizon_ns=horizon_ns)
    label_status, label_reasons = verify_label_availability(target_rows, horizon_ns=horizon_ns)
    if label_status != "PASS":
        raise ValueError(f"PIT_LABEL_AUDIT_FAILED:{label_reasons}")

    realized_outcomes: list[dict[str, Any]] = []
    for target in target_rows:
        decision_ns = int(target["prediction_cutoff"])
        realized_outcomes.append(
            {
                "decision_at_ns": decision_ns,
                "instrument_id": instrument_id,
                "label_available_time_ns": int(target["label_available_time"]),
                "target_version": "forward_return_v1",
                "forward_return": str(target["forward_return"]),
                "horizon_ns": int(target["horizon_ns"]),
            }
        )

    decision_start = iso_to_epoch_ns(str(bars[0]["date"]))
    decision_end = iso_to_epoch_ns(str(bars[-1]["date"])) + 1
    source_sha256 = _fixture_source_sha256(path)

    context = {
        "profile": PROFILE_MARKET_TECHNICAL,
        "source_fixture": str(path.relative_to(REPO_ROOT)),
        "source_sha256": source_sha256,
        "admission_id": admission_id,
        "decision_start_ns": decision_start,
        "decision_end_ns": decision_end,
        "decision_cutoff_ns": iso_to_epoch_ns(str(bars[-2]["date"])),
        "horizon_ns": horizon_ns,
        "experiment_binding": {
            "binding_kind": "RESEARCH_EXPORT_PROFILE",
            "profile": PROFILE_MARKET_TECHNICAL,
            "admission_id": admission_id,
        },
    }
    tables = {
        "instruments": instruments,
        "market_observations": market_observations,
        "feature_snapshots": feature_snapshots,
        "realized_outcomes": realized_outcomes,
        "audit_exclusions": audit_exclusions,
        "information_events": [],
    }
    return context, tables, [str(path.relative_to(REPO_ROOT))]


def build_event_macro_tables(
    *,
    fixture_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Profile C: admitted ES macro events with vintage-safe consensus features."""
    path = fixture_path or ES_MACRO_FIXTURE
    payload = json.loads(path.read_text(encoding="utf-8"))
    admission_id = str(payload.get("admission_id") or payload.get("fixture_id"))
    instrument_family = str(payload.get("instrument_family") or "ES")
    instrument_id = f"FUT-{instrument_family}"

    instruments = [
        {
            "instrument_id": instrument_id,
            "admission_id": admission_id,
            "effective_from_ns": 0,
            "effective_to_ns": 9_999_999_999_999_999_999,
            "universe_version": admission_id,
        }
    ]

    information_events: list[dict[str, Any]] = []
    feature_snapshots: list[dict[str, Any]] = []
    realized_outcomes: list[dict[str, Any]] = []
    audit_exclusions: list[dict[str, Any]] = []
    market_observations: list[dict[str, Any]] = []

    for event in payload.get("events") or []:
        event_id = str(event["event_id"])
        release_raw = event.get("release_time")
        if release_raw is None:
            audit_exclusions.append(
                {
                    "reason_code": "UNRELEASED_MACRO_EVENT",
                    "row_ref": event_id,
                    "audit_version": "research_export_v1",
                }
            )
            continue
        release_ns = iso_to_epoch_ns(str(release_raw))
        scheduled_ns = iso_to_epoch_ns(str(event.get("scheduled_time") or release_raw))
        information_events.append(
            {
                "event_id": event_id,
                "event_type": str(event.get("event_type")),
                "instrument_id": instrument_id,
                "source_time_ns": scheduled_ns,
                "observed_at_ns": release_ns,
                "release_time_ns": release_ns,
                "vintage_version": "initial_release",
            }
        )
        consensus = event.get("consensus")
        actual = event.get("actual")
        feature_snapshots.append(
            {
                "feature_snapshot_id": f"fs-macro-{event_id}",
                "instrument_id": instrument_id,
                "decision_at_ns": release_ns,
                "earliest_usable_at_ns": release_ns,
                "feature_version": "macro_consensus_v1",
                "feature_values": {"consensus": consensus},
            }
        )
        if actual is not None:
            realized_outcomes.append(
                {
                    "decision_at_ns": release_ns,
                    "instrument_id": instrument_id,
                    "label_available_time_ns": release_ns + 1,
                    "target_version": "macro_actual_v1",
                    "event_id": event_id,
                    "actual": actual,
                }
            )
        else:
            audit_exclusions.append(
                {
                    "reason_code": "MISSING_ACTUAL_AT_RELEASE",
                    "row_ref": event_id,
                    "audit_version": "research_export_v1",
                }
            )

    if not information_events:
        raise ValueError("NO_RELEASED_MACRO_EVENTS")

    decision_times = [int(row["release_time_ns"]) for row in information_events]
    context = {
        "profile": PROFILE_EVENT_MACRO,
        "source_fixture": str(path.relative_to(REPO_ROOT)),
        "source_sha256": _fixture_source_sha256(path),
        "admission_id": admission_id,
        "decision_start_ns": min(decision_times),
        "decision_end_ns": max(decision_times) + 1,
        "decision_cutoff_ns": max(decision_times),
        "horizon_ns": 0,
        "experiment_binding": {
            "binding_kind": "RESEARCH_EXPORT_PROFILE",
            "profile": PROFILE_EVENT_MACRO,
            "admission_id": admission_id,
        },
    }
    tables = {
        "instruments": instruments,
        "market_observations": market_observations,
        "information_events": information_events,
        "feature_snapshots": feature_snapshots,
        "realized_outcomes": realized_outcomes,
        "audit_exclusions": audit_exclusions,
    }
    return context, tables, [str(path.relative_to(REPO_ROOT))]


__all__ = [
    "ES_MACRO_FIXTURE",
    "NVDA_BARS_FIXTURE",
    "PROFILE_EVENT_MACRO",
    "PROFILE_MARKET_TECHNICAL",
    "build_event_macro_tables",
    "build_market_technical_tables",
]
