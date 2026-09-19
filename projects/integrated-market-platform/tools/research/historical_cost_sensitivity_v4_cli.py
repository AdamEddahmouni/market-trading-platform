"""Lane E: Historical cost sensitivity v4 (freeze + bounded execute)."""

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
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v3 import (  # noqa: E402
    load_pinned_opend_build_v3,
)
from market_platform_foundation.intelligence.historical_research_harness.cost_sensitivity_v4 import (  # noqa: E402
    CANONICAL_COST_SENSITIVITY_V4_EVIDENCE_REL,
    HISTORICAL_COST_SENSITIVITY_V4,
    HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
    canonical_cost_sensitivity_v4_evidence_dir,
    promote_cost_sensitivity_v4_freeze_to_disk,
    publish_cost_sensitivity_v4_evidence_receipt,
    run_frozen_cost_sensitivity_v4,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-sha", help="Research code SHA for freeze promotion.")
    parser.add_argument("--promote-freeze", action="store_true", help="Write frozen_experiment_definition.json.")
    parser.add_argument("--execute", action="store_true", help="Run pre-registered cost grid.")
    parser.add_argument(
        "--publish-evidence",
        action="store_true",
        default=True,
        help="Write evidence/ receipts after execution (default: on).",
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
    print(f"EVIDENCE_LABEL: {HISTORICAL_COST_SENSITIVITY_V4}", file=sys.stderr)
    admission = evaluate_item9_prospective_corpus_admission(
        corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
    )
    if admission.get("disposition") != "REFUSED":
        print("historical authority must refuse Item 9 admission", file=sys.stderr)
        return 1

    evidence_dir = canonical_cost_sensitivity_v4_evidence_dir(ROOT)
    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen: dict

    if args.promote_freeze or not frozen_path.is_file():
        try:
            frozen_path, frozen, freeze_receipt = promote_cost_sensitivity_v4_freeze_to_disk(
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
                "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
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
            "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
            "EXPERIMENT_DEFINITION_FROZEN": "YES",
            "experiment_definition_hash": compute_experiment_definition_hash(frozen),
            "canonical_evidence_dir": CANONICAL_COST_SENSITIVITY_V4_EVIDENCE_REL,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    build = load_pinned_opend_build_v3(ROOT)
    pack_result = run_frozen_cost_sensitivity_v4(repository_root=ROOT, build=build, frozen_definition=frozen)
    if args.publish_evidence and pack_result.ok:
        publish_cost_sensitivity_v4_evidence_receipt(
            repository_root=ROOT,
            frozen_definition=frozen,
            pack_result=pack_result,
        )

    payload = {
        "ok": pack_result.ok,
        "stage": "execute",
        "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
        "experiment_definition_hash": pack_result.experiment_definition_hash,
        "pack_run_id": pack_result.pack_run_id,
        "reason_code": pack_result.reason_code,
        "component_sensitivity_table": pack_result.body.get("component_sensitivity_table"),
        "invariant_violations": pack_result.body.get("invariant_violations"),
        "contamination_status": (pack_result.body.get("contamination_audit") or {}).get("CONTAMINATION_STATUS"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if pack_result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
