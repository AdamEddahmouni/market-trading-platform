"""Direct-path authority audits (BUILD 35)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]

PROHIBITED_PATTERNS = (
    r"broker\.submit\s*\(",
    r"place_order\s*\(",
    r"submit_order\s*\(",
    r"force_promote",
    r"force_live",
    r"skip_reconciliation",
    r"ignore_risk",
    r"auto_confirm",
    r"auto_authorize",
)

# Modules allowed to contain broker submit (behind authority gates)
BROKER_ADAPTER_ALLOWLIST = frozenset(
    {
        "src/market_platform_foundation/intelligence/broker",
        "src/market_platform_foundation/intelligence/live_canary",
        "src/market_platform_foundation/intelligence/execution",
        "tests/",
    }
)

FORECAST_BROKER_FORBIDDEN = (
    "src/market_platform_foundation/intelligence/forecast",
)

RESEARCH_ACTIVE_MODEL_FORBIDDEN = (
    "src/market_platform_foundation/intelligence/research",
)


def _scan_paths(
    patterns: tuple[str, ...],
    *,
    include_roots: tuple[str, ...],
    exclude_tests: bool = False,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for root_rel in include_roots:
        root = ROOT / root_rel
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if exclude_tests and "/tests/" in str(path).replace("\\", "/"):
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if any(rel.startswith(allowed) for allowed in BROKER_ADAPTER_ALLOWLIST):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern in patterns:
                if re.search(pattern, content):
                    findings.append({"path": rel, "pattern": pattern})
    return findings


def audit_direct_forecast_to_broker() -> list[dict[str, str]]:
    return _scan_paths(PROHIBITED_PATTERNS, include_roots=FORECAST_BROKER_FORBIDDEN)


def audit_direct_llm_to_broker() -> list[dict[str, str]]:
    return _scan_paths(
        PROHIBITED_PATTERNS,
        include_roots=("src/market_platform_foundation/intelligence/specialists",),
    )


def audit_direct_research_to_active_model() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for root_rel in RESEARCH_ACTIVE_MODEL_FORBIDDEN:
        root = ROOT / root_rel
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(r"activate.*model|set_champion|force_promote", content, re.IGNORECASE):
                rel = str(path.relative_to(ROOT)).replace("\\", "/")
                if "promotion" not in rel and "validation" not in rel:
                    findings.append({"path": rel, "pattern": "direct_active_model_mutation"})
    return findings


def audit_deployment_to_live_authorization() -> list[dict[str, str]]:
    from market_platform_foundation.intelligence.live_canary.deployment.plan import (
        build_deployment_record,
        deployment_grants_live_authority,
    )

    record = build_deployment_record(
        environment_ref="ENV-fixture",
        release_ref="REL-fixture",
        deployment_started_ns=0,
        configuration_hash="abc",
        artifact_hashes={"bundle_content": "hash"},
        deployment_completed_ns=1,
    )
    if deployment_grants_live_authority(record):
        return [{"path": "deployment/plan.py", "pattern": "deployment_grants_live_authority"}]
    return []


def audit_release_approval_to_order_confirmation() -> list[dict[str, str]]:
    from .approval import approval_confirms_order

    if approval_confirms_order():
        return [{"path": "release_governance/approval.py", "pattern": "approval_confirms_order"}]
    return []
