from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from phase_1e_fixture_builders import build_phase_1e_artifacts
from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.halts import normalize_trading_halt_record
from squeeze_core.contracts import ReplayMode
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.replay import ReplayEngine
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
HALT_ROOT = FIXTURE_ROOT / "providers" / "halts"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"


def _case(filename: str, fixture_id: str) -> dict[str, Any]:
    document = json.loads((HALT_ROOT / filename).read_text(encoding="utf-8"))
    return next(
        item["record"]
        for item in document["cases"]
        if item["metadata"]["fixture_id"] == fixture_id
    )


def _context(ingested_at: str) -> AdapterContext:
    base = AdapterContext.model_validate_json(
        (HALT_ROOT / "context.json").read_text(encoding="utf-8")
    )
    return base.model_copy(
        update={
            "ingested_at": datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
        }
    )


def _normalize(filename: str, fixture_id: str, received: str):
    raw = _case(filename, fixture_id)
    result = normalize_trading_halt_record(raw, _context(received))
    if not result.accepted or len(result.observations) != 1:
        raise RuntimeError(f"Phase 1F fixture normalization drifted: {fixture_id}")
    return raw, result.observations[0]


def build_phase_1f_artifacts() -> dict[str, Any]:
    timeline = json.loads(
        (EVIDENCE_ROOT / "halt_resumption_timeline.json").read_text(encoding="utf-8")
    )
    complete_raw, halt = _normalize(
        "representative_cases.json", "halt-complete-v1", timeline["announcement_received"]
    )
    _, quote_schedule = _normalize(
        "lifecycle_cases.json", "halt-quote-scheduled", timeline["quote_schedule_received"]
    )
    _, quotes_resumed = _normalize(
        "lifecycle_cases.json", "halt-quote-resumed", timeline["quotes_resumed"]
    )
    _, trade_schedule = _normalize(
        "lifecycle_cases.json", "halt-trade-scheduled", timeline["trade_schedule_published"]
    )
    _, trading_resumed = _normalize(
        "lifecycle_cases.json", "halt-trading-resumed", timeline["trading_resumed"]
    )
    halt_observations = (
        halt,
        quote_schedule,
        quotes_resumed,
        trade_schedule,
        trading_resumed,
    )

    phase_1e = build_phase_1e_artifacts()
    observations = tuple(
        sorted(phase_1e["observations"] + halt_observations, key=observation_order_key)
    )
    if len(observations) != 12:
        raise RuntimeError("Phase 1F mixed fixture must contain exactly twelve observations")
    jsonl_bytes = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)

    timeline_bundles = {}
    for label, raw_as_of in timeline["as_of"].items():
        timeline_bundles[label] = build_point_in_time_evidence(
            "TESTA",
            replay.observations,
            PointInTimeEvidencePolicy(
                as_of=datetime.fromisoformat(raw_as_of.replace("Z", "+00:00")),
                allow_stale=True,
                allow_delayed=True,
                allow_unknown_freshness=True,
                include_published_short_interest_domain=True,
                include_sec_filings_domain=True,
                include_trading_halts_domain=True,
            ),
        )

    final_bundle = build_point_in_time_evidence(
        "TESTA",
        replay.observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat("2026-01-31T16:00:00+00:00"),
            allow_stale=True,
            allow_delayed=True,
            allow_unknown_freshness=True,
            include_published_short_interest_domain=True,
            include_sec_filings_domain=True,
            include_trading_halts_domain=True,
        ),
    )
    metadata = {
        "halt_complete_raw_sha256": canonical_hash(complete_raw),
        "halt_observation_sha256": canonical_hash(halt),
        "quote_schedule_observation_sha256": canonical_hash(quote_schedule),
        "quotes_resumed_observation_sha256": canonical_hash(quotes_resumed),
        "trade_schedule_observation_sha256": canonical_hash(trade_schedule),
        "trading_resumed_observation_sha256": canonical_hash(trading_resumed),
        "mixed_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
        "before_announcement_bundle_sha256": timeline_bundles["before_announcement"].bundle_hash,
        "after_announcement_receipt_bundle_sha256": timeline_bundles["after_announcement_receipt"].bundle_hash,
        "after_quote_schedule_bundle_sha256": timeline_bundles["after_quote_schedule"].bundle_hash,
        "after_quotes_resumed_bundle_sha256": timeline_bundles["after_quotes_resumed"].bundle_hash,
        "after_trade_schedule_bundle_sha256": timeline_bundles["after_trade_schedule"].bundle_hash,
        "after_trading_resumed_bundle_sha256": timeline_bundles["after_trading_resumed"].bundle_hash,
        "serialized_final_bundle_sha256": canonical_hash(final_bundle),
        "final_bundle_sha256": final_bundle.bundle_hash,
        "phase_1e_mixed_jsonl_sha256": phase_1e["metadata"]["mixed_jsonl_sha256"],
        "phase_1e_strict_replay_sha256": phase_1e["metadata"]["strict_replay_sha256"],
        "schema_version": "1.0.0",
    }
    return {
        "jsonl_bytes": jsonl_bytes,
        "metadata": metadata,
        "observations": observations,
        "halt_observations": halt_observations,
        "replay": replay,
        "timeline_bundles": timeline_bundles,
        "final_bundle": final_bundle,
    }


def write_artifacts() -> None:
    artifacts = build_phase_1f_artifacts()
    (EVIDENCE_ROOT / "normalized_phase_1f_point_in_time.jsonl").write_bytes(
        artifacts["jsonl_bytes"]
    )
    (EVIDENCE_ROOT / "expected_phase_1f_bundle_metadata.json").write_bytes(
        canonical_json_bytes(artifacts["metadata"]) + b"\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1f_artifacts()["jsonl_bytes"].decode("utf-8"), end="")
