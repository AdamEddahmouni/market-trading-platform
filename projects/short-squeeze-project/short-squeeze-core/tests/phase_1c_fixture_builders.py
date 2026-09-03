import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finviz import normalize_finviz_snapshot_record
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_record
from squeeze_core.contracts import ReplayMode
from squeeze_core.evidence import (
    PointInTimeEvidenceBundle,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.replay import ReplayEngine, ReplayResult
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash, canonical_json_bytes, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
FINVIZ_ROOT = FIXTURE_ROOT / "providers" / "finviz"
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"


@dataclass(frozen=True, slots=True)
class Phase1CArtifacts:
    jsonl: bytes
    replay: ReplayResult
    bundle: PointInTimeEvidenceBundle
    raw_hashes: dict[str, str]


def _document() -> dict:
    return json.loads((EVIDENCE_ROOT / "mixed_finviz_ibkr_cases.json").read_text())


def _finviz_record() -> dict:
    cases = json.loads((FINVIZ_ROOT / "representative_cases.json").read_text())["cases"]
    return next(
        case["record"]
        for case in cases
        if case["metadata"]["fixture_id"] == _document()["finviz_fixture_id"]
    )


def load_evidence_policy() -> PointInTimeEvidencePolicy:
    return PointInTimeEvidencePolicy.model_validate(_document()["policy"])


def build_phase_1c_artifacts() -> Phase1CArtifacts:
    document = _document()
    finviz_record = _finviz_record()
    finviz_context = AdapterContext.model_validate_json(
        (FINVIZ_ROOT / "context.json").read_text()
    )
    ibkr_context = AdapterContext.model_validate(document["ibkr_context"])
    finviz_result = normalize_finviz_snapshot_record(finviz_record, finviz_context)
    ibkr_result = normalize_ibkr_borrow_record(document["ibkr_record"], ibkr_context)
    observations = sorted(
        finviz_result.observations + ibkr_result.observations,
        key=observation_order_key,
    )
    if not finviz_result.accepted or not ibkr_result.accepted or len(observations) != 3:
        raise RuntimeError("Phase 1C fixture normalization expectations drifted")
    jsonl = serialize_jsonl(observations)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    bundle = build_point_in_time_evidence("TESTA", replay.observations, load_evidence_policy())
    return Phase1CArtifacts(
        jsonl=jsonl,
        replay=replay,
        bundle=bundle,
        raw_hashes={
            "finviz_complete_raw_sha256": canonical_hash(finviz_record),
            "ibkr_mixed_raw_sha256": canonical_hash(document["ibkr_record"]),
            "finviz_observation_sha256": canonical_hash(finviz_result.observations[0]),
        },
    )


def expected_metadata(artifacts: Phase1CArtifacts) -> bytes:
    values = {
        **artifacts.raw_hashes,
        "mixed_jsonl_sha256": hashlib.sha256(artifacts.jsonl).hexdigest(),
        "strict_replay_sha256": artifacts.replay.result_hash,
        "evidence_bundle_sha256": artifacts.bundle.bundle_hash,
        "evidence_bundle_serialized_sha256": canonical_hash(artifacts.bundle),
        "phase_1a_minimal_sha256": hashlib.sha256(
            (FIXTURE_ROOT / "minimal_session.jsonl").read_bytes()
        ).hexdigest(),
        "phase_1a_quality_sha256": hashlib.sha256(
            (FIXTURE_ROOT / "quality_edge_cases.jsonl").read_bytes()
        ).hexdigest(),
        "phase_1a_out_of_order_sha256": hashlib.sha256(
            (FIXTURE_ROOT / "out_of_order_session.jsonl").read_bytes()
        ).hexdigest(),
        "phase_1b_ibkr_jsonl_sha256": hashlib.sha256(
            (FIXTURE_ROOT / "providers" / "ibkr" / "normalized_session.jsonl").read_bytes()
        ).hexdigest(),
    }
    return canonical_json_bytes(values) + b"\n"


def write_artifacts() -> None:
    artifacts = build_phase_1c_artifacts()
    (EVIDENCE_ROOT / "normalized_point_in_time.jsonl").write_bytes(artifacts.jsonl)
    (EVIDENCE_ROOT / "expected_bundle_metadata.json").write_bytes(
        expected_metadata(artifacts)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_artifacts()
    else:
        print(build_phase_1c_artifacts().jsonl.decode("utf-8"), end="")
