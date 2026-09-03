"""Build MRA-002 Anthropic assistant acceptance evidence."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/mra002/assertion-predicates.json"
EVALUATED_AT = "2026-08-18T18:30:00.000000000Z"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.assistant.anthropic_inference import AnthropicInference, extract_citation_refs
from market_platform_foundation.assistant.context_assembler import build_evidence_context
from market_platform_foundation.assistant.grounded_inference import GroundedEvidenceInference
from market_platform_foundation.assistant.service import AssistantResearchService
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes, write_canonical_json
from market_platform_foundation.mra002_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.ui_api.store import ReplayStore


def _load_store() -> ReplayStore:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    return store


def _mock_anthropic_payload(text: str) -> bytes:
    payload = {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 120, "output_tokens": 40},
    }
    return json.dumps(payload).encode("utf-8")


def _anthropic_mocked_answer_report(store: ReplayStore) -> dict[str, object]:
    evidence_context = build_evidence_context(store)
    failures: list[str] = []
    provider_id = ""
    citation_refs: list[str] = []
    with patch("market_platform_foundation.assistant.anthropic_inference.urlopen") as mock_urlopen:
        mock_response = io.BytesIO(
            _mock_anthropic_payload("BIYA is on the admitted fixture [explain:disclosure:BIYA].")
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response
        inference = AnthropicInference(api_key="mra002-evidence-key", model="claude-test")
        outcome = inference.infer("Why is BIYA here?", evidence_context=evidence_context)
    provider_id = outcome.provider_id
    citation_refs = [row.get("ref", "") for row in outcome.citations]
    if outcome.abstained:
        failures.append("MRA2_001_ABSTAINED")
    if provider_id != AnthropicInference.provider_id:
        failures.append("MRA2_001_PROVIDER_MISMATCH")
    if "explain:disclosure:BIYA" not in citation_refs:
        failures.append("MRA2_001_NO_CITATION")
    return {
        "artifact_type": "MRA002_ANTHROPIC_MOCKED_ANSWER_REPORT",
        "citation_refs": citation_refs,
        "failures": sorted(set(failures)),
        "logical_id": "mra002.anthropic_mocked_answer_report",
        "provider_id": provider_id,
        "status": "PASS" if not failures else "FAIL",
    }


def _api_key_abstention_report() -> dict[str, object]:
    inference = AnthropicInference(api_key="")
    outcome = inference.infer("Why is BIYA here?", evidence_context={"resolve_explain": lambda _ref: {}})
    failures: list[str] = []
    if not outcome.abstained:
        failures.append("MRA2_002_DID_NOT_ABSTAIN")
    if outcome.abstention_reason != "API_KEY_MISSING":
        failures.append("MRA2_002_REASON_MISMATCH")
    return {
        "abstention_reason": outcome.abstention_reason,
        "artifact_type": "MRA002_API_KEY_ABSTENTION_REPORT",
        "failures": sorted(set(failures)),
        "logical_id": "mra002.api_key_abstention_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _grounded_fallback_report(store: ReplayStore) -> dict[str, object]:
    evidence_context = build_evidence_context(store)
    failures: list[str] = []
    with patch("market_platform_foundation.assistant.anthropic_inference.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = ConnectionError("network down")
        inference = AnthropicInference(api_key="mra002-evidence-key", model="claude-test")
        outcome = inference.infer("Why is BIYA here?", evidence_context=evidence_context)
    if outcome.abstained:
        failures.append("MRA2_003_FALLBACK_ABSTAINED")
    if outcome.provider_id != GroundedEvidenceInference.provider_id:
        failures.append("MRA2_003_PROVIDER_MISMATCH")
    return {
        "artifact_type": "MRA002_GROUNDED_FALLBACK_REPORT",
        "failures": sorted(set(failures)),
        "logical_id": "mra002.grounded_fallback_report",
        "provider_id": outcome.provider_id,
        "status": "PASS" if not failures else "FAIL",
    }


def _authority_boundary_report(output_dir: Path) -> dict[str, object]:
    from market_platform_foundation.assistant.audit_store import AssistantAuditStore

    audit_root = output_dir / ".audit-boundary-check"
    service = AssistantResearchService(
        AssistantAuditStore(audit_root),
        inference=AnthropicInference(api_key="mra002-evidence-key", model="claude-test"),
    )
    status = service.build_status()
    failures: list[str] = []
    if status.get("authority_boundary") != "READ_ONLY_NO_EXECUTION":
        failures.append("MRA2_004_BOUNDARY_MISMATCH")
    if status.get("provider_id") != AnthropicInference.provider_id:
        failures.append("MRA2_004_PROVIDER_MISMATCH")
    return {
        "artifact_type": "MRA002_AUTHORITY_BOUNDARY_REPORT",
        "authority_boundary": status.get("authority_boundary"),
        "failures": sorted(set(failures)),
        "logical_id": "mra002.authority_boundary_report",
        "provider_id": status.get("provider_id"),
        "status": "PASS" if not failures else "FAIL",
    }


def _citation_filter_report() -> dict[str, object]:
    allowed = {"explain:quality:system", "explain:disclosure:BIYA"}
    refs = extract_citation_refs(
        "Quality [explain:quality:system] and fake [explain:forged:ZZZZ] plus [explain:disclosure:BIYA].",
        allowed,
    )
    failures: list[str] = []
    if "explain:forged:ZZZZ" in refs:
        failures.append("MRA2_005_FORGED_REF_LEAKED")
    if set(refs) != {"explain:quality:system", "explain:disclosure:BIYA"}:
        failures.append("MRA2_005_FILTER_MISMATCH")
    return {
        "artifact_type": "MRA002_CITATION_FILTER_REPORT",
        "citation_refs": list(refs),
        "failures": sorted(set(failures)),
        "logical_id": "mra002.citation_filter_report",
        "status": "PASS" if not failures else "FAIL",
    }


def build_evidence(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    store = _load_store()

    mocked = _anthropic_mocked_answer_report(store)
    abstention = _api_key_abstention_report()
    fallback = _grounded_fallback_report(store)
    boundary = _authority_boundary_report(output_dir)
    citation_filter = _citation_filter_report()

    write_canonical_json(output_dir / "anthropic-mocked-answer-report.json", mocked)
    write_canonical_json(output_dir / "missing-key-abstention-report.json", abstention)
    write_canonical_json(output_dir / "grounded-fallback-report.json", fallback)
    write_canonical_json(output_dir / "authority-boundary-report.json", boundary)
    write_canonical_json(output_dir / "citation-filter-report.json", citation_filter)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "MRA2-001": {
            "failures": mocked.get("failures"),
            "reason_codes": mocked.get("failures", []),
            "status": mocked.get("status"),
        },
        "MRA2-002": {
            "failures": abstention.get("failures"),
            "reason_codes": abstention.get("failures", []),
            "status": abstention.get("status"),
        },
        "MRA2-003": {
            "failures": fallback.get("failures"),
            "reason_codes": fallback.get("failures", []),
            "status": fallback.get("status"),
        },
        "MRA2-004": {
            "failures": boundary.get("failures"),
            "reason_codes": boundary.get("failures", []),
            "status": boundary.get("status"),
        },
        "MRA2-005": {
            "failures": citation_filter.get("failures"),
            "reason_codes": citation_filter.get("failures", []),
            "status": citation_filter.get("status"),
        },
    }

    members = {
        "mra002.anthropic_mocked_answer_report": "anthropic-mocked-answer-report.json",
        "mra002.api_key_abstention_report": "missing-key-abstention-report.json",
        "mra002.grounded_fallback_report": "grounded-fallback-report.json",
        "mra002.authority_boundary_report": "authority-boundary-report.json",
        "mra002.citation_filter_report": "citation-filter-report.json",
    }
    selected_evidence = []
    for logical_id, filename in sorted(members.items()):
        path = output_dir / filename
        digest = sha256_bytes(path.read_bytes())
        selected_evidence.append({"logical_id": logical_id, "sha256": digest})

    manifest_inputs = {
        "active_keys": registry["active_keys"],
        "assertion_observations": observations,
        "evaluated_at": EVALUATED_AT,
        "selected_evidence": selected_evidence,
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "mra002", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["mra002.run_mra002_pipeline/1.0.0"],
    }
    run_id = create_run_manifest(output_dir / "assertion-run-manifest.json", manifest_inputs)
    results = evaluate_run(output_dir / "assertion-run-manifest.json", output_dir)
    aggregate = aggregate_status(results)
    write_canonical_json(
        output_dir / "assertion-aggregate.json",
        {"aggregate_status": aggregate, "results": [row["assertion_id"] for row in results], "run_id": run_id},
    )

    bundle_members = {
        **members,
        "mra002.assertion_aggregate": "assertion-aggregate.json",
        "mra002.assertion_registry": "assertion_registry.json",
        "mra002.assertion_results": "assertion-results.json",
        "mra002.assertion_run_manifest": "assertion-run-manifest.json",
    }
    candidate_members = []
    for logical_id, filename in sorted(bundle_members.items()):
        path = output_dir / filename
        candidate_members.append(
            {
                "logical_id": logical_id,
                "repository_relative_path": str(path.relative_to(ROOT).as_posix()),
                "sha256": sha256_bytes(path.read_bytes()),
            }
        )
    candidate_body = {
        "candidate_evidence_root": sha256_bytes(canonical_bytes(candidate_members)),
        "index_members": candidate_members,
        "logical_id": "mra002.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "output_dir": str(output_dir),
        "run_id": run_id,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="Build acceptance evidence to directory")
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    report = build_evidence(Path(args.output_dir).resolve())
    print(report)
    return 0 if report["aggregate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
