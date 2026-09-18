"""One-off generator for IBP suite catalog fixtures (dev tooling)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests/fixtures/intelligence_benchmark"
GOLD_ROOT = FIXTURE_ROOT / "evaluator_only/gold"
MODES = ["A", "B", "C", "D", "E"]


def main() -> None:
    GOLD_ROOT.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []
    for index in range(1, 31):
        case_id = f"IBP-CASE-{index:03d}"
        mode = MODES[(index - 1) % 5]
        gold_ref = f"evaluator_only/gold/{case_id}.json"
        gold_path = FIXTURE_ROOT / gold_ref
        gold_path.write_text(
            json.dumps(
                {
                    "case_id": case_id,
                    "authority": "EVALUATOR_ONLY",
                    "gold_answer": f"synthetic-gold-{index:03d}",
                    "do_not_expose_to_sut": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        entry: dict = {
            "case_id": case_id,
            "blind_mode": mode,
            "input_profile": "synthetic_intelligence_fixture_v1",
            "evaluator_gold_ref": gold_ref,
        }
        if index == 1:
            entry["historical_harness_fixture"] = (
                "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
            )
        cases.append(entry)
    catalog = {
        "schema_version": "imp.intelligence-benchmark-suite/1.0.0",
        "protocol_id": "imp-intelligence-benchmark-protocol-v1",
        "suite_id": "ibp-v1-30",
        "description": "Minimal IBP v1 catalog (30 cases; evaluator gold isolated)",
        "cases": cases,
        "smoke10_case_ids": [row["case_id"] for row in cases[:10]],
    }
    (FIXTURE_ROOT / "ibp_suite_catalog_v1.json").write_text(
        json.dumps(catalog, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
