from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from phase_1d_fixture_builders import build_phase_1d_artifacts
from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.sec import normalize_sec_filing_records
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.replay import ReplayEngine
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.contracts import ReplayMode
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
SEC_ROOT = FIXTURE_ROOT / "providers" / "sec"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"


def _case(filename: str, fixture_id: str) -> dict[str, Any]:
    document = json.loads((SEC_ROOT / filename).read_text(encoding="utf-8"))
    return next(
        item["record"]
        for item in document["cases"]
        if item["metadata"]["fixture_id"] == fixture_id
    )


def _context(ingested_at: str) -> AdapterContext:
    base = AdapterContext.model_validate_json(
        (SEC_ROOT / "context.json").read_text(encoding="utf-8")
    )
    return base.model_copy(
        update={
            "ingested_at": datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
        }
    )


def build_phase_1e_artifacts() -> dict[str, Any]:
    timeline = json.loads(
        (EVIDENCE_ROOT / "sec_filing_availability_timeline.json").read_text(
            encoding="utf-8"
        )
    )
    original_raw = _case("representative_cases.json", "sec-complete-original-v1")
    amendment_raw = _case("amendment_cases.json", "sec-amendment-v1")
    sec_result = normalize_sec_filing_records(
        [original_raw, amendment_raw], _context(timeline["amendment_received"])
    )
    if not sec_result.accepted or len(sec_result.observations) != 2:
        raise RuntimeError("Phase 1E SEC fixture normalization drifted")
    original, amendment = sorted(
        sec_result.observations, key=lambda item: item.source_timestamp
    )
    original_received = datetime.fromisoformat(
        timeline["original_received"].replace("Z", "+00:00")
    )
    original = original.model_copy(
        update={
            "received_timestamp": original_received,
            "effective_timestamp": max(original.source_timestamp, original_received),
        }
    )

    phase_1d = build_phase_1d_artifacts()
    observations = tuple(
        sorted(
            phase_1d["observations"] + (original, amendment),
            key=observation_order_key,
        )
    )
    if len(observations) != 7:
        raise RuntimeError("Phase 1E mixed fixture must contain exactly seven observations")
    jsonl_bytes = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)

    timeline_bundles = {}
    for label, raw_as_of in timeline["as_of"].items():
        policy = PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat(raw_as_of.replace("Z", "+00:00")),
            allow_stale=True,
            allow_delayed=True,
            allow_unknown_freshness=True,
            include_published_short_interest_domain=True,
            include_sec_filings_domain=True,
        )
        timeline_bundles[label] = build_point_in_time_evidence(
            "TESTA", replay.observations, policy
        )

    metadata = {
        "sec_complete_raw_sha256": canonical_hash(original_raw),
        "sec_original_observation_sha256": canonical_hash(original),
        "sec_amendment_observation_sha256": canonical_hash(amendment),
        "mixed_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
        "before_acceptance_bundle_sha256": timeline_bundles["before_acceptance"].bundle_hash,
        "after_acceptance_before_receipt_bundle_sha256": timeline_bundles["after_acceptance_before_receipt"].bundle_hash,
        "after_original_receipt_bundle_sha256": timeline_bundles["after_original_receipt"].bundle_hash,
        "before_amendment_receipt_bundle_sha256": timeline_bundles["before_amendment_receipt"].bundle_hash,
        "after_amendment_receipt_bundle_sha256": timeline_bundles["after_amendment_receipt"].bundle_hash,
        "after_amendment_serialized_sha256": canonical_hash(
            timeline_bundles["after_amendment_receipt"]
        ),
        "phase_1d_mixed_jsonl_sha256": phase_1d["metadata"]["mixed_jsonl_sha256"],
        "phase_1d_strict_replay_sha256": phase_1d["metadata"]["strict_replay_sha256"],
        "phase_1c_bundle_sha256": "d633447eb59cc8cdb059429e53498ca8a49f3895da0800fb56c1ff43729f2455",
    }
    return {
        "jsonl_bytes": jsonl_bytes,
        "metadata": metadata,
        "observations": observations,
        "replay": replay,
        "timeline_bundles": timeline_bundles,
    }


def write_artifacts() -> None:
    artifacts = build_phase_1e_artifacts()
    (EVIDENCE_ROOT / "normalized_phase_1e_point_in_time.jsonl").write_bytes(
        artifacts["jsonl_bytes"]
    )
    (EVIDENCE_ROOT / "expected_phase_1e_bundle_metadata.json").write_bytes(
        canonical_json_bytes(artifacts["metadata"]) + b"\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1e_artifacts()["jsonl_bytes"].decode("utf-8"), end="")
