"""Publish formal Phase 1 decision completion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import load_json_strict, write_canonical_json
from market_platform_foundation.offline_guard import install_guard

BUNDLE_DIR = ROOT / "evidence/phase1/decision-bundle"
PUBLICATION_PATH = (
    ROOT / "docs/superpowers/governance/2026-08-15-phase-1-decision-publication.json"
)
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
ROADMAP_PATH = ROOT / "docs/roadmap/REVISION_3_ROADMAP.md"


def publish(*, bundle_dir: Path, publication_path: Path) -> dict[str, object]:
    verifier_path = bundle_dir / "adr-verifier-result.json"
    index_path = bundle_dir / "adr-acceptance-index.json"
    root_path = bundle_dir / "candidate-evidence-root.json"
    for path in (verifier_path, index_path, root_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing bundle artifact: {path}")

    verifier = load_json_strict(verifier_path)
    index_doc = load_json_strict(index_path)
    root_doc = load_json_strict(root_path)
    if not isinstance(verifier, dict) or not isinstance(index_doc, dict) or not isinstance(root_doc, dict):
        raise ValueError("bundle artifacts invalid")
    if verifier.get("overall_status") != "PASS":
        raise ValueError("ADR verifier must be PASS before publication")

    manifest = load_json_strict(AUTHORITY_PATH)
    if not isinstance(manifest, dict):
        raise ValueError("authority manifest invalid")
    if manifest.get("phase1_status") == "PASS":
        raise ValueError("Phase 1 decision publication already recorded")

    authority_at_publication = write_canonical_json(
        AUTHORITY_PATH,
        {
            **manifest,
            "phase1_status": "PASS",
        },
    )

    publication_doc = {
        "artifact_type": "PHASE_1_DECISION_PUBLICATION",
        "authority_manifest_at_publication": {
            "logical_id": "foundation.canonical_authority_manifest",
            "phase0_status": manifest.get("phase0_status"),
            "phase0a_status": manifest.get("phase0a_status"),
            "phase1_status": "PASS",
            "repository_relative_path": "manifests/phase0/canonical-authority.json",
            "sha256": authority_at_publication,
        },
        "candidate_evidence_root": str(root_doc["candidate_evidence_root"]),
        "effect": (
            "Publishes Phase 1 foundational decision completion. All registry ADRs "
            "are accepted with conformance evidence and the ADR verifier reports PASS. "
            "Phase 2 contract implementation remains unauthorized."
        ),
        "logical_id": "phase1.decision_publication",
        "phase1_adr_acceptance_index": {
            "accepted_adr_count": index_doc.get("accepted_adr_count"),
            "index_sha256": index_doc.get("index_sha256"),
            "repository_relative_path": str(
                index_path.resolve().relative_to(ROOT.resolve()).as_posix()
            ),
        },
        "phase1_adr_verifier_result": {
            "overall_status": verifier.get("overall_status"),
            "repository_relative_path": str(
                verifier_path.resolve().relative_to(ROOT.resolve()).as_posix()
            ),
            "total_count": verifier.get("total_count"),
        },
        "principal_id": "PROJECT-PRINCIPAL-001",
        "published_at": "2026-08-15T14:45:00.000000000Z",
        "publisher_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "repository_root_id": "ROOT-2E7C91F4",
        "sanitization": {
            "absolute_paths_included": False,
            "account_identifiers_included": False,
            "credential_values_included": False,
            "remote_urls_included": False,
        },
        "schema_version": "1.0.0",
        "status": "PUBLISHED",
    }
    if publication_path.exists():
        raise FileExistsError(publication_path)
    publication_hash = write_canonical_json(publication_path, publication_doc)

    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    roadmap = roadmap.replace(
        "| Phase 1 — foundational decisions | Consider dataset identity, PIT feature semantics, model identity/reproducibility, cache semantics, institutional evidence, donor reuse, and provider-neutral LLM boundaries. | decision work in progress after Phase 0A `PASS` |",
        "| Phase 1 — foundational decisions | Consider dataset identity, PIT feature semantics, model identity/reproducibility, cache semantics, institutional evidence, donor reuse, and provider-neutral LLM boundaries. | `PASS` — all registry ADRs accepted; Phase 2 remains unauthorized |",
    )
    ROADMAP_PATH.write_text(roadmap, encoding="utf-8")

    return {
        "authority_manifest_at_publication": authority_at_publication,
        "candidate_evidence_root": root_doc["candidate_evidence_root"],
        "publication_path": str(publication_path),
        "publication_sha256": publication_hash,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", default=str(BUNDLE_DIR))
    parser.add_argument("--publication", default=str(PUBLICATION_PATH))
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    try:
        report = publish(
            bundle_dir=Path(args.bundle_dir).resolve(),
            publication_path=Path(args.publication).resolve(),
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
