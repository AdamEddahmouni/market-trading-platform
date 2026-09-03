"""Cross-check the machine-readable domain matrix against the actual code.

The matrix in ``docs/phase-1-evidence-domain-matrix.json`` is only trustworthy if it cannot
drift from the code. This test asserts that every declared domain maps to a real
``CoverageDomain``, that each ``event_type``/``payload_type``/``payload_model`` triple matches
the canonical ``PAYLOAD_BINDINGS``, that referenced provider modules import, and that referenced
documentation files exist.
"""

import importlib
import json
from pathlib import Path

from squeeze_core.contracts.enums import EventType, PayloadType
from squeeze_core.contracts.observation import PAYLOAD_BINDINGS
from squeeze_core.evidence import CoverageDomain

REPO = Path(__file__).parents[2]
MATRIX = REPO / "docs" / "phase-1-evidence-domain-matrix.json"


def _matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def test_matrix_covers_exactly_every_coverage_domain() -> None:
    declared = {entry["coverage_domain"] for entry in _matrix()["domains"]}
    assert declared == {member.value for member in CoverageDomain}


def test_matrix_event_and_payload_bindings_match_code() -> None:
    for entry in _matrix()["domains"]:
        event_type = EventType(entry["event_type"])
        expected_payload_type, expected_model = PAYLOAD_BINDINGS[event_type]
        assert entry["payload_type"] == expected_payload_type.value, entry["coverage_domain"]
        assert entry["payload_type"] == PayloadType(entry["payload_type"]).value
        assert entry["payload_model"] == expected_model.__name__, entry["coverage_domain"]


def test_matrix_provider_modules_import() -> None:
    for entry in _matrix()["domains"]:
        for module in entry["provider_modules"]:
            assert importlib.import_module(module) is not None


def test_matrix_documentation_files_exist() -> None:
    missing = []
    for entry in _matrix()["domains"]:
        for doc in entry["documentation"]:
            if not (REPO / doc).exists():
                missing.append(doc)
    assert missing == [], f"referenced documentation missing: {sorted(set(missing))}"


def test_matrix_fixture_provenance_classes_are_allowed() -> None:
    allowed = {
        "SANITIZED_RECORDED_SAMPLE",
        "SANITIZED_REPRESENTATIVE_SAMPLE",
        "SYNTHETIC_EDGE_CASE",
    }
    for entry in _matrix()["domains"]:
        assert set(entry["fixture_provenance"]) <= allowed, entry["coverage_domain"]
