"""Baseline training dataset types and hygiene (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import ForecastTarget
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from .errors import BaselineTrainingError
from .features import BaselineFeatureSchema, FeatureVectorBuilder
from .identity import derive_dataset_fingerprint
from .types import BaselineClassLabel, BaselineFeatureVector


@dataclass(frozen=True, slots=True)
class BaselineTrainingExample:
    snapshot_id: str
    decision_time_ns: int
    feature_vector: BaselineFeatureVector
    label: BaselineClassLabel
    label_available_time_ns: int
    source_signal_refs: tuple[str, ...] = ()
    regime_key: str | None = None
    label_provenance: str | None = None


@dataclass(frozen=True, slots=True)
class BaselineTrainingDataset:
    examples: tuple[BaselineTrainingExample, ...]
    feature_schema: BaselineFeatureSchema
    target: ForecastTarget
    training_cutoff_ns: int
    allow_degraded_training_examples: bool = False

    @property
    def fingerprint(self) -> str:
        canonical_examples = []
        for example in self.examples:
            canonical_examples.append(
                {
                    "snapshot_id": example.snapshot_id,
                    "decision_time_ns": example.decision_time_ns,
                    "feature_values": list(example.feature_vector.values),
                    "feature_keys": list(example.feature_vector.feature_keys),
                    "label": example.label.value,
                    "label_available_time_ns": example.label_available_time_ns,
                    "regime_key": example.regime_key,
                }
            )
        return derive_dataset_fingerprint(
            feature_schema_fingerprint_value=self.feature_schema.fingerprint,
            target=self.target,
            training_cutoff_ns=self.training_cutoff_ns,
            examples=canonical_examples,
        )


def _example_identity_key(
    snapshot_id: str,
    target: ForecastTarget,
    decision_time_ns: int,
) -> tuple[str, str, int]:
    return (snapshot_id, target.target_kind, decision_time_ns)


def build_training_example(
    *,
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...] | list[SignalV1],
    schema: BaselineFeatureSchema,
    label: BaselineClassLabel,
    label_available_time_ns: int,
    allow_degraded: bool = False,
    regime_key: str | None = None,
) -> BaselineTrainingExample:
    vector, diagnostics = FeatureVectorBuilder(schema).extract(
        snapshot,
        signals,
        allow_degraded=allow_degraded,
    )
    if vector is None:
        codes = ", ".join(item.code.value for item in diagnostics)
        raise BaselineTrainingError(
            f"TRAINING_FEATURE_EXTRACTION_FAILED:{codes}",
            details={"diagnostics": [item.code.value for item in diagnostics]},
        )
    return BaselineTrainingExample(
        snapshot_id=snapshot.snapshot_id,
        decision_time_ns=snapshot.decision_time_ns,
        feature_vector=vector,
        label=label,
        label_available_time_ns=label_available_time_ns,
        source_signal_refs=tuple(signal.signal_id for signal in vector.source_signals),
        regime_key=regime_key,
    )


def build_training_dataset(
    *,
    raw_examples: list[BaselineTrainingExample],
    feature_schema: BaselineFeatureSchema,
    target: ForecastTarget,
    training_cutoff_ns: int,
    allow_degraded_training_examples: bool = False,
) -> BaselineTrainingDataset:
    if not raw_examples:
        raise BaselineTrainingError("TRAINING_DATASET_EMPTY")

    seen: dict[tuple[str, str, int], BaselineClassLabel] = {}
    canonical: list[BaselineTrainingExample] = []

    for example in raw_examples:
        if example.label_available_time_ns > training_cutoff_ns:
            raise BaselineTrainingError(
                "FUTURE_LABEL_REJECTED",
                details={
                    "snapshot_id": example.snapshot_id,
                    "label_available_time_ns": example.label_available_time_ns,
                    "training_cutoff_ns": training_cutoff_ns,
                },
            )
        identity = _example_identity_key(example.snapshot_id, target, example.decision_time_ns)
        if identity in seen:
            if seen[identity] != example.label:
                raise BaselineTrainingError(
                    "CONFLICTING_TRAINING_LABELS",
                    details={"snapshot_id": example.snapshot_id},
                )
            continue
        seen[identity] = example.label
        canonical.append(example)

    canonical.sort(key=lambda row: (row.decision_time_ns, row.snapshot_id))

    return BaselineTrainingDataset(
        examples=tuple(canonical),
        feature_schema=feature_schema,
        target=target,
        training_cutoff_ns=training_cutoff_ns,
        allow_degraded_training_examples=allow_degraded_training_examples,
    )


__all__ = [
    "BaselineTrainingDataset",
    "BaselineTrainingExample",
    "build_training_dataset",
    "build_training_example",
]
