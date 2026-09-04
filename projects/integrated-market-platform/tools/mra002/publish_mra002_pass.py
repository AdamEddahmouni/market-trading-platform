"""Publish formal MRA-002 PASS."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard

BUILD_RUN_DIR = ROOT / "evidence/mra002/build-run"
POSTREVIEW_DIR = ROOT / "evidence/mra002/postreview-pass"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-18-mra-002-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"


def publication_manifest_hash(manifest: dict[str, object], bound: dict[str, object]) -> str:
    snapshot = {
        key: value
        for key, value in manifest.items()
        if not key.endswith("_status")
    }
    for key, value in bound.items():
        if key.endswith("_status"):
            snapshot[key] = value
    return sha256_bytes(canonical_bytes(snapshot))


def _sync_postreview(build_run: Path, postreview: Path) -> None:
    if postreview.exists():
        shutil.rmtree(postreview)
    shutil.copytree(build_run, postreview)


def publish(*, publication_path: Path, build_run_dir: Path) -> dict[str, object]:
    manifest_path = build_run_dir / "assertion-run-manifest.json"
    candidate_path = build_run_dir / "candidate-evidence-root.json"
    aggregate_path = build_run_dir / "assertion-aggregate.json"
    for path in (manifest_path, candidate_path, aggregate_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest_doc = load_json_strict(manifest_path)
    candidate_doc = load_json_strict(candidate_path)
    aggregate_doc = load_json_strict(aggregate_path)
    if not isinstance(manifest_doc, dict) or not isinstance(candidate_doc, dict):
        raise ValueError("build-run artifacts invalid")
    if aggregate_doc.get("aggregate_status") != "PASS":
        raise ValueError("assertion aggregate must be PASS")

    run_id = str(manifest_doc.get("run_id", ""))
    candidate_root = str(candidate_doc.get("candidate_evidence_root", ""))
    if not run_id or not candidate_root:
        raise ValueError("run_id and candidate_evidence_root required")

    _sync_postreview(build_run_dir, POSTREVIEW_DIR)

    final_doc = {
        "artifact_type": "MRA002_FINAL_ACCEPTANCE_RESULT",
        "final_result_id": sha256_bytes(
            json.dumps(
                {"aggregate_status": "PASS", "run_id": run_id},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "logical_id": "mra002.final_acceptance_result",
        "outcome": "PASS",
        "run_id": run_id,
    }
    write_canonical_json(POSTREVIEW_DIR / "mra002.final_acceptance_result.json", final_doc)

    authority_manifest = load_json_strict(AUTHORITY_PATH)
    if not isinstance(authority_manifest, dict):
        raise ValueError("authority manifest invalid")
    updated_manifest = {
        **authority_manifest,
        "mra002_status": "PASS",
    }
    authority_binding = {
        "logical_id": "foundation.canonical_authority_manifest",
        "mra001_status": updated_manifest.get("mra001_status"),
        "mra002_status": "PASS",
        "repository_relative_path": "manifests/phase0/canonical-authority.json",
        "ui1_status": updated_manifest.get("ui1_status"),
        "ui2_status": updated_manifest.get("ui2_status"),
    }
    authority_hash = publication_manifest_hash(updated_manifest, authority_binding)
    authority_binding["sha256"] = authority_hash
    write_canonical_json(AUTHORITY_PATH, updated_manifest)

    if publication_path.exists():
        raise FileExistsError(publication_path)

    publication_doc = {
        "artifact_type": "MRA002_PASS_PUBLICATION",
        "assertion_run_id": run_id,
        "authority_manifest_at_publication": authority_binding,
        "candidate_evidence_root": candidate_root,
        "effect": (
            "Publishes MRA-002 PASS for Anthropic LLM research assistant "
            "(mocked HTTP acceptance; grounded fallback; env-injected credentials)."
        ),
        "final_acceptance_result": {
            "final_result_id": final_doc["final_result_id"],
            "outcome": "PASS",
            "repository_relative_path": "evidence/mra002/postreview-pass/mra002.final_acceptance_result.json",
            "sha256": sha256_bytes((POSTREVIEW_DIR / "mra002.final_acceptance_result.json").read_bytes()),
        },
        "logical_id": "mra002.pass_publication",
        "principal_id": "PROJECT-PRINCIPAL-001",
        "published_at": "2026-08-18T18:45:00.000000000Z",
        "publisher_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "repository_root_id": "ROOT-2E7C91F4",
        "schema_version": "1.0.0",
        "status": "PUBLISHED",
        "summary": "MRA-002 assertions MRA2-001 through MRA2-005 pass with mocked Anthropic HTTP.",
    }
    publication_hash = write_canonical_json(publication_path, publication_doc)
    return {
        "authority_manifest_at_publication": authority_hash,
        "candidate_evidence_root": candidate_root,
        "publication_path": str(publication_path),
        "publication_sha256": publication_hash,
        "run_id": run_id,
    }


def main() -> int:
    install_guard([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", default=str(PUBLICATION_PATH))
    parser.add_argument("--build-run", default=str(BUILD_RUN_DIR))
    args = parser.parse_args()
    try:
        report = publish(
            publication_path=Path(args.publication).resolve(),
            build_run_dir=Path(args.build_run).resolve(),
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
