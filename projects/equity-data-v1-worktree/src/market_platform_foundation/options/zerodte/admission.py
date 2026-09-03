"""Fail-closed Phase C admission scaffold for O11 0DTE prerequisites.

Mirrors the Phase B chain-history admission shape
(``manifests/options/phase-b-chain-history-admission.json``) and the fail-closed
evaluation pattern of ``options/research/harness.evaluate_phase_b_admission()``.
The default manifest is an embedded constant with ``status="PENDING"`` and empty
``dataset_slots``: until a real Phase C dataset is procured, admitted, and slotted,
every entry point here reports blocked and fails closed.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_EXTERNAL_MANIFEST_PATH = _REPO_ROOT / "manifests" / "options" / "phase-c-intraday-chain-admission.json"

PHASE_C_ADMISSION_STATUS_PENDING = "PENDING"
PHASE_C_ADMISSION_STATUS_ADMITTED = "ADMITTED"
PHASE_C_DATA_NOT_ADMITTED_REASON = "PHASE_C_DATA_NOT_ADMITTED"
PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT = "PHASE_C_INTRADAY_CHAIN_SNAPSHOTS"
PHASE_C_HIGH_PRIORITY_REQUIREMENTS = (PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT,)

DEFAULT_ADMISSION_MANIFEST: dict[str, Any] = {
    "logical_id": "options.o11_zerodte_intraday_chain_admission",
    "schema_version": "1.0.0",
    "status": PHASE_C_ADMISSION_STATUS_PENDING,
    "phase": "C",
    "research_only": True,
    "gate_milestones": ["R-O11"],
    "admission_requirements": [
        {
            "requirement_id": PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT,
            "description": (
                "Single-name full intraday option-chain snapshots for the expiry day "
                "(0DTE), with aligned event_time/available_time bitemporality"
            ),
            "minimum_symbols": 3,
            "maximum_symbols": 5,
            "priority": "HIGH",
            "status": "NOT_ADMITTED",
        },
    ],
    "dataset_slots": [],
    "notes": (
        "Phase C intraday chain snapshots are not admitted. O11 0DTE analytics and "
        "execution-correctness linkage remain blocked until all HIGH-priority "
        "requirements are admitted and manifest status is ADMITTED. This package "
        "delivers fixture-proven prerequisite infrastructure only."
    ),
}


def load_phase_c_admission_manifest(path: Path | str | None = None) -> dict[str, Any]:
    """Embedded default manifest, or an explicit external manifest when given.

    The default is a defensive deep copy: callers cannot mutate module state.
    An explicit ``path`` must point at an existing JSON manifest file.
    """
    if path is None:
        return deepcopy(DEFAULT_ADMISSION_MANIFEST)
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"phase C admission manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"phase C admission manifest must be a JSON object: {manifest_path}")
    return payload


def evaluate_phase_c_admission(
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail-closed admission check for Phase C intraday-chain-snapshot datasets."""
    payload = manifest or load_phase_c_admission_manifest()
    status = str(payload.get("status", PHASE_C_ADMISSION_STATUS_PENDING))
    requirements = payload.get("admission_requirements", [])
    slots = payload.get("dataset_slots", [])
    if not isinstance(requirements, list):
        requirements = []
    if not isinstance(slots, list):
        slots = []

    requirement_rows: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        requirement_id = str(requirement.get("requirement_id", ""))
        requirement_status = str(requirement.get("status", "NOT_ADMITTED"))
        admitted_slots = [
            slot
            for slot in slots
            if isinstance(slot, dict)
            and str(slot.get("requirement_id", "")) == requirement_id
            and slot.get("content_path")
        ]
        row = {
            "requirement_id": requirement_id,
            "status": requirement_status,
            "admitted_slot_count": len(admitted_slots),
            "priority": requirement.get("priority"),
        }
        requirement_rows.append(row)
        if requirement_status != PHASE_C_ADMISSION_STATUS_ADMITTED and not admitted_slots:
            if requirement_id in PHASE_C_HIGH_PRIORITY_REQUIREMENTS:
                blocking_reasons.append(f"{requirement_id}_NOT_ADMITTED")

    admitted = status == PHASE_C_ADMISSION_STATUS_ADMITTED and not blocking_reasons
    if status != PHASE_C_ADMISSION_STATUS_ADMITTED:
        blocking_reasons.insert(0, "PHASE_C_MANIFEST_STATUS_PENDING")
    if admitted and not slots:
        admitted = False
        blocking_reasons.append("PHASE_C_DATASET_SLOTS_EMPTY")

    return {
        "admitted": admitted,
        "status": status,
        "logical_id": payload.get("logical_id"),
        "requirement_rows": requirement_rows,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "research_only": True,
    }


def run_o11_zerodte_prerequisite_harness(
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """O11 prerequisite harness — blocked/fail-closed until Phase C data is admitted."""
    admission = evaluate_phase_c_admission(manifest)
    if not admission["admitted"]:
        return {
            "available": False,
            "gate_status": "BLOCKED",
            "reason": PHASE_C_DATA_NOT_ADMITTED_REASON,
            "blocking_reasons": list(admission["blocking_reasons"]),
            "admission": admission,
            "partition_scaffold": {"fold_count": 0, "partitions": []},
            "research_only": True,
        }
    # Admitted path stays out of scope by design: post-admission increments
    # (expiration-aware analytics, execution-correctness linkage) require their
    # own design docs and forward-validation gates before anything runs here.
    raise NotImplementedError(
        "Phase C admission succeeded; post-admission O11 analytics are separate "
        "increments that do not exist yet."
    )


__all__ = [
    "DEFAULT_ADMISSION_MANIFEST",
    "DEFAULT_EXTERNAL_MANIFEST_PATH",
    "PHASE_C_ADMISSION_STATUS_ADMITTED",
    "PHASE_C_ADMISSION_STATUS_PENDING",
    "PHASE_C_DATA_NOT_ADMITTED_REASON",
    "PHASE_C_HIGH_PRIORITY_REQUIREMENTS",
    "PHASE_C_INTRADAY_CHAIN_SNAPSHOTS_REQUIREMENT",
    "evaluate_phase_c_admission",
    "load_phase_c_admission_manifest",
    "run_o11_zerodte_prerequisite_harness",
]
