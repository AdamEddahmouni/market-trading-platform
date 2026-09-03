import hashlib
import json
import subprocess
import sys
from pathlib import Path

from squeeze_core.serialization import canonical_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_phase_2v_outcome_anchors import build_anchor_results  # noqa: E402

METADATA = REPO_ROOT / "tests/fixtures/validation/outcome_amendment/expected_phase_2v_outcome_metadata.json"


def test_all_required_additive_anchors_recompute():
    expected = json.loads(METADATA.read_text(encoding="utf-8"))["anchors"]
    results = build_anchor_results()
    assert len(expected) == len(results) == 31
    actual = {name: (hashlib.sha256(value).hexdigest() if isinstance(value, bytes)
                     else canonical_hash(value)) for name, value in results.items()}
    assert actual == expected


def test_generator_is_byte_identical_on_repeated_runs():
    tracked = [METADATA,
               REPO_ROOT / "tests/fixtures/validation/outcome_amendment/biya_outcome_case.json",
               REPO_ROOT / "apps/biya-validation-demo/data/biya-outcome-case.json"]
    before = {path: path.read_bytes() for path in tracked}
    for _ in range(2):
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts/generate_phase_2v_outcome_anchors.py")],
                       cwd=REPO_ROOT, check=True)
    assert {path: path.read_bytes() for path in tracked} == before


def test_public_fixture_contains_no_local_paths_or_private_fields():
    rendered = (REPO_ROOT / "apps/biya-validation-demo/data/biya-outcome-case.json").read_text(encoding="utf-8")
    lowered = rendered.lower()
    assert "c:\\" not in lowered
    for forbidden in ("api_key", "authorization", "cookie", "account_id", "private_url"):
        assert forbidden not in lowered
