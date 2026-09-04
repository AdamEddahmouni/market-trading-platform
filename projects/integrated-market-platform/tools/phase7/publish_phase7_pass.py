"""Publish formal Phase 7 PASS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict, sha256_bytes, write_canonical_json
from market_platform_foundation.offline_guard import install_guard

RUN_ID = "B101693ACC598DA769ED39857E47B8F13FCC0F4E39BFF4F93282E0EDF93946B3"
CANDIDATE_ROOT = "23764FACBB6BB29C73A741FB877388B19988277734D0E19A76D116B9A3B742B0"
POSTREVIEW_DIR = ROOT / "evidence/phase7/postreview-pass"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-16-phase-7-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
ROADMAP_PATH = ROOT / "docs/roadmap/REVISION_3_ROADMAP.md"


def publish(*, publication_path: Path) -> dict[str, object]:
    final_path = POSTREVIEW_DIR / "phase7.final_acceptance_result.json"
    index_path = POSTREVIEW_DIR / "phase7.acceptance_index.json"
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
    if manifest.get("phase7_status") == "PASS":
        raise ValueError("Phase 7 PASS already published")

    authority_at_publication = write_canonical_json(
        AUTHORITY_PATH,
        {**manifest, "phase7_status": "PASS"},
    )

    publication_doc = {
        "acceptance_index": {
            "index_sha256": index_doc.get("index_sha256"),
            "logical_id": "phase7.acceptance_index",
            "repository_relative_path": "evidence/phase7/postreview-pass/phase7.acceptance_index.json",
            "root_hash": index_doc.get("root_hash"),
            "sha256": sha256_bytes(index_path.read_bytes()),
        },
        "artifact_type": "PHASE_7_PASS_PUBLICATION",
        "assertion_run_id": RUN_ID,
        "authority_manifest_at_publication": {
            "logical_id": "foundation.canonical_authority_manifest",
            "phase0_status": manifest.get("phase0_status"),
            "phase0a_status": manifest.get("phase0a_status"),
            "phase1_status": manifest.get("phase1_status"),
            "phase2_status": manifest.get("phase2_status"),
            "phase3_status": manifest.get("phase3_status"),
            "phase4_status": manifest.get("phase4_status"),
            "phase5_status": manifest.get("phase5_status"),
            "phase5r_status": manifest.get("phase5r_status"),
            "phase6_status": manifest.get("phase6_status"),
            "phase7_status": "PASS",
            "repository_relative_path": "manifests/phase0/canonical-authority.json",
            "sha256": authority_at_publication,
        },
        "candidate_evidence_root": CANDIDATE_ROOT,
        "effect": (
            "Publishes Phase 7 PASS for independent risk, conservative simulation, cash/position/P&L "
            "reconciliation, and attribution on the admitted equity intraday source. "
            "Phase 8 remains unauthorized."
        ),
        "final_acceptance_result": {
            "final_result_id": final_doc.get("final_result_id"),
            "outcome": final_doc.get("outcome"),
            "repository_relative_path": "evidence/phase7/postreview-pass/phase7.final_acceptance_result.json",
            "sha256": sha256_bytes(final_path.read_bytes()),
        },
        "logical_id": "phase7.pass_publication",
        "principal_id": "PROJECT-PRINCIPAL-001",
        "published_at": "2026-08-16T02:00:00.000000000Z",
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
        "| Phase 7 — risk, simulation, and accounting | Independent risk, conservative simulation, cash/position/P&L reconciliation, and attribution remain mandatory. | unchanged prerequisite |",
        "| Phase 7 — risk, simulation, and accounting | Independent risk, conservative simulation, cash/position/P&L reconciliation, and attribution remain mandatory. | `PASS` — risk, simulation, and accounting proven on admitted fixture; Phase 8 remains unauthorized |",
    )
    ROADMAP_PATH.write_text(roadmap, encoding="utf-8")

    return {
        "authority_manifest_at_publication": authority_at_publication,
        "candidate_evidence_root": CANDIDATE_ROOT,
        "publication_path": str(publication_path),
        "publication_sha256": publication_hash,
    }


def main() -> int:
    install_guard([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", default=str(PUBLICATION_PATH))
    args = parser.parse_args()
    try:
        report = publish(publication_path=Path(args.publication).resolve())
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
