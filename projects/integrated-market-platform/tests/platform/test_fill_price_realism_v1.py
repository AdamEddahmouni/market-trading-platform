"""Fill-price realism v1 harness (Lane F)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_FOREIGN_MANIFEST = (
    r"C:\Users\adame\Desktop\market-trading-platform\.worktrees\opend-fill-economics-v3"
    r"\projects\integrated-market-platform\artifacts\historical-research-harness"
    r"\baseline-pack-v3\runs\48D2248BDD4EFA0A7F1286783B004281F4E5C049C129AD91435CBAB7D760B3A4"
    r"\run_manifest.json"
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.historical_research_harness.fill_price_realism_harness import (  # noqa: E402
    reprice_locked_fills,
    resolve_v3_baseline_run_dir,
    run_frozen_fill_price_realism_v1,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (  # noqa: E402
    verify_frozen_experiment_definition,
)

POLICY = {
    "commission_minor_per_share": 0,
    "fee_minor_per_order": 0,
    "initial_cash_minor": 1_000_000_00,
    "price_scale": 100,
}


def _bar(
    *,
    time_ns: int,
    open_: str,
    high: str,
    low: str,
    close: str,
) -> dict:
    return {
        "available_time": time_ns,
        "event_type": "BAR_OHLCV_1M",
        "instrument_id": "canonical:EQUITY:XNAS:TEST",
        "bar_payload": {"open": open_, "high": high, "low": low, "close": close, "volume": 1000},
    }


class FillPriceRealismUnitTests(unittest.TestCase):
    def test_reprice_adverse_vs_open_changes_gross(self) -> None:
        events = [
            _bar(time_ns=100, open_="10.0", high="10.5", low="9.5", close="10.2"),
            _bar(time_ns=200, open_="10.2", high="10.8", low="10.0", close="10.4"),
        ]
        fills = [
            {
                "direction": "long",
                "fill_id": "a",
                "fill_price_minor": 1050,
                "fill_quantity": 10,
                "fill_time": 100,
                "instrument_id": "canonical:EQUITY:XNAS:TEST",
            },
            {
                "direction": "short",
                "fill_id": "b",
                "fill_price_minor": 1040,
                "fill_quantity": 10,
                "fill_time": 200,
                "instrument_id": "canonical:EQUITY:XNAS:TEST",
            },
        ]
        adverse = reprice_locked_fills(
            fills,
            events=events,
            fill_price_reference="BAR_ADVERSE_TOUCH",
            mtm_reference="MTM_LAST_BAR_CLOSE",
            cost_slippage_bps=0.0,
            policy=POLICY,
        )
        at_open = reprice_locked_fills(
            fills,
            events=events,
            fill_price_reference="BAR_OPEN",
            mtm_reference="MTM_LAST_BAR_CLOSE",
            cost_slippage_bps=0.0,
            policy=POLICY,
        )
        self.assertNotEqual(adverse["gross_pnl"], at_open["gross_pnl"])
        self.assertEqual(adverse["fill_count"], 2)

    def test_resolve_v3_run_dir_from_sibling_worktree(self) -> None:
        run_id = "4A1EF4884FB0699B2568A6D6EE67B384AD904B3EFD5903F997AE4ACD8C09E214"
        resolved = resolve_v3_baseline_run_dir(ROOT, run_id=run_id, manifest_path=None)
        if resolved is None:
            self.skipTest("v3 run artifacts not present on this host")
        self.assertTrue((resolved / "predictions.json").is_file())

    def test_resolve_v3_foreign_windows_manifest_path_no_oserror(self) -> None:
        missing_run_id = "0" * 64
        try:
            resolved = resolve_v3_baseline_run_dir(
                ROOT,
                run_id=missing_run_id,
                manifest_path=_FOREIGN_MANIFEST,
            )
        except OSError as exc:
            self.fail(f"resolve_v3_baseline_run_dir must not raise OSError: {exc}")
        if sys.platform != "win32":
            self.assertIsNone(resolved)


class FillPriceRealismIntegrationTests(unittest.TestCase):
    def test_frozen_definition_hash_stable(self) -> None:
        import json

        frozen_path = (
            ROOT
            / "evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1"
            / "frozen_experiment_definition.json"
        )
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        verify = verify_frozen_experiment_definition(frozen)
        self.assertTrue(verify.get("ok"))
        self.assertEqual(
            verify["experiment_definition_hash"],
            "C4FCD3AB6CA6AEE57C91A0D709EC8D77EBFA6AA774542BF9AAD9FC761C2D1149",
        )

    def test_bounded_run_when_v3_artifacts_present(self) -> None:
        import json

        frozen_path = (
            ROOT
            / "evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1"
            / "frozen_experiment_definition.json"
        )
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        evidence_receipt = (
            ROOT
            / "evidence/historical-research/imp-integrate-experiment-06-r1-opend-fill-price-realism-v1"
            / "fill_price_realism_evidence_receipt.json"
        )
        evidence_run = evidence_receipt.parent / "fill_price_realism_run_record.json"
        receipt_mtime = evidence_receipt.stat().st_mtime_ns if evidence_receipt.is_file() else None
        run_mtime = evidence_run.stat().st_mtime_ns if evidence_run.is_file() else None
        result = run_frozen_fill_price_realism_v1(
            repository_root=ROOT,
            frozen_definition=frozen,
            persist_canonical_evidence=False,
        )
        if result.reason_code == "V3_FILL_SCHEDULE_RUN_DIR_UNAVAILABLE":
            self.skipTest("v3 local run dirs unavailable")
        self.assertTrue(result.ok, msg=result.reason_code)
        if receipt_mtime is not None:
            self.assertEqual(evidence_receipt.stat().st_mtime_ns, receipt_mtime)
        if run_mtime is not None:
            self.assertEqual(evidence_run.stat().st_mtime_ns, run_mtime)
        self.assertTrue(result.pack_run_id)
        baseline_rows = result.body.get("results") or []
        self.assertEqual(len(baseline_rows), 4)
        for row in baseline_rows:
            self.assertEqual(len(row.get("arms") or []), 6)


if __name__ == "__main__":
    unittest.main()
