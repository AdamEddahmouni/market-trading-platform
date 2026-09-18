"""Lane R3: OpenD Historical Baseline Pack v3 (freeze promote + execute)."""

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
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (  # noqa: E402
    compute_experiment_definition_hash,
    verify_frozen_experiment_definition,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v2 import (  # noqa: E402
    verify_pinned_opend_corpus_fingerprint,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v3 import (  # noqa: E402
    CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL,
    HISTORICAL_BASELINE_PACK_V3,
    canonical_baseline_pack_v3_evidence_dir,
    load_pinned_opend_build_v3,
    promote_pre_execution_v3_freeze_to_disk,
    publish_baseline_pack_v3_evidence_receipt,
    run_frozen_historical_baseline_pack_v3,
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
        help="Pinned corpus directory (defaults to git-tracked v3 evidence corpus_pin).",
    )
    parser.add_argument(
        "--code-sha",
        help="Research code SHA for freeze promotion (defaults to runtime git SHA).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify dataset fingerprint against pinned corpus only.",
    )
    parser.add_argument(
        "--promote-freeze",
        action="store_true",
        help="Promote pre_execution_frozen_experiment_definition.json to frozen (Lane A landed).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run frozen baseline pack once (+ one full deterministic rerun).",
    )
    parser.add_argument(
        "--publish-evidence",
        action="store_true",
        default=True,
        help="Write git-tracked evidence/ receipts after execution (default: on).",
    )
    parser.add_argument(
        "--no-publish-evidence",
        action="store_false",
        dest="publish_evidence",
        help="Skip writing evidence/ receipts after execution.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in historical_research_governance_lines():
        print(line, file=sys.stderr)
    print(f"EVIDENCE_LABEL: {HISTORICAL_BASELINE_PACK_V3}", file=sys.stderr)
    admission = evaluate_item9_prospective_corpus_admission(
        corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
    )
    if admission.get("disposition") != "REFUSED":
        print("historical authority must refuse Item 9 admission", file=sys.stderr)
        return 1

    evidence_dir = canonical_baseline_pack_v3_evidence_dir(ROOT)
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

    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen: dict

    if args.promote_freeze or not frozen_path.is_file():
        try:
            frozen_path, frozen, freeze_receipt = promote_pre_execution_v3_freeze_to_disk(
                repository_root=ROOT,
                code_sha=args.code_sha,
            )
        except ValueError as exc:
            print(json.dumps({"ok": False, "stage": "promote_freeze", "reason_code": str(exc)}, indent=2, sort_keys=True))
            return 1
        if not args.execute:
            payload = {
                "ok": True,
                "stage": "promote_freeze",
                "experiment_definition_hash": frozen["experiment_definition_hash"],
                "freeze_receipt": freeze_receipt,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
    else:
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))

    verify = verify_frozen_experiment_definition(frozen)
    if not verify.get("ok"):
        print(json.dumps({"ok": False, "stage": "verify_frozen_definition", "verify": verify}, indent=2, sort_keys=True))
        return 1

    if not args.execute:
        payload = {
            "ok": True,
            "stage": "freeze",
            "evidence_label": HISTORICAL_BASELINE_PACK_V3,
            "EXPERIMENT_DEFINITION_FROZEN": "YES",
            "experiment_definition_hash": compute_experiment_definition_hash(frozen),
            "dataset_fingerprint": (frozen.get("dataset") or {}).get("dataset_fingerprint"),
            "frozen_definition_path": str(frozen_path.relative_to(ROOT)),
            "canonical_evidence_dir": CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL,
            "fingerprint_verification": fingerprint,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    build = load_pinned_opend_build_v3(ROOT)
    pack_result = run_frozen_historical_baseline_pack_v3(
        repository_root=ROOT,
        build=build,
        frozen_definition=frozen,
        deterministic_rerun=True,
    )
    evidence_receipt_path = None
    if pack_result.ok and args.publish_evidence:
        evidence_receipt_path = publish_baseline_pack_v3_evidence_receipt(
            repository_root=ROOT,
            frozen_definition=frozen,
            pack_result=pack_result,
        )

    contamination = pack_result.body.get("contamination_audit") if pack_result.ok else None
    payload = {
        "ok": pack_result.ok,
        "stage": "execute",
        "evidence_label": HISTORICAL_BASELINE_PACK_V3,
        "observation_language": "BOUNDED_HISTORICAL_OBSERVATION",
        "pack_run_id": pack_result.pack_run_id,
        "experiment_definition_hash": pack_result.experiment_definition_hash,
        "dataset_fingerprint": pack_result.dataset_fingerprint,
        "baseline_results": pack_result.body.get("baseline_results") if pack_result.ok else None,
        "contamination_audit": contamination,
        "reproducibility": pack_result.body.get("reproducibility") if pack_result.ok else None,
        "artifact_dir": str(pack_result.artifact_dir) if pack_result.ok else None,
        "evidence_receipt_path": str(evidence_receipt_path) if evidence_receipt_path else None,
        "reason_code": pack_result.reason_code,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if pack_result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
