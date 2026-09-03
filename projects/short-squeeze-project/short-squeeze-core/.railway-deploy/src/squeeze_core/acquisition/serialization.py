from pydantic import BaseModel

from squeeze_core.serialization import canonical_json_bytes

from .models import AcquisitionBatch, AcquisitionPlan, ArtifactManifest, SourceManifest


def serialize_acquisition_model(value: BaseModel) -> bytes:
    return canonical_json_bytes(value)


def deserialize_acquisition_plan(value: bytes | str) -> AcquisitionPlan:
    return AcquisitionPlan.model_validate_json(value)


def deserialize_source_manifest(value: bytes | str) -> SourceManifest:
    return SourceManifest.model_validate_json(value)


def deserialize_artifact_manifest(value: bytes | str) -> ArtifactManifest:
    return ArtifactManifest.model_validate_json(value)


def deserialize_acquisition_batch(value: bytes | str) -> AcquisitionBatch:
    return AcquisitionBatch.model_validate_json(value)


__all__ = [
    "deserialize_acquisition_batch", "deserialize_acquisition_plan",
    "deserialize_artifact_manifest", "deserialize_source_manifest",
    "serialize_acquisition_model",
]
