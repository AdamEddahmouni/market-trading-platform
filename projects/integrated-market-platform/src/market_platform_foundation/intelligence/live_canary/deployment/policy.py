"""Default deployment policy builders (BUILD 34)."""

from __future__ import annotations

from .types import BUILD34_KNOWN_LIMITATIONS

BUILD33_HEAD = "16bf0f3e854e99ac2e992d8c7245b8f1742979b9"


def build_default_deployment_policy_refs() -> dict[str, str]:
    return {
        "build33_source_ref": BUILD33_HEAD,
        "build33_qualification_ref": "BUILD33-SUPERVISED-PRODUCTION-PILOT-QUALIFIED",
        "pilot_policy_ref": "PILPOL-default",
        "slo_policy_ref": "SLO-default",
    }
