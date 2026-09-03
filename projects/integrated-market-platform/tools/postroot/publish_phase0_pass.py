"""Publish formal Phase 0 PASS after postroot gate and principal validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import load_json_strict, sha256_bytes, write_canonical_json

RUN_ID = "DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66"
CANDIDATE_ROOT = "78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482"
ROOT_ID = "ROOT-2E7C91F4"
PRE_PUBLICATION_AUTHORITY_HASH = (
    "972E82F21A148C10BE20588847F48D7886115D9693A5EC14222DE18D22098D70"
)
AUTHORITY_MANIFEST_PATH = ROOT / "manifests/phase0/canonical-authority.json"
DEFAULT_POSTREVIEW = ROOT / "evidence/phase0/postreview"
DEFAULT_PUBLICATION = (
    ROOT
    / "docs/superpowers/governance/2026-08-15-phase-0-pass-publication.json"
)
README_PATH = ROOT / "README.md"
ROADMAP_PATH = ROOT / "docs/roadmap/REVISION_3_ROADMAP.md"
PROMPTS_PATH = ROOT / "docs/superpowers/governance/2026-08-14-ai-review-run-prompts.md"


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run_principal_validation() -> bool:
    from tools.postroot.verify_governed_subject_hashes import main as verify_subject
    from tools.postroot.verify_postreview_hashes import main as verify_postreview

    return verify_postreview() == 0 and verify_subject() == 0


def build_publication_record(
    *,
    final_doc: dict[str, object],
    index_doc: dict[str, object],
    final_path: Path,
    index_path: Path,
    authority_at_acceptance_hash: str,
    authority_at_publication_hash: str,
    published_at: str,
) -> dict[str, object]:
    return {
        "acceptance_index": {
            "index_sha256": str(index_doc["index_sha256"]),
            "logical_id": "phase0.acceptance_index",
            "repository_relative_path": repo_relative(index_path),
            "root_hash": str(index_doc["root_hash"]),
            "sha256": sha256_file(index_path),
        },
        "artifact_type": "PHASE_0_PASS_PUBLICATION",
        "assertion_run_id": RUN_ID,
        "authority_manifest_at_acceptance": {
            "logical_id": "foundation.canonical_authority_manifest",
            "phase0_status": "BLOCKED_PENDING_POSTROOT_ACCEPTANCE",
            "repository_relative_path": repo_relative(AUTHORITY_MANIFEST_PATH),
            "sha256": authority_at_acceptance_hash,
        },
        "authority_manifest_at_publication": {
            "logical_id": "foundation.canonical_authority_manifest",
            "phase0_status": "PASS",
            "repository_relative_path": repo_relative(AUTHORITY_MANIFEST_PATH),
            "sha256": authority_at_publication_hash,
        },
        "candidate_evidence_root": CANDIDATE_ROOT,
        "effect": (
            "Publishes Phase 0 PASS for the governed repository subject bound to "
            "the completed postroot acceptance index and final acceptance result. "
            "Candidate evidence bundles remain immutable pre-publication snapshots."
        ),
        "final_acceptance_result": {
            "final_result_id": str(final_doc["final_result_id"]),
            "logical_id": "phase0.final_acceptance_result",
            "outcome": str(final_doc["outcome"]),
            "repository_relative_path": repo_relative(final_path),
            "sha256": sha256_file(final_path),
        },
        "logical_id": "phase0.pass_publication",
        "principal_id": "PROJECT-PRINCIPAL-001",
        "published_at": published_at,
        "publisher_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "repository_root_id": ROOT_ID,
        "sanitization": {
            "absolute_paths_included": False,
            "account_identifiers_included": False,
            "credential_values_included": False,
            "remote_urls_included": False,
        },
        "schema_version": "1.0.0",
        "status": "PUBLISHED",
    }


def update_readme() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    text = text.replace(
        "Its Phase 0 status is\n`BLOCKED_PENDING_POSTROOT_ACCEPTANCE`.",
        "Its Phase 0 status is `PASS`, published per "
        "[phase-0-pass-publication](docs/superpowers/governance/2026-08-15-phase-0-pass-publication.json).",
    )
    README_PATH.write_text(text, encoding="utf-8")


def update_roadmap() -> None:
    text = ROADMAP_PATH.read_text(encoding="utf-8")
    text = text.replace(
        "| Phase 0 — governance and structural no-live safety | Preserve existing scope; bind the approved revision and fresh current-subject evidence. Candidate evidence is not final acceptance. | `BLOCKED_PENDING_POSTROOT_ACCEPTANCE` |",
        "| Phase 0 — governance and structural no-live safety | Structural no-live safety and governance evidence accepted for the current repository subject. | `PASS` |",
    )
    ROADMAP_PATH.write_text(text, encoding="utf-8")


def update_prompts_index(publication_hash: str) -> None:
    text = PROMPTS_PATH.read_text(encoding="utf-8")
    marker = "Principal validation of these artifacts remains a separate step before formal publication."
    replacement = (
        "Formal Phase 0 PASS was published in "
        "[2026-08-15-phase-0-pass-publication.json](./2026-08-15-phase-0-pass-publication.json) "
        f"(SHA-256 `{publication_hash}`)."
    )
    if marker in text:
        text = text.replace(marker, replacement)
    PROMPTS_PATH.write_text(text, encoding="utf-8")


def publish(
    *,
    postreview: Path,
    publication_path: Path,
    skip_validation: bool,
) -> dict[str, object]:
    if not skip_validation and not run_principal_validation():
        raise ValueError("principal validation checks failed")

    final_path = postreview / "phase0.final_acceptance_result.json"
    index_path = postreview / "phase0.acceptance_index.json"
    if not final_path.is_file() or not index_path.is_file():
        raise FileNotFoundError("postreview gate artifacts are missing")

    final_doc = load_json_strict(final_path)
    index_doc = load_json_strict(index_path)
    if not isinstance(final_doc, dict) or not isinstance(index_doc, dict):
        raise ValueError("postreview artifacts are invalid")
    if str(final_doc.get("outcome", "")) != "PASS":
        raise ValueError(f"final acceptance outcome is not PASS: {final_doc.get('outcome')}")

    authority_at_acceptance = sha256_file(AUTHORITY_MANIFEST_PATH)
    if authority_at_acceptance != PRE_PUBLICATION_AUTHORITY_HASH:
        raise ValueError(
            "authority manifest hash does not match acceptance snapshot: "
            f"{authority_at_acceptance}"
        )

    manifest = load_json_strict(AUTHORITY_MANIFEST_PATH)
    if not isinstance(manifest, dict):
        raise ValueError("authority manifest is invalid")
    if manifest.get("phase0_status") == "PASS":
        raise ValueError("Phase 0 PASS is already published")

    manifest["phase0_status"] = "PASS"
    authority_at_publication = write_canonical_json(AUTHORITY_MANIFEST_PATH, manifest)

    published_at = str(final_doc.get("completed_at", "2026-08-15T03:22:01.000000000Z"))
    publication_doc = build_publication_record(
        final_doc=final_doc,
        index_doc=index_doc,
        final_path=final_path,
        index_path=index_path,
        authority_at_acceptance_hash=authority_at_acceptance,
        authority_at_publication_hash=authority_at_publication,
        published_at=published_at,
    )
    if publication_path.exists():
        raise FileExistsError(publication_path)
    publication_hash = write_canonical_json(publication_path, publication_doc)

    update_readme()
    update_roadmap()
    update_prompts_index(publication_hash)

    return {
        "authority_manifest_at_acceptance": authority_at_acceptance,
        "authority_manifest_at_publication": authority_at_publication,
        "final_acceptance_outcome": final_doc["outcome"],
        "final_result_id": final_doc["final_result_id"],
        "index_sha256": index_doc["index_sha256"],
        "publication_path": str(publication_path),
        "publication_sha256": publication_hash,
        "published_at": published_at,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postreview", default=str(DEFAULT_POSTREVIEW))
    parser.add_argument("--publication", default=str(DEFAULT_PUBLICATION))
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip automated principal validation (not recommended)",
    )
    return parser.parse_args()


def main() -> int:
    from market_platform_foundation.offline_guard import install_guard

    install_guard([])
    args = parse_args()
    try:
        report = publish(
            postreview=Path(args.postreview).resolve(),
            publication_path=Path(args.publication).resolve(),
            skip_validation=args.skip_validation,
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
