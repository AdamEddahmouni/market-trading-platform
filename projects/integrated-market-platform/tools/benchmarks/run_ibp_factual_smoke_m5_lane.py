"""Lane M5 — IBP_FACTUAL_SMOKE_V1 pre-run gates, freeze, and single baseline run."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold import (  # noqa: E402
    FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS,
    admitted_artifacts_accessible,
    build_factual_blind_case_input,
    execute_factual_smoke_baseline,
    freeze_factual_smoke_run_configuration,
    load_candidate_factual_gold_protocol,
    validate_factual_gold_protocol,
)
from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold.factual_smoke_execution import (  # noqa: E402
    CONTEXT_RESET_POLICY,
)
from market_platform_foundation.intelligence.benchmark_protocol.facts_sut import run_ibp_facts_sut  # noqa: E402
from market_platform_foundation.intelligence.benchmark_protocol.sut_profiles import (  # noqa: E402
    IBP_FACTS_SUT_PROFILE_ID,
    IBP_FACTS_SUT_VERSION,
    resolve_sut_profile,
    sut_profile_documentation,
)
from market_platform_foundation.intelligence.benchmark_protocol.admitted_factual_gold.types import (  # noqa: E402
    IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
)

EVIDENCE_DIR = ROOT / "evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5"
FREEZE_FIXTURE = ROOT / "tests/fixtures/intelligence_benchmark/freeze/ibp_factual_smoke_v1_freeze.json"

EXPECTED_CASESET_HASH = "B3459E4F9D658687B12A6F8ABA4C81F15EEF51FFC05126A8B76698329C920A5C"
EXPECTED_GOLDSET_HASH = "9F5B9638470D92C5AA071F9190710CF0244839B414E538995883C7394A7A308F"
CANONICAL_SUT_CODE_SHA = "b43cfd5303dbcc5dd14cc5618c72b80c57b7db93"

TOOL_POLICY = {
    "llm_network": "DISABLED_BY_CONSTRUCTION",
    "tools_available": list(resolve_sut_profile(IBP_FACTS_SUT_PROFILE_ID).tools_available),
    "evaluator_gold_prefix_blocked": "evaluator_only/",
    "live_promotion": "FORBIDDEN",
}

EVALUATION_RULES = {
    "protocol_version": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
    "scored_subset_gate": "ANSWERABLE_FROM_ADMITTED_EVIDENCE",
    "excluded_case_ids": ["IBP-FACTUAL-EXCL-001"],
    "dimensions": [
        "facts",
        "freshness",
        "provenance",
        "unknown_handling",
        "routing",
        "final_state",
        "operator_close",
        "catastrophic",
    ],
    "structured_facts_preferred": True,
    "unknown_policy_encoded_in_evaluator_contract": True,
    "no_vanity_total_score": True,
}


def _answerable_cases(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in protocol.get("cases", [])
        if row.get("SCORING_GATE") == "ANSWERABLE_FROM_ADMITTED_EVIDENCE"
    ]


def evaluate_pre_run_gates(protocol: dict[str, Any]) -> dict[str, Any]:
    gates: dict[str, str] = {}
    reasons: dict[str, list[str]] = {}

    if protocol.get("gold_source_independent") is True and all(
        (row.get("PROVENANCE_REQUIREMENTS") or {}).get("gold_source_independent") is True
        for row in protocol.get("cases", [])
    ):
        gates["GOLD_SOURCE_INDEPENDENT"] = "PASS"
    else:
        gates["GOLD_SOURCE_INDEPENDENT"] = "FAIL"
        reasons["GOLD_SOURCE_INDEPENDENT"] = ["gold_source_independent_not_true"]

    freeze = protocol.get("freeze") or {}
    if freeze.get("status") == "FROZEN" and freeze.get("cases_constructed") is True:
        gates["GOLD_EVIDENCE_ADMITTED"] = "PASS"
    else:
        gates["GOLD_EVIDENCE_ADMITTED"] = "FAIL"
        reasons["GOLD_EVIDENCE_ADMITTED"] = ["protocol_not_frozen_or_cases_not_constructed"]

    answerable = _answerable_cases(protocol)
    excluded = [row for row in protocol.get("cases", []) if row.get("SCORING_GATE") == "EXCLUDED_UNANSWERABLE"]
    if len(answerable) == 11 and len(excluded) == 1 and excluded[0]["CASE_ID"] == "IBP-FACTUAL-EXCL-001":
        gates["CASES_ANSWERABLE"] = "PASS"
    else:
        gates["CASES_ANSWERABLE"] = "FAIL"
        reasons["CASES_ANSWERABLE"] = [
            f"answerable={len(answerable)} excluded={len(excluded)}",
        ]

    access_failures: list[str] = []
    for case in answerable:
        ok, missing = admitted_artifacts_accessible(ROOT, case["EVIDENCE_SET"])
        if not ok:
            access_failures.extend(missing)
        blind = build_factual_blind_case_input(case, context_reset_token="gate-check")
        response = run_ibp_facts_sut(blind, repository_root=ROOT)
        loaded = set(response.get("admitted_evidence_artifacts_loaded") or ())
        for ref in (case.get("EVIDENCE_SET") or {}).get("sources") or []:
            artifact_ref = str(ref.get("artifact_ref") or "")
            if artifact_ref and artifact_ref not in loaded:
                access_failures.append(artifact_ref)
    if access_failures:
        gates["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"] = "FAIL"
        reasons["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"] = sorted(set(access_failures))
    else:
        gates["SUT_CAN_ACCESS_REQUIRED_EVIDENCE"] = "PASS"

    gold_leaks: list[str] = []
    for case in protocol.get("cases", []):
        blind = build_factual_blind_case_input(case, context_reset_token="gold-gate")
        for key in FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS:
            if key in blind:
                gold_leaks.append(f"{case['CASE_ID']}:{key}")
    if gold_leaks:
        gates["SUT_CANNOT_ACCESS_GOLD"] = "FAIL"
        reasons["SUT_CANNOT_ACCESS_GOLD"] = gold_leaks
    else:
        gates["SUT_CANNOT_ACCESS_GOLD"] = "PASS"

    if CONTEXT_RESET_POLICY == "one_fresh_context_per_case_v1":
        gates["CONTEXT_RESET"] = "PASS"
    else:
        gates["CONTEXT_RESET"] = "FAIL"
        reasons["CONTEXT_RESET"] = ["unexpected_context_reset_policy"]

    if (
        protocol.get("caseset_hash") == EXPECTED_CASESET_HASH
        and protocol.get("goldset_hash") == EXPECTED_GOLDSET_HASH
        and protocol.get("protocol_version") == IBP_FACTUAL_SMOKE_PROTOCOL_VERSION
    ):
        gates["CONFIG_FROZEN"] = "PASS"
    else:
        gates["CONFIG_FROZEN"] = "FAIL"
        reasons["CONFIG_FROZEN"] = ["hash_or_protocol_version_mismatch"]

    overall = "PASS" if all(v == "PASS" for v in gates.values()) else "FAIL"
    return {"overall": overall, "gates": gates, "reasons": reasons}


def build_freeze_envelope(frozen_config: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    profile = resolve_sut_profile(IBP_FACTS_SUT_PROFILE_ID)
    return {
        "artifact_kind": "intelligence_benchmark_factual_smoke_freeze_v1",
        "lane_id": "IMP-IBP-FACTUAL-GOLD-V1-M5",
        "protocol_version": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "CASESET_VERSION": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "CASESET_HASH": frozen_config["caseset_hash"],
        "GOLDSET_VERSION": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "GOLDSET_HASH": frozen_config["goldset_hash"],
        "SUT_VERSION": IBP_FACTS_SUT_VERSION,
        "SUT_CODE_SHA": frozen_config["code_sha"],
        "SUT_PROFILE_ID": IBP_FACTS_SUT_PROFILE_ID,
        "TOOL_POLICY": TOOL_POLICY,
        "CONTEXT_RESET_POLICY": CONTEXT_RESET_POLICY,
        "EVALUATION_RULES": EVALUATION_RULES,
        "pre_run_gates": gates,
        "frozen_config": frozen_config,
        "sut_profile_documentation": sut_profile_documentation(profile, code_sha=frozen_config["code_sha"]),
        "legacy_smoke10_run_id_preserved": "ibp-smoke10-76DDD188CD080365",
        "full30_executed": False,
        "ITEM9_CALIBRATED": "NO",
        "PR222_ISOLATED": True,
        "LIVE_OFF": True,
        "FTEP_EMPIRICAL_ACTIVE": "NO",
    }


def summarize_dimensions(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_dimension: dict[str, Counter[str]] = {dim: Counter() for dim in EVALUATION_RULES["dimensions"]}
    by_fact_verdict: Counter[str] = Counter()
    by_failure_type: Counter[str] = Counter()
    for row in case_results:
        dims = row.get("dimension_scores") or {}
        for dim in EVALUATION_RULES["dimensions"]:
            verdict = dims.get(dim, "MISSING")
            by_dimension[dim][verdict] += 1
        for fv in row.get("fact_verdicts") or []:
            by_fact_verdict[str(fv.get("verdict"))] += 1
        for reason in row.get("failure_reasons") or []:
            by_failure_type[str(reason).split(":")[0]] += 1
    return {
        "by_dimension": {k: dict(v) for k, v in by_dimension.items()},
        "by_fact_verdict": dict(by_fact_verdict),
        "by_failure_type": dict(by_failure_type),
    }


def build_receipt(
    *,
    run_record: dict[str, Any],
    freeze_envelope: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any]:
    summaries = summarize_dimensions(run_record.get("case_results") or [])
    return {
        "artifact_kind": "intelligence_benchmark_factual_smoke_evidence_receipt_v1",
        "lane_id": "IMP-IBP-FACTUAL-GOLD-V1-M5",
        "evidence_label": "HISTORICAL_DEVELOPMENT_FACTUAL_SMOKE_V1_BASELINE",
        "RUN_ID": run_record["run_id"],
        "CASE_COUNT": run_record["case_count"],
        "SCORES_EXECUTED": "YES" if run_record.get("scores_executed") else "NO",
        "FULL30_EXECUTED": "NO",
        "smoke10_executed": False,
        "protocol_version": IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
        "frozen_config_fingerprint": run_record["frozen_config_fingerprint"],
        "pre_run_gates": gates,
        "contamination_audit": run_record.get("contamination_audit"),
        "comparison_note_vs_legacy_smoke10": (
            "Structural comparison only: legacy ibp-smoke10-76DDD188CD080365 used synthetic "
            "evaluator gold and deterministic UNKNOWN stub SUT; IBP_FACTUAL_SMOKE_V1 uses "
            "admitted-evidence factual gold and imp_historical_routing_grounded_facts_v1. "
            "Not an apples-to-apples intelligence delta."
        ),
        "ITEM9_CALIBRATED": "NO",
        "PR222_ISOLATED": True,
        "LIVE_OFF": True,
        "FTEP_EMPIRICAL_ACTIVE": "NO",
        "frozen_evidence_unchanged": True,
        "MERGE_PERFORMED": "NO",
        "summaries": summaries,
        "freeze_envelope_path": "tests/fixtures/intelligence_benchmark/freeze/ibp_factual_smoke_v1_freeze.json",
        "factual_smoke_run_record_path": (
            "evidence/intelligence-benchmark/imp-ibp-factual-gold-v1-lane-m5/factual_smoke_run_record.json"
        ),
    }


def phase_freeze() -> dict[str, Any]:
    protocol = load_candidate_factual_gold_protocol(ROOT)
    validate_factual_gold_protocol(protocol, allow_empty_cases=False)
    gates = evaluate_pre_run_gates(protocol)
    frozen = freeze_factual_smoke_run_configuration(
        ROOT,
        code_sha=CANONICAL_SUT_CODE_SHA,
        sut_profile_id=IBP_FACTS_SUT_PROFILE_ID,
    )
    envelope = build_freeze_envelope(frozen, gates)
    FREEZE_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_FIXTURE.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "pre_run_gates.json").write_text(
        json.dumps(gates, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "frozen_config.json").write_text(
        json.dumps(frozen, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"gates": gates, "frozen": frozen, "envelope": envelope}


def phase_run(frozen: dict[str, Any], gates: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    if gates["overall"] != "PASS":
        return {"RUN_ID": "NOT_EXECUTED", "REASON": "PRE_RUN_GATES_FAILED", "gates": gates}

    def sut_runner(blind_input: dict[str, Any]) -> dict[str, Any]:
        return run_ibp_facts_sut(blind_input, repository_root=ROOT)

    record = execute_factual_smoke_baseline(
        ROOT,
        frozen_config=frozen,
        sut_runner=sut_runner,
        artifact_root=EVIDENCE_DIR,
    )
    (EVIDENCE_DIR / "factual_smoke_run_record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "contamination_audit.json").write_text(
        json.dumps(record["contamination_audit"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = build_receipt(run_record=record, freeze_envelope=envelope, gates=gates)
    (EVIDENCE_DIR / "factual_smoke_baseline_evidence_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "run", "all"), default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    frozen_payload: dict[str, Any] | None = None
    gates: dict[str, Any] | None = None
    envelope: dict[str, Any] | None = None

    if args.phase in {"freeze", "all"}:
        payload = phase_freeze()
        gates = payload["gates"]
        frozen_payload = payload["frozen"]
        envelope = payload["envelope"]
        if args.phase == "freeze":
            out = {"phase": "freeze", "gates": gates, "frozen_config_fingerprint": frozen_payload["frozen_config_fingerprint"]}
            print(json.dumps(out, indent=2, sort_keys=True) if args.json else json.dumps(out))
            return 0 if gates["overall"] == "PASS" else 1

    if args.phase in {"run", "all"}:
        if frozen_payload is None or gates is None or envelope is None:
            frozen_payload = json.loads((EVIDENCE_DIR / "frozen_config.json").read_text(encoding="utf-8"))
            gates = json.loads((EVIDENCE_DIR / "pre_run_gates.json").read_text(encoding="utf-8"))
            envelope = json.loads(FREEZE_FIXTURE.read_text(encoding="utf-8"))
        receipt = phase_run(frozen_payload, gates, envelope)
        print(json.dumps(receipt, indent=2, sort_keys=True) if args.json else json.dumps(receipt))
        if receipt.get("RUN_ID") == "NOT_EXECUTED":
            return 1
        audit = receipt.get("contamination_audit") or {}
        return 0 if audit.get("overall") == "PASS" else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
