"""Paper/Demo Phase-6 preregistration persist+load for the Path A hop.

Create is a separate operator step. The hop only loads a previously persisted
record when identity matches and ``registered_at`` is before quote
``event_time_ns``. Catalog evaluators never call ``build_preregistration``.
A scanner MATCHED is not item 7 PROVED: ``forecast_resolver`` stays None and
Path A returns ``FORECAST_UNAVAILABLE`` rather than minting from a fixture
ForecastV1.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import StrategyMatchDisposition
from market_platform_foundation.strategy.evaluation import (
    default_forecast_momentum_spec,
    default_whale_aligned_spec,
)
from market_platform_foundation.strategy.path_a_preregistration_store import (
    load_paper_demo_preregistrations,
    persist_paper_demo_preregistration,
    select_eligible_preregistration,
)
from market_platform_foundation.strategy.path_a_prospective import (
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCallerError
from market_platform_foundation.strategy.preregistration import verify_preregistration

T = 1_700_000_000_000_000_000
EARLY_REGISTERED_AT = "2020-01-01T00:00:00.000000000Z"
LATE_REGISTERED_AT = "2026-08-16T00:00:00.000000000Z"


def _quote_event(*, last_price: float = 190.1, event_time_ns: int = T) -> dict:
    return {
        "raw_payload": {"last_price": last_price},
        "clocks": {"event_time_ns": event_time_ns},
    }


class PathAPreregistrationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_operator_persist_stamps_registered_at_before_any_hop(self) -> None:
        spec = default_forecast_momentum_spec()
        record = persist_paper_demo_preregistration(
            spec, registered_at=EARLY_REGISTERED_AT, destination=self.store
        )
        self.assertEqual(record["registered_at"], EARLY_REGISTERED_AT)
        status, reasons = verify_preregistration(record, spec)
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])
        loaded = load_paper_demo_preregistrations(self.store)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["preregistration_record_hash"], record["preregistration_record_hash"])

    def test_select_requires_identity_match_and_registered_at_before_quote(self) -> None:
        spec = default_forecast_momentum_spec()
        other = default_whale_aligned_spec()
        matching = persist_paper_demo_preregistration(
            spec, registered_at=EARLY_REGISTERED_AT, destination=self.store / "match.json"
        )
        late = persist_paper_demo_preregistration(
            spec, registered_at=LATE_REGISTERED_AT, destination=self.store / "late.json"
        )
        selected = select_eligible_preregistration(
            spec, (matching,), quote_event_time_ns=T
        )
        self.assertEqual(
            selected["preregistration_record_hash"], matching["preregistration_record_hash"]
        )
        self.assertIsNone(select_eligible_preregistration(spec, (late,), quote_event_time_ns=T))
        self.assertIsNone(select_eligible_preregistration(other, (matching,), quote_event_time_ns=T))
        from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns

        self.assertEqual(iso_to_epoch_ns("2023-11-14T22:13:20.000000000Z"), T)
        same_tick = persist_paper_demo_preregistration(
            spec,
            registered_at="2023-11-14T22:13:20.000000000Z",
            destination=self.store / "same-tick.json",
        )
        self.assertIsNone(
            select_eligible_preregistration(spec, (same_tick,), quote_event_time_ns=T)
        )

    def test_tampered_record_is_not_eligible(self) -> None:
        spec = default_forecast_momentum_spec()
        record = persist_paper_demo_preregistration(
            spec, registered_at=EARLY_REGISTERED_AT, destination=self.store / "ok.json"
        )
        tampered = dict(record)
        tampered["principal_id"] = "NOT-THE-PRINCIPAL"
        self.assertIsNone(
            select_eligible_preregistration(spec, (tampered,), quote_event_time_ns=T)
        )

    def test_missing_or_corrupt_store_is_empty(self) -> None:
        self.assertEqual(load_paper_demo_preregistrations(self.store / "missing.json"), ())
        bad = self.store / "bad.json"
        bad.write_text("{not-json", encoding="utf-8")
        self.assertEqual(load_paper_demo_preregistrations(bad), ())


class PathAPreregistrationLoadHopTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_catalog_evaluators_never_call_build_preregistration(self) -> None:
        from market_platform_foundation.strategy import path_a_strategy_catalog

        source = inspect.getsource(path_a_strategy_catalog)
        self.assertNotIn("build_preregistration(", source)
        self.assertNotIn("from .preregistration import", source)
        self.assertIn("preregistration=None", source)

    def test_absent_store_keeps_preregistration_none_and_abstains(self) -> None:
        invoke = build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
            quote_event=_quote_event(),
            preregistration_path=self.store,
        )
        scan = invoke.caller.scanner.run(invoke.scan_request)
        self.assertTrue(scan.matches)
        self.assertTrue(
            all(row.disposition == StrategyMatchDisposition.ABSTAINED for row in scan.matches)
        )
        self.assertTrue(
            any("ABSTAIN_NO_PREREGISTRATION" in row.abstention_reasons for row in scan.matches)
        )
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "EMPTY")
        self.assertEqual(result.reason_codes, ("NO_MATCHED_STRATEGY",))

    def test_load_eligible_forecast_momentum_scanner_matched_is_not_oe_emit(self) -> None:
        """Load+PASS can produce a scanner MATCHED. That is not item 7 PROVED.

        ``forecast_resolver`` still returns None, so Path A is
        FORECAST_UNAVAILABLE. Tests must not inject a fixture ForecastV1.
        """

        spec = default_forecast_momentum_spec()
        persist_paper_demo_preregistration(
            spec, registered_at=EARLY_REGISTERED_AT, destination=self.store
        )
        invoke = build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
            quote_event=_quote_event(),
            preregistration_path=self.store,
        )
        self.assertEqual(
            invoke.scan_request.capability_snapshot.context["honesty"],
            "LOADED_PHASE6_PREREGISTRATION",
        )
        scan = invoke.caller.scanner.run(invoke.scan_request)
        matched = [
            row for row in scan.matches if row.disposition == StrategyMatchDisposition.MATCHED
        ]
        self.assertEqual([row.strategy_id for row in matched], ["path-a-baseline-forecast-momentum"])
        whales = [
            row
            for row in scan.matches
            if row.strategy_id != "path-a-baseline-forecast-momentum"
        ]
        self.assertTrue(whales)
        self.assertTrue(
            all(row.disposition == StrategyMatchDisposition.ABSTAINED for row in whales)
        )
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.reason_codes, ("FORECAST_RESOLUTION_FAILED",))
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.opportunities, ())
        self.assertEqual(result.assessments, ())
        self.assertIsNone(invoke.caller.forecast_resolver(matched[0]))
        from market_platform_foundation.strategy import path_a_prospective

        self.assertIn("forecast_resolver=lambda _match: None", inspect.getsource(path_a_prospective))

    def test_late_registration_abstains(self) -> None:
        spec = default_forecast_momentum_spec()
        persist_paper_demo_preregistration(
            spec, registered_at=LATE_REGISTERED_AT, destination=self.store
        )
        invoke = build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
            quote_event=_quote_event(),
            preregistration_path=self.store,
        )
        scan = invoke.caller.scanner.run(invoke.scan_request)
        self.assertTrue(
            all(row.disposition == StrategyMatchDisposition.ABSTAINED for row in scan.matches)
        )
        self.assertEqual(
            invoke.scan_request.capability_snapshot.context["honesty"],
            "NO_PREREGISTRATION_AUTHORITY_FOR_PATH_A_HOP",
        )

    def test_identity_mismatch_abstains(self) -> None:
        persist_paper_demo_preregistration(
            default_whale_aligned_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.store,
        )
        invoke = build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
            quote_event=_quote_event(),
            preregistration_path=self.store,
        )
        momentum = [
            row
            for row in invoke.caller.scanner.run(invoke.scan_request).matches
            if row.strategy_id == "path-a-baseline-forecast-momentum"
        ]
        self.assertEqual(len(momentum), 1)
        self.assertEqual(momentum[0].disposition, StrategyMatchDisposition.ABSTAINED)
        self.assertIn("ABSTAIN_NO_PREREGISTRATION", momentum[0].abstention_reasons)

    def test_no_quote_event_time_does_not_load(self) -> None:
        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.store,
        )
        invoke = build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
            preregistration_path=self.store,
        )
        self.assertEqual(
            invoke.scan_request.capability_snapshot.context["honesty"],
            "NO_PREREGISTRATION_AUTHORITY_FOR_PATH_A_HOP",
        )

    def test_live_still_forbidden_with_store(self) -> None:
        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.store,
        )
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke(
                "AAPL",
                mode="live",
                as_of_time_ns=T,
                quote_event=_quote_event(),
                preregistration_path=self.store,
            )

    def test_composer_auto_build_loads_from_store_without_fixture_forecast(self) -> None:
        from market_platform_foundation.providers.contracts import ProviderResult

        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.store,
        )
        event = {
            "capability": "US_EQUITY_L1",
            "clocks": {
                "event_time_ns": T,
                "provider_time_ns": T,
                "received_time_ns": T + 1_000_000,
            },
            "instrument_id": "AAPL",
            "provider": "test.realtime",
            "provider_symbol": "AAPL",
            "raw_payload": {
                "ask_price": 190.2,
                "ask_vol": 200,
                "bid_price": 190.0,
                "bid_vol": 100,
                "last_price": 190.1,
            },
            "sequence": 7,
            "timeliness": "REAL_TIME",
            "normalization_version": "test/1.0.0",
        }
        fetched = ProviderResult(
            status="available",
            events=(event,),
            provider_id="test.realtime",
            capability="US_EQUITY_SNAPSHOT",
        )

        class _Scripted:
            capability = "US_EQUITY_SNAPSHOT"
            provider_id = "test.realtime"

            def fetch_quote(self, symbol: str) -> ProviderResult:
                del symbol
                return fetched

        result = PathAProspectiveComposer(
            quote_provider=_Scripted(),
            preregistration_path=self.store,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.path_a.matched_count, 1)
        self.assertEqual(result.path_a.opportunities, ())
        self.assertNotEqual(result.path_a.status, "MINTED")

    def test_cli_flag_is_additive_and_does_not_change_quote_provider(self) -> None:
        from tools import path_a_prospective_run

        source = inspect.getsource(path_a_prospective_run.main)
        self.assertIn("--preregistration-path", source)
        self.assertIn("preregistration_path", source)
        self.assertIn("discover_equity_quote_stack", source)
        self.assertNotIn("quote_provider=", source.split("discover_equity_quote_stack", 1)[0])
        self.assertNotIn("ForecastV1", source)


if __name__ == "__main__":
    unittest.main()
