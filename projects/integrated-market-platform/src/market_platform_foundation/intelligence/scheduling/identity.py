"""Stable BUILD 10 inference job identities."""

from __future__ import annotations

from ...canonical import canonical_bytes, sha256_bytes

INFERENCE_JOB_IDENTITY_VERSION = "inference-job-sha256-v1"


def derive_inference_job_id(
    *,
    routing_decision_id: str,
    scheduler_policy_identity: str,
    execution_profile_id: str,
) -> str:
    payload = {
        "identity_version": INFERENCE_JOB_IDENTITY_VERSION,
        "schema_version": "1",
        "routing_decision_id": routing_decision_id,
        "scheduler_policy_identity": scheduler_policy_identity,
        "execution_profile_id": execution_profile_id,
    }
    return f"IJOB-{sha256_bytes(canonical_bytes(payload))}"


def derive_dispatch_batch_id(*, job_ids: tuple[str, ...], scheduler_policy_identity: str) -> str:
    payload = {
        "identity_version": "inference-dispatch-batch-sha256-v1",
        "scheduler_policy_identity": scheduler_policy_identity,
        "job_ids": sorted(job_ids),
    }
    return f"DBATCH-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "INFERENCE_JOB_IDENTITY_VERSION",
    "derive_dispatch_batch_id",
    "derive_inference_job_id",
]
