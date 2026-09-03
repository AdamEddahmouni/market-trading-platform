from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from phase_1f_fixture_builders import build_phase_1f_artifacts
from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.news import normalize_news_record
from squeeze_core.contracts import ReplayMode
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.replay import ReplayEngine
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
NEWS_ROOT = FIXTURE_ROOT / "providers" / "news"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"


def _case(filename: str, fixture_id: str) -> dict[str, Any]:
    document = json.loads((NEWS_ROOT / filename).read_text(encoding="utf-8"))
    return next(
        item["record"] for item in document["cases"]
        if item["metadata"]["fixture_id"] == fixture_id
    )


def _context(ingested_at: str) -> AdapterContext:
    base = AdapterContext.model_validate_json((NEWS_ROOT / "context.json").read_text(encoding="utf-8"))
    return base.model_copy(update={
        "ingested_at": datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
    })


def _normalize(raw: dict[str, Any], received: str):
    result = normalize_news_record(raw, _context(received))
    if not result.accepted or len(result.observations) != 1:
        raise RuntimeError(f"Phase 1G fixture normalization drifted: {raw['source_record_id']}")
    return result.observations[0]


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
    )


def build_phase_1g_artifacts() -> dict[str, Any]:
    timeline = json.loads((EVIDENCE_ROOT / "news_availability_timeline.json").read_text(encoding="utf-8"))

    original_raw = _case("representative_cases.json", "news-complete-v1")
    original_raw.update({
        "published_at": timeline["original_published"],
        "provider_available_at": timeline["original_available"],
        "capture_timestamp": "2026-01-31T14:01:30Z",
    })
    update_raw = _case("update_cases.json", "news-updated")
    update_raw.update({
        "published_at": timeline["original_published"],
        "updated_at": "2026-01-31T14:20:00Z",
        "provider_available_at": timeline["update_available"],
        "capture_timestamp": "2026-01-31T14:20:45Z",
    })
    withdrawal_raw = _case("update_cases.json", "news-withdrawn")
    withdrawal_raw.update({
        "published_at": timeline["original_published"],
        "updated_at": timeline["withdrawal_available"],
        "provider_available_at": timeline["withdrawal_available"],
        "capture_timestamp": "2026-01-31T15:00:30Z",
    })

    news_observations = (
        _normalize(original_raw, timeline["original_received"]),
        _normalize(update_raw, timeline["update_received"]),
        _normalize(withdrawal_raw, timeline["withdrawal_received"]),
    )
    phase_1f = build_phase_1f_artifacts()
    observations = tuple(sorted(
        phase_1f["observations"] + news_observations,
        key=observation_order_key,
    ))
    if len(observations) != 15:
        raise RuntimeError("Phase 1G mixed fixture must contain exactly fifteen observations")

    jsonl_bytes = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    timeline_bundles = {
        label: build_point_in_time_evidence("TESTA", replay.observations, _policy(raw_as_of))
        for label, raw_as_of in timeline["as_of"].items()
    }
    final_bundle = timeline_bundles["after_withdrawal_receipt"]
    metadata = {
        "original_news_observation_sha256": canonical_hash(news_observations[0]),
        "updated_news_observation_sha256": canonical_hash(news_observations[1]),
        "withdrawn_news_observation_sha256": canonical_hash(news_observations[2]),
        "mixed_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
        **{
            f"{label}_bundle_sha256": bundle.bundle_hash
            for label, bundle in timeline_bundles.items()
        },
        "serialized_final_bundle_sha256": canonical_hash(final_bundle),
        "final_bundle_sha256": final_bundle.bundle_hash,
        "phase_1f_mixed_jsonl_sha256": phase_1f["metadata"]["mixed_jsonl_sha256"],
        "phase_1f_strict_replay_sha256": phase_1f["metadata"]["strict_replay_sha256"],
        "schema_version": "1.0.0",
    }
    return {
        "jsonl_bytes": jsonl_bytes,
        "metadata": metadata,
        "observations": observations,
        "news_observations": news_observations,
        "replay": replay,
        "timeline_bundles": timeline_bundles,
        "final_bundle": final_bundle,
    }


def write_artifacts() -> None:
    artifacts = build_phase_1g_artifacts()
    (EVIDENCE_ROOT / "normalized_phase_1g_point_in_time.jsonl").write_bytes(artifacts["jsonl_bytes"])
    (EVIDENCE_ROOT / "expected_phase_1g_bundle_metadata.json").write_bytes(
        canonical_json_bytes(artifacts["metadata"]) + b"\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1g_artifacts()["jsonl_bytes"].decode("utf-8"), end="")
