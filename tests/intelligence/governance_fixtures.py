"""Shared fixtures for BUILD 23 governance tests."""

from __future__ import annotations

from market_platform_foundation.intelligence.governance import (
    ActivationEngine,
    FeatureReferenceDistributionV1,
    MonitoringWindowV1,
    RuntimeReportedIdentityV1,
    build_activation_policy,
    build_drift_policy,
    build_fail_safe_policy,
    build_rollback_policy,
)
from market_platform_foundation.intelligence.promotion import PromotionEngine
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE, validated_candidate_bundle
from tests.intelligence.outcome_fixtures import T, HORIZON_5M


def default_activation_policy(**overrides):
    kwargs = {"champion_scope": DEFAULT_SCOPE}
    kwargs.update(overrides)
    return build_activation_policy(**kwargs)


def default_drift_policy(**overrides):
    kwargs = {"champion_scope": DEFAULT_SCOPE, "minimum_sample": 4}
    kwargs.update(overrides)
    return build_drift_policy(**kwargs)


def default_fail_safe_policy(**overrides):
    kwargs = {"champion_scope": DEFAULT_SCOPE}
    kwargs.update(overrides)
    return build_fail_safe_policy(**kwargs)


def default_rollback_policy(**overrides):
    kwargs = {"champion_scope": DEFAULT_SCOPE}
    kwargs.update(overrides)
    return build_rollback_policy(**kwargs)


def monitoring_window(*, start_ns: int | None = None, end_ns: int | None = None) -> MonitoringWindowV1:
    start = start_ns if start_ns is not None else T
    end = end_ns if end_ns is not None else T + HORIZON_5M
    return MonitoringWindowV1(start_ns=start, end_ns=end, evaluation_as_of_ns=end)


def feature_reference(*, fingerprint: str = "schema-v1") -> FeatureReferenceDistributionV1:
    return FeatureReferenceDistributionV1(
        reference_id="ref-fixture",
        schema_version="1",
        feature_schema_fingerprint=fingerprint,
        feature_means={"f1": 0.0, "f2": 1.0},
        feature_stds={"f1": 1.0, "f2": 1.0},
        feature_missingness_rates={"f1": 0.0, "f2": 0.0},
        sample_count=100,
    )


def activated_champion_bundle():
    repo, manifest, candidate, artifact_bytes, report, plan = validated_candidate_bundle()
    promotion_engine = PromotionEngine()
    champion = promotion_engine.bootstrap_champion(
        champion_scope=DEFAULT_SCOPE,
        candidate=candidate,
        effective_from_ns=T,
    )
    repo.put_champion_assignment(champion)
    activation_policy = default_activation_policy()
    activation = ActivationEngine().create_activation(
        policy=activation_policy,
        champion_assignment=champion,
        effective_from_ns=T,
        artifact_bytes=artifact_bytes,
    )
    return repo, champion, candidate, artifact_bytes, activation_policy, activation


def matching_runtime_identity(activation) -> RuntimeReportedIdentityV1:
    return RuntimeReportedIdentityV1(
        candidate_id=activation.candidate_id,
        candidate_artifact_hash=activation.candidate_artifact_hash,
        policy_stack_hash=activation.activation_policy_id,
    )
