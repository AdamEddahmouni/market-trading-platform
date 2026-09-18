"""Lane R2: Frozen OpenD Historical Baseline Pack v2 (definition only; no execution)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    historical_research_governance_lines,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v2 import (  # noqa: E402
    CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL,
    HISTORICAL_BASELINE_PACK_V2,
    canonical_baseline_pack_v2_evidence_dir,
    compute_experiment_definition_hash,
    freeze_baseline_pack_v2_definition_to_disk,
    verify_frozen_experiment_definition,
    verify_pinned_opend_corpus_fingerprint,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-pin",
        type=Path,
        help="Pinned corpus directory (defaults to git-tracked evidence corpus_pin).",
    )
    parser.add_argument(
        "--code-sha",
        help="Research code SHA recorded in the frozen definition (defaults to runtime git SHA).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify dataset fingerprint against pinned corpus only.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in historical_research_governance_lines():
        print(line, file=sys.stderr)
    print(f"EVIDENCE_LABEL: {HISTORICAL_BASELINE_PACK_V2}", file=sys.stderr)
    admission = evaluate_item9_prospective_corpus_admission(
        corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
    )
    if admission.get("disposition") != "REFUSED":
        print("historical authority must refuse Item 9 admission", file=sys.stderr)
        return 1

    evidence_dir = canonical_baseline_pack_v2_evidence_dir(ROOT)
    corpus_pin = args.corpus_pin or (evidence_dir / "corpus_pin")
    fingerprint = verify_pinned_opend_corpus_fingerprint(repository_root=ROOT, corpus_dir=corpus_pin)
    if args.verify_only:
        print(json.dumps({"ok": fingerprint.get("ok"), "fingerprint_verification": fingerprint}, indent=2, sort_keys=True))
        return 0 if fingerprint.get("ok") else 1

    if not fingerprint.get("ok"):
        print(
            json.dumps(
                {"ok": False, "stage": "dataset_fingerprint", "fingerprint_verification": fingerprint},
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    try:
        frozen_path, frozen, receipt = freeze_baseline_pack_v2_definition_to_disk(
            repository_root=ROOT,
            corpus_dir=corpus_pin,
            artifact_root=evidence_dir,
            code_sha=args.code_sha,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "stage": "freeze", "reason_code": str(exc)}, indent=2, sort_keys=True))
        return 1

    verify = verify_frozen_experiment_definition(frozen)
    if not verify.get("ok"):
        print(json.dumps({"ok": False, "stage": "verify_frozen_definition", "verify": verify}, indent=2, sort_keys=True))
        return 1

    payload = {
        "ok": True,
        "stage": "freeze",
        "evidence_label": HISTORICAL_BASELINE_PACK_V2,
        "EXPERIMENT_DEFINITION_FROZEN": receipt["EXPERIMENT_DEFINITION_FROZEN"],
        "execution_status": receipt["execution_status"],
        "performance_run": receipt["performance_run"],
        "experiment_definition_hash": compute_experiment_definition_hash(frozen),
        "dataset_fingerprint": receipt["dataset_fingerprint"],
        "frozen_definition_path": str(frozen_path.relative_to(ROOT)),
        "canonical_evidence_dir": CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL,
        "fingerprint_verification": fingerprint,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
