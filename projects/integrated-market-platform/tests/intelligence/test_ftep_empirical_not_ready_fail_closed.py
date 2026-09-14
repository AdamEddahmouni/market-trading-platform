"""Fail-closed FTEP promotion guards for software-only hop leftovers.

Leftover FETCHED Finviz tokens, US_EQUITY_RTH closure (MARKET_CLOSED gates),
missing PRODUCTION contributor JSON, and software MATCHED Path A mints must not
flip program labels ``EMPIRICAL_ACTIVE`` or declare simulator ``CALIBRATED``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (  # noqa: E402
    collect_ftep_campaign_status,
)
from market_platform_foundation.intelligence.paper_forward_bridge.session_policy import (  # noqa: E402
    CALENDAR_US_EQUITY_RTH,
)
from market_platform_foundation.local_state.paths import REPO_ROOT  # noqa: E402
from market_platform_foundation.paper.calibration.runner import (  # noqa: E402
    STATUS_WAITING_FOR_MARKET,
    run_calibration_campaign,
)
from market_platform_foundation.providers.contracts import ProviderResult  # noqa: E402
from market_platform_foundation.strategy.evaluation import default_forecast_momentum_spec  # noqa: E402
from market_platform_foundation.strategy.path_a_forecast_producer import (  # noqa: E402
    load_paper_demo_contributors,
    produce_paper_demo_forecast,
)
from market_platform_foundation.strategy.path_a_preregistration_store import (  # noqa: E402
    persist_paper_demo_preregistration,
)
from market_platform_foundation.strategy.path_a_prospective import (  # noqa: E402
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)

T = 1_700_000_000_000_000_000
EARLY_REGISTERED_AT = "2020-01-01T00:00:00.000000000Z"
CAMPAIGN = "FTEP-V1-002"


def _realtime_event() -> dict:
    return {
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


class _RealtimeQuoteProvider:
    capability = "US_EQUITY_SNAPSHOT"
    provider_id = "test.realtime"

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        return ProviderResult(
            status="available",
            events=(_realtime_event(),),
            provider_id="test.realtime",
            capability="US_EQUITY_SNAPSHOT",
        )


def assert_no_ftep_empirical_promotion(serialized: str) -> None:
    if "EMPIRICAL_ACTIVE" in serialized:
        raise AssertionError("serialized payload claims FTEP EMPIRICAL_ACTIVE")
    compact = serialized.replace(" ", "")
    if '"calibrated":true' in compact or '"empirical_active":true' in compact:
        raise AssertionError("serialized payload claims CALIBRATED or empirical_active=true")


def assert_ftep_campaign_still_not_empirical(repository_root: Path, campaign_slug: str) -> None:
    payload = collect_ftep_campaign_status(repository_root, campaign_slug)
    assert payload["governed_session_count"] == 0, payload
    assert payload["empirical_lock_count"] == 0, payload
    dumped = json.dumps(payload)
    assert_no_ftep_empirical_promotion(dumped)


class FtepEmpiricalNotReadyFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_leftover_fetched_overlay_hop_output_has_no_ftep_promotion(self) -> None:
        from market_platform_foundation.providers.finviz_context_discovery import (
            discover_finviz_context_stack,
        )
        from market_platform_foundation.providers.adapters.finviz_elite_context import (
            overlay_payload,
        )
        from tools.path_a_prospective_run import main as path_a_cli_main

        env = {
            "FINVIZ_API_KEY": "",
            "FINVIZ_AUTH_TOKEN": "",
            "FINVIZ_API_TOKEN": "",
            "FINVIZ_ELITE_TOKEN": "",
            "IMP_FINVIZ_ELITE_TOKEN": "",
            "IMP_FINVIZ_TOKEN": "",
            "FINVIZ_USERNAME": "operator@example.com",
            "FINVIZ_PASSWORD": "not-a-real-password",
            "IMP_FINVIZ_LIVE": "",
        }
        adapter, discovery = discover_finviz_context_stack(
            env=env,
            token_fetcher=lambda: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        )
        overlay = overlay_payload(
            discovery=discovery.to_dict(),
            result=adapter.fetch_context("AAPL"),
        )
        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch(
                "tools.path_a_prospective_run._finviz_hop_overlay",
                return_value=(adapter, overlay),
            ):
                with patch("sys.stdout", stdout):
                    code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        dumped = stdout.getvalue()
        payload = json.loads(dumped)
        self.assertEqual(payload["equity_context"]["discovery"]["auto_fetch_status"], "FETCHED")
        assert_no_ftep_empirical_promotion(dumped)
        assert_ftep_campaign_still_not_empirical(REPO_ROOT, CAMPAIGN)

    def test_market_closed_session_gate_and_status_have_no_ftep_promotion(self) -> None:
        from tools.ftep_session_start import collect_session_start_gates

        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.campaign_status.is_within_us_equity_rth",
            return_value=False,
        ):
            status = collect_ftep_campaign_status(REPO_ROOT, CAMPAIGN)
            self.assertFalse(status["us_equity_rth_open"])
            self.assertEqual(status["calendar_scope"], CALENDAR_US_EQUITY_RTH)
            assert_no_ftep_empirical_promotion(json.dumps(status))
            payload = collect_session_start_gates(REPO_ROOT, CAMPAIGN)
        self.assertFalse(payload["would_create_session"])
        self.assertIn("US_EQUITY_RTH_CLOSED", payload["blockers"])
        assert_no_ftep_empirical_promotion(json.dumps(payload))
        assert_ftep_campaign_still_not_empirical(REPO_ROOT, CAMPAIGN)

    def test_missing_production_json_does_not_promote_ftep_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            missing = store / "missing-contributors.json"
            forecasts = store / "forecasts"
            prereg = store / "prereg"
            forecasts.mkdir()
            prereg.mkdir()
            persist_paper_demo_preregistration(
                default_forecast_momentum_spec(),
                registered_at=EARLY_REGISTERED_AT,
                destination=prereg,
            )
            invoke = build_paper_demo_path_a_invoke("AAPL", mode="paper", as_of_time_ns=T)
            produced = produce_paper_demo_forecast(
                contributors=load_paper_demo_contributors(missing),
                calibration_artifact=None,
                champion=invoke.caller.champion_at_forecast,
                policy=invoke.caller.opportunity_policy,
                destination=forecasts,
                account_id=invoke.scan_request.scope.account_id,
                mode="paper",
                as_of_time_ns=T,
            )
            self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
            composer = PathAProspectiveComposer(
                quote_provider=_RealtimeQuoteProvider(),
                preregistration_path=prereg,
                contributor_path=missing,
                forecast_path=forecasts,
            ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
            assert_no_ftep_empirical_promotion(json.dumps(composer.to_dict()))
        assert_ftep_campaign_still_not_empirical(REPO_ROOT, CAMPAIGN)

    def test_software_matched_mint_does_not_promote_ftep_labels(self) -> None:
        sys.path.insert(0, str(ROOT / "tests" / "intelligence"))
        from test_path_a_prospective import _run_matched_fixture_hop

        result, _engine = _run_matched_fixture_hop(mode="paper")
        self.assertEqual(result.path_a.status, "MINTED")
        assert_no_ftep_empirical_promotion(json.dumps(result.to_dict()))
        assert_ftep_campaign_still_not_empirical(REPO_ROOT, CAMPAIGN)

    def test_market_closed_calibration_waiting_is_not_calibrated(self) -> None:
        from tests.platform.test_calibration_harness import ALPACA_PAPER_ENV, _decision

        outcome = run_calibration_campaign(
            env=ALPACA_PAPER_ENV,
            now_ns=T,
            decision=_decision(),
            session_label="CLOSED",
        )
        self.assertEqual(outcome.status, STATUS_WAITING_FOR_MARKET)
        assert_no_ftep_empirical_promotion(json.dumps(outcome.to_dict()))
        self.assertFalse(outcome.calibrated)
        self.assertFalse(outcome.empirical_active)


if __name__ == "__main__":
    unittest.main()
