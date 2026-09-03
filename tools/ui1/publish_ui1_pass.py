"""Publish formal UI-001 PASS."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard

RUN_ID = "AC5DD9D35F59C22E6216EAB0E8202DDEC7E06329F1076904F884B778B780D0D1"
CANDIDATE_ROOT = "4112D3438D2B98FF3A9EB04D574AB1142C2B1212CD402468225DD68514708D2E"
POSTREVIEW_DIR = ROOT / "evidence/ui1/postreview-pass"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-18-ui-001-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
ROADMAP_PATH = ROOT / "docs/roadmap/REVISION_3_ROADMAP.md"


def publish(*, publication_path: Path) -> dict[str, object]:
    final_path = POSTREVIEW_DIR / "ui1.final_acceptance_result.json"
    index_path = POSTREVIEW_DIR / "ui1.acceptance_index.json"
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
    if manifest.get("ui1_status") == "PASS":
        raise ValueError("UI-001 PASS already published")

    authority_at_publication = write_canonical_json(
        AUTHORITY_PATH,
        {**manifest, "ui1_status": "PASS"},
    )

    publication_doc = {
        "acceptance_index": {
            "index_sha256": index_doc.get("index_sha256"),
            "logical_id": "ui1.acceptance_index",
            "repository_relative_path": "evidence/ui1/postreview-pass/ui1.acceptance_index.json",
            "root_hash": index_doc.get("root_hash"),
            "sha256": sha256_bytes(index_path.read_bytes()),
        },
        "artifact_type": "UI1_PASS_PUBLICATION",
        "assertion_run_id": RUN_ID,
        "authority_manifest_at_publication": {
            "logical_id": "foundation.canonical_authority_manifest",
            "phase8_status": manifest.get("phase8_status"),
            "ui1_status": "PASS",
            "repository_relative_path": "manifests/phase0/canonical-authority.json",
            "sha256": authority_at_publication,
        },
        "candidate_evidence_root": final_doc.get("candidate_evidence_root", CANDIDATE_ROOT),
        "effect": "Publishes UI-001 PASS for replay-only research UI on admitted equity intraday fixture.",
        "final_acceptance_result": {
            "final_result_id": final_doc.get("final_result_id"),
            "outcome": "PASS",
            "repository_relative_path": "evidence/ui1/postreview-pass/ui1.final_acceptance_result.json",
            "sha256": sha256_bytes(final_path.read_bytes()),
        },
        "logical_id": "ui1.pass_publication",
        "principal_id": "PROJECT-PRINCIPAL-001",
        "published_at": "2026-08-18T02:00:00.000000000Z",
        "publisher_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "repository_root_id": "ROOT-2E7C91F4",
        "schema_version": "1.0.0",
        "status": "PUBLISHED",
    }
    write_canonical_json(publication_path, publication_doc)
    return publication_doc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-path", default=str(PUBLICATION_PATH))
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    doc = publish(publication_path=Path(args.publication_path))
    print(doc["logical_id"], doc["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
