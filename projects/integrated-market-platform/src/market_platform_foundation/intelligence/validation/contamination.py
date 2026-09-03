"""Contamination ledger and overlap detection (BUILD 19)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.types import ResearchKnowledgeFootprint
from ..training.types import TrainingDatasetManifestV1
from .identity import derive_contamination_record_id
from .types import (
    ContaminationDisposition,
    ContaminationRecordV1,
    ContaminationType,
    HoldoutSpec,
)


@dataclass
class ContaminationLedger:
    """Append-only contamination history."""

    records: list[ContaminationRecordV1] = field(default_factory=list)

    def append(self, record: ContaminationRecordV1) -> None:
        for existing in self.records:
            if existing.contamination_record_id == record.contamination_record_id:
                return
        self.records.append(record)

    @property
    def disposition(self) -> ContaminationDisposition:
        if not self.records:
            return ContaminationDisposition.CLEAN
        if any(r.disposition == ContaminationDisposition.UNKNOWN for r in self.records):
            return ContaminationDisposition.UNKNOWN
        if any(r.disposition == ContaminationDisposition.CONTAMINATED for r in self.records):
            return ContaminationDisposition.CONTAMINATED
        return ContaminationDisposition.CLEAN


def _ranges_overlap(
    a_start: int | None,
    a_end: int | None,
    b_start: int,
    b_end: int,
) -> bool:
    if a_start is None or a_end is None:
        return False
    return a_start < b_end and b_start < a_end


def check_research_knowledge_overlap(
    footprint: ResearchKnowledgeFootprint,
    holdout: HoldoutSpec,
    *,
    validation_plan_id: str,
    experiment_id: str,
) -> ContaminationRecordV1 | None:
    if _ranges_overlap(
        footprint.decision_start_ns,
        footprint.decision_end_ns,
        holdout.holdout_start_ns,
        holdout.holdout_end_ns,
    ):
        record_id = derive_contamination_record_id(
            validation_plan_id=validation_plan_id,
            contamination_type=ContaminationType.DEVELOPMENT_EVALUATION_OVERLAP.value,
            source_ref="research_knowledge_footprint",
            affected_decision_start_ns=holdout.holdout_start_ns,
            affected_decision_end_ns=holdout.holdout_end_ns,
        )
        return ContaminationRecordV1(
            contamination_record_id=record_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            experiment_id=experiment_id,
            validation_plan_id=validation_plan_id,
            holdout_commitment_id=None,
            contamination_type=ContaminationType.DEVELOPMENT_EVALUATION_OVERLAP,
            disposition=ContaminationDisposition.CONTAMINATED,
            source_ref="research_knowledge_footprint",
            affected_decision_start_ns=holdout.holdout_start_ns,
            affected_decision_end_ns=holdout.holdout_end_ns,
            detected_context="research_footprint_decision_range_overlap",
        )
    return None


def check_training_overlap(
    dataset: TrainingDatasetManifestV1,
    holdout: HoldoutSpec,
    *,
    validation_plan_id: str,
    experiment_id: str,
) -> ContaminationRecordV1 | None:
    overlapping_refs: list[str] = []
    for ref in dataset.example_refs:
        if holdout.holdout_start_ns <= ref.decision_time_ns < holdout.holdout_end_ns:
            overlapping_refs.append(ref.snapshot_id)
    if not overlapping_refs:
        return None
    record_id = derive_contamination_record_id(
        validation_plan_id=validation_plan_id,
        contamination_type=ContaminationType.TRAINING_DATA_OVERLAP.value,
        source_ref=dataset.training_dataset_id,
        affected_decision_start_ns=holdout.holdout_start_ns,
        affected_decision_end_ns=holdout.holdout_end_ns,
    )
    return ContaminationRecordV1(
        contamination_record_id=record_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        experiment_id=experiment_id,
        validation_plan_id=validation_plan_id,
        holdout_commitment_id=None,
        contamination_type=ContaminationType.TRAINING_DATA_OVERLAP,
        disposition=ContaminationDisposition.CONTAMINATED,
        source_ref=dataset.training_dataset_id,
        affected_decision_start_ns=holdout.holdout_start_ns,
        affected_decision_end_ns=holdout.holdout_end_ns,
        affected_artifact_refs=tuple(sorted(overlapping_refs)),
        detected_context="training_example_in_holdout_range",
    )


def check_prior_holdout_access(
    *,
    validation_plan_id: str,
    experiment_id: str,
    prior_access_recorded: bool,
    holdout: HoldoutSpec,
) -> ContaminationRecordV1 | None:
    if not prior_access_recorded:
        return None
    record_id = derive_contamination_record_id(
        validation_plan_id=validation_plan_id,
        contamination_type=ContaminationType.PRIOR_HOLDOUT_ACCESS.value,
        source_ref="prior_holdout_access",
        affected_decision_start_ns=holdout.holdout_start_ns,
        affected_decision_end_ns=holdout.holdout_end_ns,
    )
    return ContaminationRecordV1(
        contamination_record_id=record_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        experiment_id=experiment_id,
        validation_plan_id=validation_plan_id,
        holdout_commitment_id=None,
        contamination_type=ContaminationType.PRIOR_HOLDOUT_ACCESS,
        disposition=ContaminationDisposition.CONTAMINATED,
        source_ref="prior_holdout_access",
        affected_decision_start_ns=holdout.holdout_start_ns,
        affected_decision_end_ns=holdout.holdout_end_ns,
        detected_context="prior_holdout_unlock_before_candidate_freeze",
    )


def assess_holdout_contamination(
    *,
    footprint: ResearchKnowledgeFootprint,
    training_dataset: TrainingDatasetManifestV1 | None,
    holdout: HoldoutSpec,
    validation_plan_id: str,
    experiment_id: str,
    prior_holdout_access: bool = False,
    provenance_complete: bool = True,
) -> ContaminationLedger:
    ledger = ContaminationLedger()
    if not provenance_complete:
        record_id = derive_contamination_record_id(
            validation_plan_id=validation_plan_id,
            contamination_type=ContaminationType.UNKNOWN_MODEL_KNOWLEDGE.value,
            source_ref="insufficient_provenance",
            affected_decision_start_ns=holdout.holdout_start_ns,
            affected_decision_end_ns=holdout.holdout_end_ns,
        )
        ledger.append(
            ContaminationRecordV1(
                contamination_record_id=record_id,
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                experiment_id=experiment_id,
                validation_plan_id=validation_plan_id,
                holdout_commitment_id=None,
                contamination_type=ContaminationType.UNKNOWN_MODEL_KNOWLEDGE,
                disposition=ContaminationDisposition.UNKNOWN,
                source_ref="insufficient_provenance",
                affected_decision_start_ns=holdout.holdout_start_ns,
                affected_decision_end_ns=holdout.holdout_end_ns,
                detected_context="unknown_overlap_provenance",
            )
        )
        return ledger

    research_record = check_research_knowledge_overlap(
        footprint, holdout, validation_plan_id=validation_plan_id, experiment_id=experiment_id
    )
    if research_record is not None:
        ledger.append(research_record)

    if training_dataset is not None:
        training_record = check_training_overlap(
            training_dataset,
            holdout,
            validation_plan_id=validation_plan_id,
            experiment_id=experiment_id,
        )
        if training_record is not None:
            ledger.append(training_record)

    prior_record = check_prior_holdout_access(
        validation_plan_id=validation_plan_id,
        experiment_id=experiment_id,
        prior_access_recorded=prior_holdout_access,
        holdout=holdout,
    )
    if prior_record is not None:
        ledger.append(prior_record)

    return ledger


__all__ = [
    "ContaminationLedger",
    "assess_holdout_contamination",
    "check_prior_holdout_access",
    "check_research_knowledge_overlap",
    "check_training_overlap",
]
