"""Generate EVIDENCE-01 forward evidence qualification artifacts."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.git_ref import read_git_head
from market_platform_foundation.intelligence.forward_qualification import (
    assess_forward_evidence_qualification,
    build_forward_evidence_qualification_policy,
    build_forward_evidence_qualification_report,
    forward_evidence_assessment_v1_to_dict,
    forward_evidence_policy_v1_to_dict,
    forward_evidence_report_v1_to_dict,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

ARTIFACT_DIR = ROOT / "artifacts" / "forward-qualification"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    head = read_git_head() or ""
    policy = build_forward_evidence_qualification_policy()
    repo = InMemoryIntelligenceRepository()
    observation_cutoff_ns = 1_700_000_000_000_000_000
    settlement_cutoff_ns = observation_cutoff_ns
    assessment = assess_forward_evidence_qualification(
        policy=policy,
        observations=(),
        repository=repo,
        observation_cutoff_ns=observation_cutoff_ns,
        settlement_cutoff_ns=settlement_cutoff_ns,
    )
    report = build_forward_evidence_qualification_report(policy=policy, assessment=assessment)

    policy_path = ARTIFACT_DIR / "EVIDENCE01_POLICY.json"
    assessment_path = ARTIFACT_DIR / "EVIDENCE01_ASSESSMENT.json"
    report_path = ARTIFACT_DIR / "EVIDENCE01_REPORT.json"
    limitations_path = ARTIFACT_DIR / "EVIDENCE01_KNOWN_LIMITATIONS.md"
    source_manifest_path = ARTIFACT_DIR / "EVIDENCE01_SOURCE_MANIFEST.json"

    policy_path.write_text(json.dumps(forward_evidence_policy_v1_to_dict(policy), indent=2), encoding="utf-8")
    assessment_path.write_text(
        json.dumps(forward_evidence_assessment_v1_to_dict(assessment), indent=2),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                **forward_evidence_report_v1_to_dict(report),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_head": head,
                "mechanism_status": "MECHANISM_VALIDATED_BY_FIXTURE",
                "forward_evidence_status": "FORWARD_EVIDENCE_OBSERVED"
                if assessment.observation_summary.eligible_predictions > 0
                else "INSUFFICIENT_FORWARD_OBSERVATION",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    limitations_path.write_text(
        "\n".join(
            [
                "# EVIDENCE-01 Known Limitations",
                "",
                "## KL-E01-001 — Forward observation accumulation in progress",
                "",
                "- **Scope:** Longer forward evidence qualification",
                "- **Why it exists:** EVIDENCE-01 policy requires materially more observation than BUILD 26",
                f"- **Current disposition:** {report.evidence01_disposition.value}",
                f"- **Limitation status:** {report.limitation_status}",
                "- **Blocking:** no",
                "",
            ]
            + [f"- {item}" for item in report.remaining_requirements]
            if report.remaining_requirements
            else ["- No remaining requirements computed (empty observation set)."],
        ),
        encoding="utf-8",
    )
    source_manifest = {
        "schema_version": "1",
        "milestone": "EVIDENCE-01",
        "source_head": head,
        "policy_ref": policy.policy_id,
        "assessment_ref": assessment.assessment_id,
        "report_ref": report.report_id,
        "build26_historical_report_ref": report.build26_historical_report_ref,
        "observation_cutoff_ns": observation_cutoff_ns,
        "settlement_cutoff_ns": settlement_cutoff_ns,
        "source_evidence_fingerprint": assessment.source_evidence_fingerprint,
        "policy_path": "artifacts/forward-qualification/EVIDENCE01_POLICY.json",
        "assessment_path": "artifacts/forward-qualification/EVIDENCE01_ASSESSMENT.json",
        "report_path": "artifacts/forward-qualification/EVIDENCE01_REPORT.json",
        "limitations_path": "artifacts/forward-qualification/EVIDENCE01_KNOWN_LIMITATIONS.md",
    }
    source_manifest_path.write_text(json.dumps(source_manifest, indent=2), encoding="utf-8")

    hash_manifest = {
        path.name: _sha256_file(path)
        for path in (
            policy_path,
            assessment_path,
            report_path,
            limitations_path,
            source_manifest_path,
        )
    }
    (ARTIFACT_DIR / "EVIDENCE01_FILE_HASHES.json").write_text(
        json.dumps(hash_manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(source_manifest, indent=2))


if __name__ == "__main__":
    main()
