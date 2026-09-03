"""Offline CLI for the Batch 09 Phase 3B registry revision preview.

No command opens a network socket and this package never imports ``ibapi``. Every write goes
to a caller-supplied output root; the canonical Phase 3B registry is opened read-only and is
never a write target. A guard refuses any output root that would overlap a committed fixture
directory containing a canonical Phase 3B registry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from squeeze_core.research.io import load_case_registry
from squeeze_core.serialization import canonical_json_bytes

from .preview import SOURCE_CASE_IDS, build_registry_revision_preview
from .publication import (
    check_phase3c_structural_compatibility,
    simulate_phase3b_publication,
)
from .report import render_field_diff, render_preview_summary

#: Canonical Phase 3B artifacts that must never be a write target.
CANONICAL_REGISTRY_PATHS = (
    Path("tests/fixtures/acquisition/batch01/phase3b-registry-candidates.json"),
    Path("tests/fixtures/acquisition/batch02/phase3b-registry-candidates.json"),
    Path("tests/fixtures/acquisition/phase_3d_phase3b_registry_candidates.json"),
    Path("tests/fixtures/research/phase_3b_case_registry.json"),
)

DEFAULT_SOURCE_REGISTRY = CANONICAL_REGISTRY_PATHS[0]
DEFAULT_FREEZE_ROOT = Path("intake/local-bars/ibkr-batch-05/phase3a/batch-08")
#: Exactly one level under the Batch 05 root, so ``resolve_artifact_path`` admits the
#: ``../phase3a/batch-08/...`` references the preview declares.
DEFAULT_OUT_ROOT = Path("intake/local-bars/ibkr-batch-05/phase3b-preview-batch-09")
PREVIEW_REGISTRY_FILENAME = "phase3b-registry-preview.json"


class PreviewOutputError(ValueError):
    """Raised when an output root would collide with a canonical artifact."""


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _guard_output_root(out_root: Path) -> None:
    resolved = out_root.resolve()
    for canonical in CANONICAL_REGISTRY_PATHS:
        parent = canonical.resolve().parent if canonical.exists() else None
        if parent is not None and (resolved == parent or parent in resolved.parents):
            raise PreviewOutputError(f"BATCH09_OUTPUT_ROOT_COLLIDES:{canonical}")


def generate(
    source_registry_path: Path,
    freeze_root: Path,
    out_root: Path,
) -> int:
    """Generate every dry-run artifact for the 13-case preview."""
    _guard_output_root(out_root)

    source_registry = load_case_registry(source_registry_path)
    freeze_summary = json.loads(
        (freeze_root / "batch-summary.json").read_text(encoding="utf-8")
    )

    preview, preview_registry = build_registry_revision_preview(
        source_registry=source_registry,
        freeze_root=freeze_root,
        freeze_summary=freeze_summary,
    )

    registry_path = out_root / PREVIEW_REGISTRY_FILENAME
    _write(registry_path, canonical_json_bytes(preview_registry) + b"\n")

    artifacts = simulate_phase3b_publication(registry_path, SOURCE_CASE_IDS)
    compatibility = check_phase3c_structural_compatibility(registry_path)

    _write(out_root / "registry-preview.jsonl", artifacts.registry_jsonl)
    _write(out_root / "registry-preview.csv", artifacts.registry_csv)
    _write(out_root / "dataset-dry-run.json", artifacts.dataset_json)
    _write(out_root / "dataset-dry-run.jsonl", artifacts.dataset_jsonl)
    _write(out_root / "dataset-dry-run.csv", artifacts.dataset_csv)
    _write(out_root / "batch-dry-run.json", artifacts.batch_json)
    _write(out_root / "candidate-previews.json", canonical_json_bytes(preview) + b"\n")
    _write(
        out_root / "registry-field-diff.json",
        canonical_json_bytes(preview.diffs) + b"\n",
    )
    _write(
        out_root / "detection-preview.json",
        canonical_json_bytes(tuple(
            {
                "case_id": item.case_id,
                "symbol": item.symbol,
                "research_detection_policy_version": item.research_detection_policy_version,
                "research_detection_status": item.research_detection_status,
                "research_detection_reason": item.research_detection_reason,
                "required_rule_outcomes": item.required_rule_outcomes,
            }
            for item in preview.candidates
        )) + b"\n",
    )
    _write(
        out_root / "phase3c-compatibility.json",
        canonical_json_bytes(compatibility) + b"\n",
    )
    _write(
        out_root / "preview-summary.json",
        canonical_json_bytes({
            "case_result_count": artifacts.case_result_count,
            "skipped_case_count": artifacts.skipped_case_count,
            "dataset_row_count": artifacts.dataset_row_count,
            "skipped_diagnostic_codes": artifacts.skipped_diagnostic_codes,
            "canonical_registry_mutated": artifacts.canonical_registry_mutated,
            "phase3b_published": False,
            "phase3e_started": False,
        }) + b"\n",
    )
    _write(
        out_root / "preview-summary.md",
        render_preview_summary(preview).encode("utf-8"),
    )
    _write(out_root / "registry-field-diff.md", render_field_diff(preview).encode("utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phase3b-preview",
        description=(
            "Batch 09 Phase 3B registry revision preview (dry run; never publishes)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    generate_parser = sub.add_parser(
        "generate", help="generate the 13-case dry-run preview"
    )
    generate_parser.add_argument(
        "--source-registry", type=Path, default=DEFAULT_SOURCE_REGISTRY
    )
    generate_parser.add_argument("--freeze-root", type=Path, default=DEFAULT_FREEZE_ROOT)
    generate_parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    return parser


def main(argv: tuple[str, ...] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return generate(args.source_registry, args.freeze_root, args.out_root)
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised through __main__
    sys.exit(main())


__all__ = [
    "CANONICAL_REGISTRY_PATHS",
    "DEFAULT_FREEZE_ROOT",
    "DEFAULT_OUT_ROOT",
    "DEFAULT_SOURCE_REGISTRY",
    "PREVIEW_REGISTRY_FILENAME",
    "PreviewOutputError",
    "build_parser",
    "generate",
    "main",
]
