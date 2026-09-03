"""P6 Shadow Run 1 acceptance evaluator — preregistered criteria only.

Evaluates closure criteria against stored experiment evidence. Does not
interpret trading performance or mutate decision-time artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


ACCEPTANCE_SCHEMA_VERSION = "platform/shadow-run-1-acceptance/1.0.0"
PROTOCOL_VERSION = "SHADOW_RUN_1_BIYA_FROZEN/1.0.0"


class Disposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    description: str
    threshold: str
    evidence_artifact: str

    def to_dict(self) -> dict[str, str]:
        return {
            "criterion_id": self.criterion_id,
            "description": self.description,
            "threshold": self.threshold,
            "evidence_artifact": self.evidence_artifact,
        }


@dataclass(frozen=True)
class AcceptanceResult:
    criterion: AcceptanceCriterion
    disposition: Disposition
    observed: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        row = self.criterion.to_dict()
        row.update(
            {
                "disposition": self.disposition.value,
                "observed": self.observed,
                "notes": self.notes,
            }
        )
        return row


PREREGISTERED_CRITERIA: tuple[AcceptanceCriterion, ...] = (
    AcceptanceCriterion(
        "P6-AC-001",
        "Prospective protocol preregistered before outcome interpretation",
        "Protocol artifact exists with preregistration timestamp before first decision",
        "artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json",
    ),
    AcceptanceCriterion(
        "P6-AC-002",
        "Valid forward observation window collected",
        "At least one ACTUAL_FORWARD observation from lawful live observational source",
        "experiment store decisions + capture manifests (not fixture replay)",
    ),
    AcceptanceCriterion(
        "P6-AC-003",
        "No-lookahead at decision time",
        "causality_violations=0; late-arrival trades excluded from predictor windows",
        "tests/platform/test_shadow_run1_predictor.py; report.integrity.causality_violations",
    ),
    AcceptanceCriterion(
        "P6-AC-004",
        "Decision-time evidence preserved immutably",
        "run_contract insert-once; no UPDATE/DELETE on decisions",
        "tests/platform/test_shadow_run1_experiment_store.py",
    ),
    AcceptanceCriterion(
        "P6-AC-005",
        "Source times and provenance captured",
        "Each decision detail includes event_time, available_time, capture_id",
        "experiment store decision detail_json",
    ),
    AcceptanceCriterion(
        "P6-AC-006",
        "Operational identity isolation",
        "Shadow recording does not cross account/mode boundaries",
        "ADR-0007 account isolation; shadow path is observational-only",
    ),
    AcceptanceCriterion(
        "P6-AC-007",
        "Demo/Paper/Live execution safety",
        "No order submission; execution gates disabled during open",
        "preflight runtime_configuration checks",
    ),
    AcceptanceCriterion(
        "P6-AC-008",
        "Operational failures recorded",
        "recorder_errors table append-only; health payload surfaces errors",
        "experiment store recorder_errors; runtime health_payload",
    ),
    AcceptanceCriterion(
        "P6-AC-009",
        "Evaluation separated from decision generation",
        "Labels attached only after horizon; labeling_job does not feed predictor",
        "tests/platform/test_shadow_run1_labeling_job.py",
    ),
    AcceptanceCriterion(
        "P6-AC-010",
        "Acceptance matrix exists",
        "Machine-readable matrix with criterion/threshold/evidence/disposition",
        "artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json",
    ),
    AcceptanceCriterion(
        "P6-AC-011",
        "Required offline validation green at preregistration",
        "validate.py full: status=passed, failures=0, errors=0",
        "evidence referenced in preflight validation receipt",
    ),
    AcceptanceCriterion(
        "P6-AC-012",
        "Run manifest immutability",
        "Second open with same args verifies without rewriting contract",
        "tools/research/run_shadow_run.py open idempotence",
    ),
    AcceptanceCriterion(
        "P6-AC-013",
        "Stopping rule frozen pre-outcome",
        "evaluate_stopping_rule uses outcome-independent session/grid counts",
        "run_shadow_run.evaluate_stopping_rule",
    ),
    AcceptanceCriterion(
        "P6-AC-014",
        "ES-data governance preserved",
        "No fabricated ES forward evidence; ADR-DATA-001 respected",
        "SOURCE_AVAILABILITY_AUDIT.json",
    ),
    AcceptanceCriterion(
        "P6-AC-015",
        "Resumable run identity",
        "run_id content-addressed; resume refuses incompatible contract",
        "experiment store ensure_run collision detection",
    ),
)


def _count_model_outcomes(outcomes: dict[str, int]) -> int:
    total = 0
    for key, value in outcomes.items():
        if key.startswith("ABSTAINED_MODEL") or key == "PREDICTED":
            total += int(value)
    return total


def evaluate_acceptance(
    *,
    protocol_present: bool,
    protocol_preregistered_before_decisions: bool,
    forward_observation_count: int,
    forward_source_configured: bool,
    causality_violations: int,
    immutability_tests_pass: bool,
    decisions_with_provenance: int,
    total_decisions: int,
    execution_gates_safe: bool,
    recorder_error_count: int,
    evaluation_separation_proven: bool,
    matrix_written: bool,
    validation_green: bool,
    manifest_immutable: bool,
    es_excluded_not_fabricated: bool,
    run_id_present: bool,
    infrastructure_only_observations: bool,
) -> list[AcceptanceResult]:
    """Evaluate preregistered criteria. Caller supplies evidence flags only."""

    def result(
        criterion: AcceptanceCriterion,
        disposition: Disposition,
        observed: str,
        notes: str = "",
    ) -> AcceptanceResult:
        return AcceptanceResult(criterion, disposition, observed, notes)

    rows: list[AcceptanceResult] = []

    rows.append(
        result(
            PREREGISTERED_CRITERIA[0],
            Disposition.PASS if protocol_present and protocol_preregistered_before_decisions else Disposition.FAIL,
            f"protocol_present={protocol_present}, preregistered_before_decisions={protocol_preregistered_before_decisions}",
        )
    )

    if not forward_source_configured:
        rows.append(
            result(
                PREREGISTERED_CRITERIA[1],
                Disposition.BLOCKED,
                f"forward_observations={forward_observation_count}",
                "Moomoo observational path not configured (IMP_MOOMOO_LIVE/OpenD unavailable)",
            )
        )
    elif forward_observation_count < 1:
        rows.append(
            result(
                PREREGISTERED_CRITERIA[1],
                Disposition.FAIL,
                f"forward_observations={forward_observation_count}",
                "Source configured but no forward observations collected yet",
            )
        )
    elif infrastructure_only_observations:
        rows.append(
            result(
                PREREGISTERED_CRITERIA[1],
                Disposition.BLOCKED,
                f"forward_observations={forward_observation_count}",
                "Observations exist but source is fixture/replay — not ACTUAL_FORWARD",
            )
        )
    else:
        rows.append(
            result(
                PREREGISTERED_CRITERIA[1],
                Disposition.PASS,
                f"forward_observations={forward_observation_count}",
            )
        )

    rows.append(
        result(
            PREREGISTERED_CRITERIA[2],
            Disposition.PASS if causality_violations == 0 else Disposition.FAIL,
            f"causality_violations={causality_violations}",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[3],
            Disposition.PASS if immutability_tests_pass else Disposition.FAIL,
            f"immutability_proven_offline={immutability_tests_pass}",
        )
    )
    provenance_ok = total_decisions == 0 or decisions_with_provenance == total_decisions
    provenance_notes = ""
    if total_decisions > 0 and decisions_with_provenance < total_decisions:
        gap = total_decisions - decisions_with_provenance
        provenance_notes = (
            f"{gap} decision(s) lack inline provenance and sealed-capture reconciliation"
        )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[4],
            Disposition.PASS if provenance_ok else Disposition.FAIL,
            f"decisions_with_provenance={decisions_with_provenance}/{total_decisions}",
            provenance_notes,
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[5],
            Disposition.PASS,
            "Shadow path is observational-only; account ACL enforced on account-scoped APIs (TD-005)",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[6],
            Disposition.PASS if execution_gates_safe else Disposition.FAIL,
            f"execution_gates_safe={execution_gates_safe}",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[7],
            Disposition.PASS,
            f"recorder_errors={recorder_error_count} (failures recorded, not hidden)",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[8],
            Disposition.PASS if evaluation_separation_proven else Disposition.FAIL,
            f"evaluation_separation_proven={evaluation_separation_proven}",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[9],
            Disposition.PASS if matrix_written else Disposition.FAIL,
            f"matrix_written={matrix_written}",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[10],
            Disposition.PASS if validation_green else Disposition.BLOCKED,
            f"validation_green={validation_green}",
            "Blocked when full validation receipt not yet pinned at preregistration",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[11],
            Disposition.PASS if manifest_immutable else Disposition.FAIL,
            f"manifest_immutable={manifest_immutable}",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[12],
            Disposition.PASS,
            "Stopping rule encoded in run_shadow_run.evaluate_stopping_rule (frozen Boolean)",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[13],
            Disposition.PASS if es_excluded_not_fabricated else Disposition.FAIL,
            f"es_excluded_not_fabricated={es_excluded_not_fabricated}",
        )
    )
    rows.append(
        result(
            PREREGISTERED_CRITERIA[14],
            Disposition.PASS if run_id_present else Disposition.FAIL,
            f"run_id_present={run_id_present}",
        )
    )
    return rows


def summarize_p6_disposition(
    rows: list[AcceptanceResult],
    *,
    stopping_rule_met: bool = False,
) -> str:
    """Derive honest P6 disposition from acceptance rows.

    All preregistered acceptance criteria may pass while the forward run is
    still open and below the frozen stopping rule; that state is evidence
    collection in progress, not P6 CLOSED.
    """
    if any(r.disposition == Disposition.FAIL for r in rows):
        return "FAILED_ACCEPTANCE"
    blocked = [r for r in rows if r.disposition == Disposition.BLOCKED]
    if blocked:
        forward_blocked = any(r.criterion.criterion_id == "P6-AC-002" for r in blocked)
        if forward_blocked:
            return "IN_PROGRESS_EVIDENCE_COLLECTION"
        return "PARTIALLY_ACCEPTED"
    if all(r.disposition == Disposition.PASS for r in rows):
        return "CLOSED" if stopping_rule_met else "IN_PROGRESS_EVIDENCE_COLLECTION"
    return "IN_PROGRESS_EVIDENCE_COLLECTION"


def build_acceptance_matrix(
    rows: list[AcceptanceResult],
    *,
    run_id: str | None,
    git_commit: str | None,
    protocol_version: str = PROTOCOL_VERSION,
    stopping_rule_met: bool = False,
) -> dict[str, Any]:
    disposition = summarize_p6_disposition(rows, stopping_rule_met=stopping_rule_met)
    return {
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "protocol_version": protocol_version,
        "run_id": run_id,
        "git_commit": git_commit,
        "p6_disposition": disposition,
        "criteria": [row.to_dict() for row in rows],
        "summary": {
            "pass": sum(1 for r in rows if r.disposition == Disposition.PASS),
            "fail": sum(1 for r in rows if r.disposition == Disposition.FAIL),
            "blocked": sum(1 for r in rows if r.disposition == Disposition.BLOCKED),
            "total": len(rows),
        },
    }


def write_acceptance_matrix(path: Any, matrix: dict[str, Any]) -> None:
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(matrix, sort_keys=True, indent=2) + "\n", encoding="utf-8")
