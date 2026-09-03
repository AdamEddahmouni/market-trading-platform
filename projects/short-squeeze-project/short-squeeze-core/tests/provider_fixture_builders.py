import argparse
import hashlib
import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_records
from squeeze_core.contracts import ReplayMode
from squeeze_core.replay import ReplayEngine
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_json_bytes, parse_jsonl, serialize_jsonl


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "providers" / "ibkr"


def build_ibkr_normalized_session() -> bytes:
    context = AdapterContext.model_validate_json((FIXTURE_ROOT / "context.json").read_text())
    cases = json.loads((FIXTURE_ROOT / "representative_cases.json").read_text())["cases"]
    replay_types = {"COMPLETE_RECORD", "EXPLICIT_ZERO_FEE", "MISSING_AVAILABILITY"}
    records = [case["record"] for case in cases if case["metadata"]["fixture_type"] in replay_types]
    result = normalize_ibkr_borrow_records(records, context)
    if not result.accepted or len(result.observations) != 6:
        raise RuntimeError("provider fixture expectations drifted")
    return serialize_jsonl(sorted(result.observations, key=observation_order_key))


def expected_artifact_hashes(session: bytes) -> bytes:
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(list(parse_jsonl(session.splitlines())))
    values = {
        "normalized_session_sha256": hashlib.sha256(session).hexdigest(),
        "strict_replay_sha256": replay.result_hash,
    }
    return canonical_json_bytes(values) + b"\n"


def write_ibkr_fixtures() -> None:
    session = build_ibkr_normalized_session()
    (FIXTURE_ROOT / "normalized_session.jsonl").write_bytes(session)
    (FIXTURE_ROOT / "expected_artifact_hashes.json").write_bytes(
        expected_artifact_hashes(session)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_ibkr_fixtures()
    else:
        print(build_ibkr_normalized_session().decode("utf-8"), end="")
