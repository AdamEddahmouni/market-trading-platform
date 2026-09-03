import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_record
from squeeze_core.contracts import ReplayMode
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
FINRA_ROOT = FIXTURE_ROOT / "providers" / "finra"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"


def _cases(filename: str) -> dict[str, dict[str, Any]]:
    document = json.loads((FINRA_ROOT / filename).read_text(encoding="utf-8"))
    return {
        case["metadata"]["fixture_id"]: case["record"] for case in document["cases"]
    }


def _context(ingested_at: str) -> AdapterContext:
    base = AdapterContext.model_validate_json(
        (FINRA_ROOT / "context.json").read_text(encoding="utf-8")
    )
    return base.model_copy(
        update={
            "ingested_at": datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
        }
    )


def build_phase_1d_artifacts() -> dict[str, Any]:
    representative = _cases("representative_cases.json")
    revisions = _cases("revision_cases.json")
    timeline = json.loads(
        (EVIDENCE_ROOT / "short_interest_publication_timeline.json").read_text(
            encoding="utf-8"
        )
    )
    original_record = representative["finra-complete-v1"]
    correction_record = revisions["finra-corrected-v1"]
    original_result = normalize_finra_short_interest_record(
        original_record, _context(timeline["original_received"])
    )
    correction_result = normalize_finra_short_interest_record(
        correction_record, _context(timeline["correction_received"])
    )
    if not original_result.accepted or not correction_result.accepted:
        raise RuntimeError("Phase 1D FINRA fixture normalization drifted")

    phase_1c_observations = tuple(
        load_fixture(EVIDENCE_ROOT / "normalized_point_in_time.jsonl")
    )
    observations = tuple(
        sorted(
            phase_1c_observations
            + original_result.observations
            + correction_result.observations,
            key=observation_order_key,
        )
    )
    if len(observations) != 5:
        raise RuntimeError("Phase 1D mixed fixture must contain exactly five observations")
    jsonl_bytes = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)

    policies: dict[str, PointInTimeEvidencePolicy] = {}
    timeline_bundles = {}
    for label, raw_as_of in timeline["as_of"].items():
        policy = PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat(raw_as_of.replace("Z", "+00:00")),
            allow_stale=True,
            allow_delayed=True,
            allow_unknown_freshness=True,
            include_published_short_interest_domain=True,
        )
        policies[label] = policy
        timeline_bundles[label] = build_point_in_time_evidence(
            "TESTA", replay.observations, policy
        )

    metadata = {
        "finra_complete_raw_sha256": canonical_hash(original_record),
        "finra_original_observation_sha256": canonical_hash(
            original_result.observations[0]
        ),
        "finra_correction_observation_sha256": canonical_hash(
            correction_result.observations[0]
        ),
        "mixed_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
        "before_publication_bundle_sha256": timeline_bundles[
            "before_publication"
        ].bundle_hash,
        "after_publication_before_receipt_bundle_sha256": timeline_bundles[
            "after_publication_before_receipt"
        ].bundle_hash,
        "after_original_receipt_bundle_sha256": timeline_bundles[
            "after_original_receipt"
        ].bundle_hash,
        "before_correction_receipt_bundle_sha256": timeline_bundles[
            "before_correction_receipt"
        ].bundle_hash,
        "after_correction_receipt_bundle_sha256": timeline_bundles[
            "after_correction_receipt"
        ].bundle_hash,
        "after_correction_serialized_sha256": canonical_hash(
            timeline_bundles["after_correction_receipt"]
        ),
    }
    return {
        "jsonl_bytes": jsonl_bytes,
        "metadata": metadata,
        "observations": observations,
        "replay": replay,
        "policies": policies,
        "timeline_bundles": timeline_bundles,
    }


def write_artifacts() -> None:
    artifacts = build_phase_1d_artifacts()
    (EVIDENCE_ROOT / "normalized_phase_1d_point_in_time.jsonl").write_bytes(
        artifacts["jsonl_bytes"]
    )
    (EVIDENCE_ROOT / "expected_phase_1d_bundle_metadata.json").write_bytes(
        canonical_json_bytes(artifacts["metadata"]) + b"\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1d_artifacts()["jsonl_bytes"].decode("utf-8"), end="")
