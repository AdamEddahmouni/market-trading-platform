"""Build MRA-001 grounded assistant acceptance evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/mra001/assertion-predicates.json"
EVALUATED_AT = "2026-08-18T16:50:00.000000000Z"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.assistant.grounded_inference import GroundedEvidenceInference
from market_platform_foundation.assistant.service import AssistantResearchService
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes, write_canonical_json
from market_platform_foundation.mra001_assertions import aggregate_status, build_registry, create_run_manifest, evaluate_run
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.ui_api.assistant_projections import build_assistant_status, submit_assistant_prompt
from market_platform_foundation.ui_api.projections import build_explain_payload, build_inspect_payload
from market_platform_foundation.ui_api.store import TRACKED_ASSISTANT_AUDIT_ROOT, ReplayStore


def _load_store(audit_root: Path | None = None) -> ReplayStore:
    store = ReplayStore(
        collection_root=COLLECTION_ROOT,
        assistant_audit_root=audit_root if audit_root is not None else TRACKED_ASSISTANT_AUDIT_ROOT,
    )
    store.load()
    return store


def _grounded_answer_report(store: ReplayStore) -> dict[str, object]:
    service = store.assistant_service
    conversation = service.create_conversation("MRA-001 evidence")
    result = submit_assistant_prompt(store, conversation["conversation_id"], "Why is BIYA here?")
    assistant = result["assistant_message"]
    provenance = assistant.get("provenance", {})
    abstained = bool(provenance.get("abstained"))
    content = str(assistant.get("content", ""))
    failures: list[str] = []
    if abstained:
        failures.append("MRA001_STILL_ABSTAINED")
    if content == "PROVIDER_NOT_AUTHORIZED":
        failures.append("MRA001_PROVIDER_NOT_AUTHORIZED")
    if not provenance.get("citation_refs"):
        failures.append("MRA001_NO_CITATIONS")
    return {
        "artifact_type": "MRA001_GROUNDED_ANSWER_REPORT",
        "abstained": abstained,
        "content_preview": content[:240],
        "failures": sorted(set(failures)),
        "logical_id": "mra001.grounded_answer_report",
        "provider_id": provenance.get("provider_id"),
        "status": "PASS" if not failures else "FAIL",
    }


def _abstention_report(store: ReplayStore) -> dict[str, object]:
    inference = GroundedEvidenceInference()
    outcome = inference.infer(
        "Explain unavailable microstructure on ZZZZ",
        evidence_context={"resolve_explain": lambda _ref: (_ for _ in ()).throw(ValueError("missing"))},
    )
    failures: list[str] = []
    if not outcome.abstained:
        failures.append("MRA002_DID_NOT_ABSTAIN")
    if outcome.abstention_reason not in {"REF_NOT_FOUND", "EVIDENCE_NOT_AVAILABLE", "EVIDENCE_CONTEXT_MISSING"}:
        failures.append("MRA002_REASON_NOT_EXPLICIT")
    return {
        "artifact_type": "MRA001_ABSTENTION_REPORT",
        "abstention_reason": outcome.abstention_reason,
        "failures": sorted(set(failures)),
        "logical_id": "mra001.abstention_report",
        "status": "PASS" if not failures else "FAIL",
    }


def _citation_resolution_report(store: ReplayStore) -> dict[str, object]:
    conversation = store.assistant_service.create_conversation("MRA-001 citations")
    result = submit_assistant_prompt(store, conversation["conversation_id"], "explain quality")
    refs = result["assistant_message"].get("provenance", {}).get("citation_refs", [])
    failures: list[str] = []
    for ref in refs:
        try:
            if str(ref).startswith("explain:"):
                build_explain_payload(store, str(ref))
            elif str(ref).startswith("inspect:"):
                build_inspect_payload(store, str(ref))
        except ValueError:
            failures.append(f"MRA003_UNRESOLVED:{ref}")
    return {
        "artifact_type": "MRA001_CITATION_RESOLUTION_REPORT",
        "citation_refs": list(refs),
        "failures": sorted(set(failures)),
        "logical_id": "mra001.citation_resolution_report",
        "status": "PASS" if refs and not failures else "FAIL",
    }


def _authority_boundary_report(store: ReplayStore) -> dict[str, object]:
    status = build_assistant_status(store)
    failures: list[str] = []
    if status.get("authority_boundary") != "READ_ONLY_NO_EXECUTION":
        failures.append("MRA004_BOUNDARY_MISMATCH")
    if status.get("provider_id") != GroundedEvidenceInference.provider_id:
        failures.append("MRA004_PROVIDER_MISMATCH")
    return {
        "artifact_type": "MRA001_AUTHORITY_BOUNDARY_REPORT",
        "authority_boundary": status.get("authority_boundary"),
        "failures": sorted(set(failures)),
        "logical_id": "mra001.authority_boundary_report",
        "provider_id": status.get("provider_id"),
        "status": "PASS" if not failures else "FAIL",
    }


def _determinism_report(store: ReplayStore) -> dict[str, object]:
    index = store.cursor_index
    conversation_a = store.assistant_service.create_conversation("MRA determinism A")
    answer_a = submit_assistant_prompt(store, conversation_a["conversation_id"], "Summarize replay context")
    store.set_cursor_index(max(0, index - 1))
    store.set_cursor_index(index)
    conversation_b = store.assistant_service.create_conversation("MRA determinism B")
    answer_b = submit_assistant_prompt(store, conversation_b["conversation_id"], "Summarize replay context")
    content_a = str(answer_a["assistant_message"].get("content", ""))
    content_b = str(answer_b["assistant_message"].get("content", ""))
    match = content_a == content_b
    return {
        "artifact_type": "MRA001_DETERMINISM_REPORT",
        "determinism_match": match,
        "logical_id": "mra001.determinism_report",
        "status": "PASS" if match else "FAIL",
    }


def build_evidence(
    output_dir: Path,
    *,
    assistant_audit_root: Path | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    store = _load_store(assistant_audit_root)

    grounded = _grounded_answer_report(store)
    abstention = _abstention_report(store)
    citations = _citation_resolution_report(store)
    boundary = _authority_boundary_report(store)
    determinism = _determinism_report(store)

    write_canonical_json(output_dir / "grounded-answer-report.json", grounded)
    write_canonical_json(output_dir / "abstention-report.json", abstention)
    write_canonical_json(output_dir / "citation-resolution-report.json", citations)
    write_canonical_json(output_dir / "authority-boundary-report.json", boundary)
    write_canonical_json(output_dir / "determinism-report.json", determinism)

    registry = build_registry(REGISTRY_PATH)
    write_canonical_json(output_dir / "assertion_registry.json", registry)

    observations = {
        "MRA-001": {
            "failures": grounded.get("failures"),
            "reason_codes": grounded.get("failures", []),
            "status": grounded.get("status"),
        },
        "MRA-002": {
            "failures": abstention.get("failures"),
            "reason_codes": abstention.get("failures", []),
            "status": abstention.get("status"),
        },
        "MRA-003": {
            "failures": citations.get("failures"),
            "reason_codes": citations.get("failures", []),
            "status": citations.get("status"),
        },
        "MRA-004": {
            "failures": boundary.get("failures"),
            "reason_codes": boundary.get("failures", []),
            "status": boundary.get("status"),
        },
        "MRA-005": {
            "determinism_match": determinism.get("determinism_match"),
            "reason_codes": [] if determinism.get("determinism_match") else ["MRA005_MISMATCH"],
            "status": determinism.get("status"),
        },
    }

    members = {
        "mra001.grounded_answer_report": "grounded-answer-report.json",
        "mra001.abstention_report": "abstention-report.json",
        "mra001.citation_resolution_report": "citation-resolution-report.json",
        "mra001.authority_boundary_report": "authority-boundary-report.json",
        "mra001.determinism_report": "determinism-report.json",
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
        "subject_manifest_hash": sha256_bytes(canonical_bytes({"track": "mra001", "root_id": "ROOT-2E7C91F4"})),
        "tool_versions": ["mra001.run_mra001_pipeline/1.0.0"],
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
        "mra001.assertion_aggregate": "assertion-aggregate.json",
        "mra001.assertion_registry": "assertion_registry.json",
        "mra001.assertion_results": "assertion-results.json",
        "mra001.assertion_run_manifest": "assertion-run-manifest.json",
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
        "logical_id": "mra001.candidate_evidence_root",
        "run_id": run_id,
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", candidate_body)
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": candidate_body["candidate_evidence_root"],
        "instrument_id": store.instrument_id,
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
