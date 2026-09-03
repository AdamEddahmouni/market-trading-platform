"""Publish formal Phase 15 PASS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard

RUN_ID = "PLACEHOLDER_RUN_ID"
CANDIDATE_ROOT = "PLACEHOLDER_CANDIDATE_ROOT"
POSTREVIEW_DIR = ROOT / "evidence/phase15/postreview-pass"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-18-phase-15-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"


def publish(*, publication_path: Path, run_id: str, candidate_root: str) -> dict[str, object]:
    final_path = POSTREVIEW_DIR / "phase15.final_acceptance_result.json"
    index_path = POSTREVIEW_DIR / "phase15.acceptance_index.json"
    for path in (final_path, index_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    final_doc = load_json_strict(final_path)
    index_doc = load_json_strict(index_path)
    if not isinstance(final_doc, dict) or not isinstance(index_doc, dict):
        raise ValueError("postreview artifacts invalid")
    if final_doc.get("outcome") != "PASS":
        raise ValueError("final acceptance result must be PASS")

    manifest = load_json_strict(AUTHORITY_PATH)
    if not isinstance(manifest, dict):
        raise ValueError("authority manifest invalid")
    if manifest.get("phase15_status") == "PASS":
        raise ValueError("Phase 15 PASS already published")

    authority_at_publication = write_canonical_json(
        AUTHORITY_PATH,
        {**manifest, "phase15_status": "PASS"},
    )

    publication_doc = {
        "acceptance_index": {
            "index_sha256": index_doc.get("index_sha256"),
            "logical_id": "phase15.acceptance_index",
            "repository_relative_path": "evidence/phase15/postreview-pass/phase15.acceptance_index.json",
            "root_hash": index_doc.get("root_hash"),
            "sha256": sha256_bytes(index_path.read_bytes()),
        },
        "artifact_type": "PHASE_15_PASS_PUBLICATION",
        "assertion_run_id": run_id,
        "authority_manifest_at_publication": {
            "logical_id": "foundation.canonical_authority_manifest",
            "phase10_status": manifest.get("phase10_status"),
            "phase11_status": manifest.get("phase11_status"),
            "phase12_status": manifest.get("phase12_status"),
            "phase13_status": manifest.get("phase13_status"),
            "phase14_status": manifest.get("phase14_status"),
            "phase15_status": "PASS",
            "phase9_status": manifest.get("phase9_status"),
            "repository_relative_path": "manifests/phase0/canonical-authority.json",
            "sha256": authority_at_publication,
            "ui1_status": manifest.get("ui1_status"),
        },
        "candidate_evidence_root": candidate_root,
        "effect": (
            "Publishes Phase 15 PASS for fixture-first public_catalyst whale family on "
            "ADMITTED-CATALYST-BOXL-001."
        ),
        "final_acceptance_result": {
            "final_result_id": final_doc.get("final_result_id"),
            "outcome": final_doc.get("outcome"),
            "repository_relative_path": "evidence/phase15/postreview-pass/phase15.final_acceptance_result.json",
            "sha256": sha256_bytes(final_path.read_bytes()),
        },
        "logical_id": "phase15.pass_publication",
        "principal_id": "PROJECT-PRINCIPAL-001",
        "published_at": "2026-08-18T23:05:00.000000000Z",
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
    return {
        "authority_manifest_at_publication": authority_at_publication,
        "candidate_evidence_root": candidate_root,
        "publication_path": str(publication_path),
        "publication_sha256": publication_hash,
    }


def main() -> int:
    install_guard([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", default=str(PUBLICATION_PATH))
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--candidate-root", default=CANDIDATE_ROOT)
    args = parser.parse_args()
    if args.run_id == RUN_ID or args.candidate_root == CANDIDATE_ROOT:
        print("Provide --run-id and --candidate-root from pipeline output", file=sys.stderr)
        return 1
    try:
        report = publish(
            publication_path=Path(args.publication).resolve(),
            run_id=args.run_id,
            candidate_root=args.candidate_root,
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
