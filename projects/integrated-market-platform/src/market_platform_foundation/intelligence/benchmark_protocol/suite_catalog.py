"""IBP v1 suite catalog (30 cases; Smoke10 = first 10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .types import (
    IBP_FULL_SUITE_CASE_COUNT,
    IBP_PROTOCOL_ID,
    IBP_SMOKE10_CASE_COUNT,
    IBP_SUITE_CATALOG_SCHEMA_VERSION,
    IntelligenceBenchmarkBlindMode,
)

_CATALOG_RELATIVE = Path("tests/fixtures/intelligence_benchmark/ibp_suite_catalog_v1.json")


def default_suite_catalog_path(repository_root: Path) -> Path:
    return repository_root / _CATALOG_RELATIVE


def load_suite_catalog(repository_root: Path) -> dict[str, Any]:
    path = default_suite_catalog_path(repository_root)
    if not path.is_file():
        raise FileNotFoundError(f"IBP_SUITE_CATALOG_MISSING:{path}")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    validate_suite_catalog(catalog, repository_root=repository_root)
    return catalog


def validate_suite_catalog(catalog: dict[str, Any], *, repository_root: Path | None = None) -> None:
    if catalog.get("schema_version") != IBP_SUITE_CATALOG_SCHEMA_VERSION:
        raise ValueError("IBP_SUITE_SCHEMA_MISMATCH")
    if catalog.get("protocol_id") != IBP_PROTOCOL_ID:
        raise ValueError("IBP_SUITE_PROTOCOL_MISMATCH")
    cases = catalog.get("cases")
    if not isinstance(cases, list) or len(cases) != IBP_FULL_SUITE_CASE_COUNT:
        raise ValueError("IBP_SUITE_CASE_COUNT_INVALID")
    seen: set[str] = set()
    modes = list(IntelligenceBenchmarkBlindMode)
    for index, case in enumerate(cases):
        case_id = case.get("case_id")
        if not case_id or case_id in seen:
            raise ValueError("IBP_SUITE_CASE_ID_INVALID")
        seen.add(case_id)
        expected_mode = modes[index % len(modes)]
        if case.get("blind_mode") != expected_mode.value:
            raise ValueError("IBP_SUITE_BLIND_MODE_SEQUENCE_INVALID")
        gold_ref = case.get("evaluator_gold_ref")
        if not gold_ref or not str(gold_ref).startswith("evaluator_only/"):
            raise ValueError("IBP_SUITE_GOLD_REF_MUST_BE_EVALUATOR_ONLY")
        if repository_root is not None:
            gold_path = repository_root / "tests/fixtures/intelligence_benchmark" / gold_ref
            if not gold_path.is_file():
                raise FileNotFoundError(f"IBP_EVALUATOR_GOLD_MISSING:{gold_ref}")
    smoke10 = catalog.get("smoke10_case_ids")
    if not isinstance(smoke10, list) or len(smoke10) != IBP_SMOKE10_CASE_COUNT:
        raise ValueError("IBP_SMOKE10_LIST_INVALID")
    if smoke10 != [cases[i]["case_id"] for i in range(IBP_SMOKE10_CASE_COUNT)]:
        raise ValueError("IBP_SMOKE10_MUST_BE_FIRST_TEN_CASES")


def suite_catalog_fingerprint(catalog: dict[str, Any]) -> str:
    body = {
        "schema_version": catalog.get("schema_version"),
        "suite_id": catalog.get("suite_id"),
        "case_ids": [row["case_id"] for row in catalog.get("cases", [])],
    }
    return sha256_bytes(canonical_bytes(body))


def smoke10_case_ids(catalog: dict[str, Any]) -> tuple[str, ...]:
    return tuple(catalog.get("smoke10_case_ids", ()))


__all__ = [
    "default_suite_catalog_path",
    "load_suite_catalog",
    "smoke10_case_ids",
    "suite_catalog_fingerprint",
    "validate_suite_catalog",
]
