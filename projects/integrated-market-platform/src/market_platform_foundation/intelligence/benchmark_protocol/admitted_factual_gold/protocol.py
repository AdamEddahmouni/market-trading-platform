"""Load and validate admitted factual gold protocol fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .hashing import compute_caseset_hash, compute_goldset_hash, factual_gold_hash_algorithm
from .validation import validate_factual_gold_protocol

_PROTOCOL_RELATIVE = Path(
    "tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_empty.json"
)
_CANDIDATE_PROTOCOL_RELATIVE = Path(
    "tests/fixtures/intelligence_benchmark/admitted_factual_gold/protocol_ibp_factual_smoke_v1_candidate.json"
)


def default_factual_gold_protocol_path(repository_root: Path) -> Path:
    return repository_root / _PROTOCOL_RELATIVE


def candidate_factual_gold_protocol_path(repository_root: Path) -> Path:
    return repository_root / _CANDIDATE_PROTOCOL_RELATIVE


def load_factual_gold_protocol(repository_root: Path) -> dict[str, Any]:
    path = default_factual_gold_protocol_path(repository_root)
    if not path.is_file():
        raise FileNotFoundError(f"IBP_FACTUAL_GOLD_PROTOCOL_MISSING:{path}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    validate_factual_gold_protocol(protocol)
    return protocol


def load_candidate_factual_gold_protocol(repository_root: Path) -> dict[str, Any]:
    path = candidate_factual_gold_protocol_path(repository_root)
    if not path.is_file():
        raise FileNotFoundError(f"IBP_FACTUAL_GOLD_CANDIDATE_PROTOCOL_MISSING:{path}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    validate_factual_gold_protocol(protocol, allow_empty_cases=False)
    return protocol


def empty_protocol_template() -> dict[str, Any]:
    """Canonical M1 empty protocol (no cases; hashes over empty sets)."""
    cases: list[dict[str, Any]] = []
    return {
        "artifact_kind": "ibp_admitted_factual_gold_protocol_v1",
        "schema_version": "imp.ibp-admitted-factual-gold/1.0.0",
        "hypothesis_id": "LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1",
        "protocol_version": "IBP_FACTUAL_SMOKE_V1",
        "hash_algorithm": factual_gold_hash_algorithm(),
        "gold_source_independent": True,
        "caseset_hash": compute_caseset_hash(cases),
        "goldset_hash": compute_goldset_hash([]),
        "cases": cases,
        "freeze": {
            "status": "UNFROZEN",
            "cases_constructed": False,
            "smoke10_executed": False,
        },
    }


__all__ = [
    "candidate_factual_gold_protocol_path",
    "default_factual_gold_protocol_path",
    "empty_protocol_template",
    "load_candidate_factual_gold_protocol",
    "load_factual_gold_protocol",
]
