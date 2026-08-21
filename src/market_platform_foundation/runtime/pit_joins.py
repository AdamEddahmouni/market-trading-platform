"""Centralized point-in-time joins over the bitemporal reference store (O-23)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..contracts.reference import ReferenceKind, ReferenceQualityFlag
from .bitemporal_store import BitemporalReferenceStore, load_reference_records

P0_FIXTURE_DIR = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "platform" / "p0"
)
P0_SLICE = P0_FIXTURE_DIR / "p0_bitemporal_slice.json"
P0_EXPECTED = P0_FIXTURE_DIR / "p0_bitemporal_expected.json"


def join_as_of(
    store: BitemporalReferenceStore,
    kind: ReferenceKind | str,
    entity_key: str,
    market_time: str,
    knowledge_time: str,
) -> dict[str, Any]:
    resolved_kind = kind if isinstance(kind, ReferenceKind) else ReferenceKind(str(kind))
    key = entity_key.upper()
    record = store.as_of(resolved_kind, key, market_time, knowledge_time)
    siblings = store.versions(resolved_kind, key)
    flags: list[str] = []
    later = [row for row in siblings if row.known_from > knowledge_time]
    if record is None:
        flags.append(ReferenceQualityFlag.REFERENCE_UNAVAILABLE.value)
        if later:
            flags.append(ReferenceQualityFlag.LOOKAHEAD_REJECTED.value)
        return {
            "status": "UNAVAILABLE",
            "record": None,
            "payload": {},
            "record_version": None,
            "quality_flags": flags,
        }
    if later:
        flags.append(ReferenceQualityFlag.LOOKAHEAD_REJECTED.value)
        flags.append(ReferenceQualityFlag.REFERENCE_SUPERSEDED.value)
    return {
        "status": "AVAILABLE",
        "record": record,
        "payload": dict(record.payload),
        "record_version": record.record_version,
        "quality_flags": flags,
    }


def store_from_fixture(path: Path | None = None) -> BitemporalReferenceStore:
    payload = json.loads((path or P0_SLICE).read_text(encoding="utf-8"))
    store = BitemporalReferenceStore()
    for record in load_reference_records(payload.get("records") or []):
        store.append(record)
    return store


def run_p0_bitemporal_gate_validation(*, fixture_path: Path | None = None) -> dict[str, Any]:
    expected = json.loads(P0_EXPECTED.read_text(encoding="utf-8"))
    store = store_from_fixture(fixture_path)
    gate_summary: list[dict[str, Any]] = []
    for query in expected.get("queries") or []:
        result = join_as_of(
            store,
            str(query["kind"]),
            str(query["entity_key"]),
            str(query["market_time"]),
            str(query["knowledge_time"]),
        )
        failures: list[str] = []
        if result["status"] != query.get("expected_status"):
            failures.append("STATUS_MISMATCH")
        if query.get("expected_spec_version") and result["payload"].get("spec_version") != query["expected_spec_version"]:
            failures.append("SPEC_VERSION_MISMATCH")
        if query.get("expected_earnings_event_time") and result["payload"].get("earnings_event_time") != query["expected_earnings_event_time"]:
            failures.append("EARNINGS_TIME_MISMATCH")
        if query.get("expected_open_interest") is not None and result["payload"].get("open_interest") != query["expected_open_interest"]:
            failures.append("OI_MISMATCH")
        if query.get("expected_dividend_yield") and result["payload"].get("dividend_yield") != query["expected_dividend_yield"]:
            failures.append("DIVIDEND_MISMATCH")
        for flag in query.get("expected_flags_include") or []:
            if flag not in result["quality_flags"]:
                failures.append(f"MISSING_FLAG_{flag}")
        gate_summary.append(
            {
                "id": query.get("id"),
                "status": "PASS" if not failures else "FAIL",
                "failures": failures,
            }
        )
    aggregate = "PASS" if gate_summary and all(row["status"] == "PASS" for row in gate_summary) else "FAIL"
    return {
        "gate_id": "P0-S1",
        "aggregate_status": aggregate,
        "gate_summary": gate_summary,
        "fixture_refs": [
            {
                "role": "bitemporal_slice",
                "admission_id": expected.get("admission_id"),
                "admitted_fixture_id": "p0_bitemporal_slice",
            }
        ],
    }


__all__ = [
    "join_as_of",
    "run_p0_bitemporal_gate_validation",
    "store_from_fixture",
]
