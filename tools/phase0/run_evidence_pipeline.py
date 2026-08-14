"""Finalize a preselected Phase 0 evidence content map."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict, write_canonical_json
from market_platform_foundation.evidence import publish_artifacts
from market_platform_foundation.offline_guard import install_guard


def main() -> int:
    events: list[dict[str, str]] = []
    install_guard(events)
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-map", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    args = parser.parse_args()
    content_map = load_json_strict(Path(args.content_map))
    if not isinstance(content_map, dict):
        raise SystemExit("content map must be an object")
    artifacts = [(logical_id, content) for logical_id, content in content_map.items()]
    output_dir = Path(args.output_dir)
    index = publish_artifacts(
        output_dir,
        artifacts,
        {
            "procedure_versions": {"evidence_writer": "1.0.0"},
            "source_manifest_sha256": args.source_manifest_sha256,
        },
    )
    write_canonical_json(output_dir / "pre-evaluation-evidence-index.json", {"artifacts": index})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
