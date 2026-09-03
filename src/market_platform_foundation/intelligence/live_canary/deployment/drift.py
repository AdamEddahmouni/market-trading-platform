"""Configuration and artifact drift assessment (BUILD 34)."""

from __future__ import annotations

from .identity import derive_drift_assessment_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    ConfigurationDriftAssessmentV1,
    DriftClassification,
)


def assess_configuration_drift(
    *,
    expected_release: str,
    expected_config_hash: str,
    observed_release: str,
    observed_config_hash: str,
) -> ConfigurationDriftAssessmentV1:
    if expected_release != observed_release:
        classification = DriftClassification.ARTIFACT_MISMATCH.value
        blocking = True
    elif expected_config_hash != observed_config_hash:
        classification = DriftClassification.CRITICAL.value
        blocking = True
    else:
        classification = DriftClassification.NONE.value
        blocking = False

    assessment = ConfigurationDriftAssessmentV1(
        drift_assessment_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        expected_release=expected_release,
        expected_config_hash=expected_config_hash,
        observed_release=observed_release,
        observed_config=observed_config_hash,
        drift_classification=classification,
        blocking_impact=blocking,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return ConfigurationDriftAssessmentV1(
        drift_assessment_id=derive_drift_assessment_id(assessment),
        schema_version=assessment.schema_version,
        expected_release=assessment.expected_release,
        expected_config_hash=assessment.expected_config_hash,
        observed_release=assessment.observed_release,
        observed_config=assessment.observed_config,
        drift_classification=assessment.drift_classification,
        blocking_impact=assessment.blocking_impact,
        implementation_version=assessment.implementation_version,
        metadata=assessment.metadata,
    )


def drift_blocks_live_actions(assessment: ConfigurationDriftAssessmentV1) -> bool:
    return assessment.blocking_impact and assessment.drift_classification in (
        DriftClassification.CRITICAL.value,
        DriftClassification.ARTIFACT_MISMATCH.value,
    )
