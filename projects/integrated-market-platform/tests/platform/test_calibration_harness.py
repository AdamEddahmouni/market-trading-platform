"""IMP simulator vs Tradier sandbox calibration harness tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import SIMULATOR_VERSION  # noqa: E402
from market_platform_foundation.intelligence.paper_forward_bridge.repository import (  # noqa: E402
    ForwardTestRepositoryError,
)
from market_platform_foundation.intelligence.paper_forward_bridge.sqlite_repository import (  # noqa: E402
    SqliteForwardTestRepository,
)
from market_platform_foundation.intelligence.paper_forward_bridge.types import (  # noqa: E402
    EvaluationState,
    ForwardTestDecision,
    ForwardTestEvidenceClass,
    ForwardTestMode,
    ForwardTestRunKind,
    ForwardTestState,
)
from market_platform_foundation.local_state.connection import LocalStateConnection  # noqa: E402
from market_platform_foundation.local_state.schema import SCHEMA_VERSION  # noqa: E402
from market_platform_foundation.paper.calibration.asset_scope import (  # noqa: E402
    EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
    CalibrationAssetScopeError,
    assert_calibration_unit_asset_scope,
)
from market_platform_foundation.paper.calibration.comparator_contract import (  # noqa: E402
    ComparatorContractError,
    validate_comparator_binding,
)
from market_platform_foundation.paper.calibration.metrics import (  # noqa: E402
    FillObservation,
    SampleHonesty,
    compute_calibration_metric_report,
)
from market_platform_foundation.paper.calibration.pairing import (  # noqa: E402
    PAIR_CONFIDENCE_HIGH,
    PAIR_METHOD_CORRELATION_ID,
    PAIR_METHOD_PAIRING_TABLE,
    ComparatorPairingRecord,
    forward_test_correlation_id,
    pair_imp_and_comparator,
)
from market_platform_foundation.paper.calibration.persistence import (  # noqa: E402
    CALIBRATION_PAIR_KIND,
    CALIBRATION_STATUS_KIND,
    CalibrationPersistenceError,
    persist_pairing_result,
)
from market_platform_foundation.paper.calibration.runner import (  # noqa: E402
    STATUS_COMPARATOR_NOT_CONFIGURED,
    STATUS_HARNESS_READY,
    STATUS_LIVE_FORBIDDEN,
    STATUS_WAITING_FOR_MARKET,
    classify_calibration_run,
    run_calibration_campaign,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.adapters.tradier_sandbox_http import (  # noqa: E402
    TradierSandboxHttpError,
    TradierSandboxHttpTransport,
    assert_tradier_sandbox_url,
    normalize_tradier_wire_order,
    tradier_http_place_order,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    build_broker_order_request,
)

T0 = 1_700_000_000_000_000_000
TRADIER_BINDING = {
    "comparator_id": "tradier",
    "environment": TRADIER_SANDBOX_ENDPOINT,
    "account_mode": "paper",
    "limitations": ["equity_only", EQUITY_PAPER_DOES_NOT_VALIDATE_ES],
}
SANDBOX_ENV = {
    "IMP_TRADIER_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "IMP_TRADIER_TOKEN": "sandbox-test-token",
    "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
    "IMP_TRADIER_ACCOUNT_ID": "VA0001",
    "IMP_TRADIER_SANDBOX_HTTP": "1",
}
ALPACA_PAPER_ENV = {
    "IMP_ALPACA_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "APCA_API_KEY_ID": "paper-key",
    "APCA_API_SECRET_KEY": "paper-secret",
    "APCA_API_BASE_URL": "https://paper-api.alpaca.markets",
}


def _decision(
    *,
    forward_test_id: str = "ftd-cal-1",
    account_id: str = "paper-a",
    symbol: str = "AAPL",
    mode: str = "PAPER",
) -> ForwardTestDecision:
    return ForwardTestDecision(
        forward_test_id=forward_test_id,
        session_id="fts-cal-1",
        account_id=account_id,
        mode=mode,
        run_kind=ForwardTestRunKind.FORWARD_TEST,
        test_mode=ForwardTestMode.EXECUTION,
        symbol=symbol,
        decision_time_ns=T0,
        source_time_ns=T0 - 1,
        state=ForwardTestState.LOCKED,
        direction="BUY",
        quantity=1,
        confidence=None,
        strategy_id="calibration",
        strategy_version="1",
        research_artifact_ref=None,
        evaluation_horizon_ns=3_600_000_000_000,
        decision_payload={"asset_class": "EQUITY"},
        provenance_snapshot={"simulator_version": SIMULATOR_VERSION},
        locked_at_ns=T0,
        evaluation_state=EvaluationState.PENDING,
        evidence_class=ForwardTestEvidenceClass.SOFTWARE_FIXTURE_ONLY,
    )


def _fill(
    *,
    order_id: str,
    filled: bool = True,
    correlation_id: str | None = None,
    **kwargs,
) -> FillObservation:
    return FillObservation(
        order_id=order_id,
        filled=filled,
        correlation_id=correlation_id,
        **kwargs,
    )


class FakeTradierHttp:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, dict]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, *, token: str, form: dict[str, str] | None = None):
        del token
        self.calls.append((method, url))
        if "api.tradier.com" in url or "api.alpaca.markets" in url:
            raise AssertionError("live host must never be contacted")
        key = (method, url)
        if key not in self.responses:
            path_keys = [item for item in self.responses if item[0] == method and url.endswith(item[1])]
            if path_keys:
                return self.responses[path_keys[0]]
            raise AssertionError(f"unexpected sandbox call {method} {url} form={form}")
        return self.responses[key]


class PairingTests(unittest.TestCase):
    def test_pairs_on_forward_test_correlation_id(self) -> None:
        ft_id = "ftd-lock-1"
        correlation = forward_test_correlation_id(ft_id)
        self.assertEqual(correlation, "forward_test:ftd-lock-1")
        result = pair_imp_and_comparator(
            forward_test_id=ft_id,
            imp_fills=[
                _fill(
                    order_id="imp-1",
                    correlation_id=correlation,
                    fill_price=100.0,
                    paper_account_id="paper-a",
                    instrument_id="AAPL",
                )
            ],
            comparator_fills=[
                _fill(
                    order_id="tr-1",
                    correlation_id=correlation,
                    fill_price=100.2,
                    paper_account_id="paper-a",
                    instrument_id="AAPL",
                )
            ],
        )
        self.assertEqual(result.pair_count, 1)
        pair = result.pairs[0]
        self.assertEqual(pair.correlation_id, correlation)
        self.assertEqual(pair.pair_method, PAIR_METHOD_CORRELATION_ID)
        self.assertEqual(pair.simulator_version, SIMULATOR_VERSION)
        self.assertEqual(len(result.unpaired_imp), 0)

    def test_pairing_table_joins_when_echo_fails(self) -> None:
        result = pair_imp_and_comparator(
            forward_test_id="ftd-lock-2",
            imp_fills=[_fill(order_id="imp-9", fill_price=10.0)],
            comparator_fills=[_fill(order_id="tr-9", fill_price=10.1)],
            pairing_table=[
                ComparatorPairingRecord(
                    forward_test_id="ftd-lock-2",
                    paper_order_id="imp-9",
                    comparator_order_id="tr-9",
                    pair_method=PAIR_METHOD_PAIRING_TABLE,
                    pair_confidence=PAIR_CONFIDENCE_HIGH,
                    pair_time_ns=T0,
                )
            ],
        )
        self.assertEqual(result.pair_count, 1)
        self.assertEqual(result.pairs[0].pair_method, PAIR_METHOD_PAIRING_TABLE)

    def test_unpaired_rows_are_counted_not_dropped(self) -> None:
        result = pair_imp_and_comparator(
            forward_test_id="ftd-lock-3",
            imp_fills=[_fill(order_id="imp-only")],
            comparator_fills=[_fill(order_id="tr-only")],
        )
        self.assertEqual(result.pair_count, 0)
        self.assertEqual(len(result.unpaired_imp), 1)
        self.assertEqual(len(result.unpaired_comparator), 1)


class MetricHonestyTests(unittest.TestCase):
    def test_zero_pairs_are_not_observable_not_zero_rate(self) -> None:
        report = compute_calibration_metric_report(imp_fills=(), comparator_fills=())
        self.assertEqual(report.pair_count, 0)
        self.assertIsNone(report.fill_disagreement_rate)
        self.assertEqual(report.sample_honesty, SampleHonesty.NOT_OBSERVABLE)
        self.assertFalse(report.calibrated)

    def test_small_n_is_reported(self) -> None:
        report = compute_calibration_metric_report(
            imp_fills=[
                _fill(
                    order_id="o1",
                    fill_price=100.0,
                    ack_time_ns=10,
                    fill_qty=1,
                    approved_qty=1,
                    fill_count=1,
                    rejected=False,
                    cancelled=False,
                )
            ],
            comparator_fills=[
                _fill(
                    order_id="o1",
                    fill_price=100.5,
                    ack_time_ns=40,
                    fill_qty=1,
                    approved_qty=1,
                    fill_count=1,
                    rejected=False,
                    cancelled=False,
                )
            ],
            minimum_n=30,
        )
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.sample_honesty, SampleHonesty.INSUFFICIENT_SAMPLE)
        self.assertEqual(report.price_error["n"], 1)
        self.assertIsNotNone(report.price_error["median"])
        self.assertIsNotNone(report.price_error["p95"])
        self.assertIsNotNone(report.slippage_bps["mean"])
        self.assertEqual(report.latency_error_ns["n"], 1)
        self.assertEqual(report.fill_qty_agreement_rate, 1.0)
        self.assertEqual(report.reject_disagreement_rate, 0.0)
        self.assertEqual(report.cancel_disagreement_rate, 0.0)
        self.assertEqual(report.simulator_version, SIMULATOR_VERSION)


class PersistenceRestartTests(unittest.TestCase):
    def test_pairs_survive_sqlite_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "imp-state.sqlite3"
            conn = LocalStateConnection(path)
            self.assertEqual(conn.schema_version(), SCHEMA_VERSION)
            repo = SqliteForwardTestRepository(conn)
            decision = _decision()
            repo.put_decision(decision)
            correlation = forward_test_correlation_id(decision.forward_test_id)
            pairing = pair_imp_and_comparator(
                forward_test_id=decision.forward_test_id,
                imp_fills=[
                    _fill(
                        order_id="imp-1",
                        correlation_id=correlation,
                        fill_price=50.0,
                        paper_account_id="paper-a",
                        instrument_id="AAPL",
                    )
                ],
                comparator_fills=[
                    _fill(
                        order_id="tr-1",
                        correlation_id=correlation,
                        fill_price=50.1,
                        paper_account_id="paper-a",
                        instrument_id="AAPL",
                    )
                ],
            )
            persist_pairing_result(
                repo,
                decision=decision,
                pairing=pairing,
                comparator=validate_comparator_binding(TRADIER_BINDING),
                evidence_class="SOFTWARE_FIXTURE_ONLY",
                observation_label="FIXTURE_BACKED_NOT_PROSPECTIVE",
                observed_at_ns=T0,
            )
            conn.close()
            restarted = SqliteForwardTestRepository(LocalStateConnection(path))
            loaded = restarted.get_decision(decision.forward_test_id)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(len(loaded.observations), 1)
            payload = loaded.observations[0].payload
            self.assertEqual(payload["kind"], CALIBRATION_PAIR_KIND)
            self.assertEqual(payload["correlation_id"], correlation)
            self.assertEqual(payload["simulator_version"], SIMULATOR_VERSION)
            self.assertFalse(payload["calibrated"])
            self.assertFalse(payload["is_market_truth"])
            self.assertTrue(payload["equity_paper_does_not_validate_es"])


class IsolationTests(unittest.TestCase):
    def test_paper_vs_live_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteForwardTestRepository(LocalStateConnection(Path(tmp) / "s.sqlite3"))
            with self.assertRaises(ForwardTestRepositoryError):
                repo.put_decision(_decision(mode="LIVE"))
        self.assertEqual(
            classify_calibration_run(env=SANDBOX_ENV, now_ns=T0, requested_mode="LIVE"),
            STATUS_LIVE_FORBIDDEN,
        )
        with self.assertRaises(ComparatorContractError):
            validate_comparator_binding(
                {
                    "comparator_id": "tradier",
                    "environment": "https://api.tradier.com/v1",
                    "account_mode": "paper",
                    "limitations": ["equity_only"],
                }
            )
        with self.assertRaises(ComparatorContractError):
            validate_comparator_binding(
                {
                    "comparator_id": "alpaca",
                    "environment": "https://api.alpaca.markets",
                    "account_mode": "paper",
                    "limitations": ["equity_only"],
                }
            )

    def test_two_accounts_and_instruments_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteForwardTestRepository(LocalStateConnection(Path(tmp) / "s.sqlite3"))
            aapl = _decision(forward_test_id="ftd-aapl", account_id="acct-a", symbol="AAPL")
            msft = _decision(forward_test_id="ftd-msft", account_id="acct-b", symbol="MSFT")
            repo.put_decision(aapl)
            repo.put_decision(msft)
            pairing_a = pair_imp_and_comparator(
                forward_test_id="ftd-aapl",
                imp_fills=[
                    _fill(
                        order_id="a",
                        correlation_id=forward_test_correlation_id("ftd-aapl"),
                        paper_account_id="acct-a",
                        instrument_id="AAPL",
                    )
                ],
                comparator_fills=[
                    _fill(
                        order_id="a",
                        correlation_id=forward_test_correlation_id("ftd-aapl"),
                        paper_account_id="acct-a",
                        instrument_id="AAPL",
                    )
                ],
            )
            persist_pairing_result(
                repo,
                decision=aapl,
                pairing=pairing_a,
                comparator=validate_comparator_binding(TRADIER_BINDING),
                evidence_class="SOFTWARE_FIXTURE_ONLY",
                observation_label="FIXTURE_BACKED_NOT_PROSPECTIVE",
                observed_at_ns=T0,
            )
            self.assertEqual(len(repo.list_decisions(account_id="acct-a")), 1)
            self.assertEqual(len(repo.list_decisions(account_id="acct-b")), 1)
            self.assertEqual(repo.list_decisions(account_id="acct-a")[0].symbol, "AAPL")
            self.assertEqual(len(repo.get_decision("ftd-msft").observations), 0)
            mismatched = pair_imp_and_comparator(
                forward_test_id="ftd-msft",
                imp_fills=[
                    _fill(
                        order_id="x",
                        correlation_id=forward_test_correlation_id("ftd-msft"),
                        paper_account_id="acct-b",
                        instrument_id="AAPL",
                    )
                ],
                comparator_fills=[
                    _fill(
                        order_id="x",
                        correlation_id=forward_test_correlation_id("ftd-msft"),
                        paper_account_id="acct-b",
                        instrument_id="AAPL",
                    )
                ],
            )
            with self.assertRaises(CalibrationPersistenceError):
                persist_pairing_result(
                    repo,
                    decision=msft,
                    pairing=mismatched,
                    comparator=validate_comparator_binding(TRADIER_BINDING),
                    evidence_class="SOFTWARE_FIXTURE_ONLY",
                    observation_label="FIXTURE_BACKED_NOT_PROSPECTIVE",
                    observed_at_ns=T0 + 1,
                )


class RunnerTests(unittest.TestCase):
    def test_unconfigured_comparator_does_not_fabricate_fills(self) -> None:
        result = run_calibration_campaign(env={}, now_ns=T0, decision=_decision())
        self.assertEqual(result.status, STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertEqual(result.pair_count, 0)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.empirical_active)
        self.assertFalse(result.detail["fabricated_fills"])
        self.assertFalse(result.detail["orders_placed"])
        self.assertIn("alpaca_gates", result.detail)

    def test_configured_outside_rth_is_waiting_for_market(self) -> None:
        result = run_calibration_campaign(
            env=SANDBOX_ENV,
            now_ns=T0,
            decision=_decision(),
            session_label="CLOSED",
        )
        self.assertEqual(result.status, STATUS_WAITING_FOR_MARKET)
        self.assertEqual(result.observation_label, STATUS_WAITING_FOR_MARKET)
        self.assertNotEqual(result.status, STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertEqual(result.pair_count, 0)
        self.assertIsNone(result.metrics.fill_disagreement_rate)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.detail["fabricated_fills"])

    def test_closed_session_without_keys_is_not_waiting_for_market(self) -> None:
        result = run_calibration_campaign(
            env={},
            now_ns=T0,
            decision=_decision(),
            session_label="CLOSED",
        )
        self.assertEqual(result.status, STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertEqual(result.observation_label, STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertNotEqual(result.status, STATUS_WAITING_FOR_MARKET)
        self.assertNotEqual(result.observation_label, STATUS_WAITING_FOR_MARKET)
        self.assertEqual(result.pair_count, 0)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.detail["orders_placed"])
        self.assertFalse(result.detail["fabricated_fills"])

    def test_alpaca_configured_closed_session_is_waiting_not_unconfigured(self) -> None:
        result = run_calibration_campaign(
            env=ALPACA_PAPER_ENV,
            now_ns=T0,
            decision=_decision(),
            session_label="CLOSED",
        )
        self.assertEqual(result.status, STATUS_WAITING_FOR_MARKET)
        self.assertEqual(result.observation_label, STATUS_WAITING_FOR_MARKET)
        self.assertNotEqual(result.status, STATUS_COMPARATOR_NOT_CONFIGURED)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.empirical_active)

    def test_status_classifiers_persist_distinctly_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "imp-state.sqlite3"
            conn = LocalStateConnection(path)
            repo = SqliteForwardTestRepository(conn)
            missing = _decision(forward_test_id="ftd-cal-missing")
            waiting = _decision(forward_test_id="ftd-cal-waiting")
            repo.put_decision(missing)
            repo.put_decision(waiting)
            missing_result = run_calibration_campaign(
                env={},
                now_ns=T0,
                decision=missing,
                repository=repo,
                session_label="CLOSED",
            )
            waiting_result = run_calibration_campaign(
                env=SANDBOX_ENV,
                now_ns=T0 + 1,
                decision=waiting,
                repository=repo,
                session_label="CLOSED",
            )
            self.assertEqual(missing_result.status, STATUS_COMPARATOR_NOT_CONFIGURED)
            self.assertEqual(waiting_result.status, STATUS_WAITING_FOR_MARKET)
            conn.close()
            restarted = SqliteForwardTestRepository(LocalStateConnection(path))
            loaded_missing = restarted.get_decision("ftd-cal-missing")
            loaded_waiting = restarted.get_decision("ftd-cal-waiting")
            assert loaded_missing is not None
            assert loaded_waiting is not None
            missing_payload = loaded_missing.observations[-1].payload
            waiting_payload = loaded_waiting.observations[-1].payload
            self.assertEqual(missing_payload["kind"], CALIBRATION_STATUS_KIND)
            self.assertEqual(waiting_payload["kind"], CALIBRATION_STATUS_KIND)
            self.assertEqual(missing_payload["status"], STATUS_COMPARATOR_NOT_CONFIGURED)
            self.assertEqual(
                missing_payload["observation_label"], STATUS_COMPARATOR_NOT_CONFIGURED
            )
            self.assertEqual(waiting_payload["status"], STATUS_WAITING_FOR_MARKET)
            self.assertEqual(
                waiting_payload["observation_label"], STATUS_WAITING_FOR_MARKET
            )
            self.assertNotEqual(missing_payload["status"], waiting_payload["status"])
            self.assertFalse(missing_payload["calibrated"])
            self.assertFalse(waiting_payload["calibrated"])
            self.assertFalse(missing_payload["empirical_active"])
            self.assertFalse(waiting_payload["empirical_active"])

    def test_equity_firewall_blocks_es_with_tradier(self) -> None:
        with self.assertRaises(CalibrationAssetScopeError):
            assert_calibration_unit_asset_scope(
                asset_class="FUTURES",
                instrument_id="ESH6",
                comparator_id="tradier",
            )
        es = replace(_decision(symbol="ES"), decision_payload={"asset_class": "FUTURES"})
        with self.assertRaises(CalibrationAssetScopeError):
            run_calibration_campaign(env=SANDBOX_ENV, now_ns=T0, decision=es, session_label="REGULAR")


class TradierSandboxHttpTests(unittest.TestCase):
    def test_fixture_path_unchanged_without_http_gate(self) -> None:
        provider = make_tradier_paper_provider(
            env={
                "IMP_TRADIER_PAPER": "1",
                "IMP_BROKER_PAPER_EXECUTION": "1",
                "IMP_TRADIER_TOKEN": "sandbox-test-token",
                "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
            },
            replay_store=TradierReplayStore(),
        )
        result = provider.place_order(
            {
                "instrument_id": "AAPL",
                "instrument": {"symbol": "AAPL", "instrument_id": "AAPL"},
                "client_order_id": "cli-x",
                "idempotency_key": "key-x",
                "intent_id": "int-x",
                "desired_quantity": 1,
                "created_time": T0,
                "side": "BUY",
                "order_type": "MARKET",
            }
        )
        self.assertEqual(result.reason_code, "BROKER_TRANSPORT_NOT_IMPLEMENTED")

    def test_production_url_blocked_before_http(self) -> None:
        with self.assertRaises(TradierSandboxHttpError):
            assert_tradier_sandbox_url("https://api.tradier.com/v1/user/profile")
        with self.assertRaises(TradierSandboxHttpError):
            assert_tradier_sandbox_url("https://api.alpaca.markets/v2/account")
        transport = TradierSandboxHttpTransport()
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            with self.assertRaises(TradierSandboxHttpError):
                transport.request(
                    "GET",
                    "https://api.tradier.com/v1/user/profile",
                    token="x",
                )

    def test_injected_sandbox_http_place_order(self) -> None:
        order_url = f"{TRADIER_SANDBOX_ENDPOINT}/accounts/VA0001/orders"
        fetch_url = f"{TRADIER_SANDBOX_ENDPOINT}/accounts/VA0001/orders/228175"
        fake = FakeTradierHttp(
            {
                ("POST", order_url): (200, {"order": {"id": 228175, "status": "ok"}}),
                ("GET", fetch_url): (
                    200,
                    {
                        "orders": {
                            "order": {
                                "id": 228175,
                                "status": "filled",
                                "symbol": "AAPL",
                                "avg_fill_price": 150.25,
                                "exec_quantity": 1,
                                "create_date": "2026-09-14T14:00:00.000Z",
                                "transaction_date": "2026-09-14T14:00:01.000Z",
                            }
                        }
                    },
                ),
            }
        )
        provider = make_tradier_paper_provider(
            env=SANDBOX_ENV,
            replay_store=TradierReplayStore(),
            http_transport=fake,
        )
        result = provider.place_order(
            {
                "instrument_id": "AAPL",
                "instrument": {"symbol": "AAPL", "instrument_id": "AAPL"},
                "client_order_id": "forward_test:ftd-cal-1",
                "idempotency_key": "forward_test:ftd-cal-1",
                "intent_id": "int-cal",
                "desired_quantity": 1,
                "created_time": T0,
                "side": "BUY",
                "order_type": "MARKET",
            }
        )
        self.assertEqual(result.status, "ok")
        self.assertTrue(fake.calls)
        self.assertTrue(all("sandbox.tradier.com" in url for _, url in fake.calls))

    def test_normalize_wire_order_maps_status_and_minor_price(self) -> None:
        record = normalize_tradier_wire_order(
            {"order": {"id": 1, "status": "filled", "avg_fill_price": "10.50", "exec_quantity": 2}},
            receive_time_ns=T0,
            instrument_id="AAPL",
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "filled")
        self.assertEqual(record["avg_fill_price_minor"], 1050)
        self.assertEqual(record["filled_quantity"], 2)

    def test_http_place_builds_equity_form_only(self) -> None:
        request = build_broker_order_request(
            {
                "client_order_id": "cli",
                "idempotency_key": "key",
                "instrument_id": "AAPL",
                "intent_id": "int",
                "order_type": "MARKET",
                "desired_quantity": 1,
                "created_time": T0,
                "side": "BUY",
            },
            broker_symbol="AAPL",
        )
        captured: dict[str, dict[str, str]] = {}

        class Capture:
            def request(self, method, url, *, token, form=None):
                if method == "POST":
                    captured["form"] = dict(form or {})
                    return 200, {"order": {"id": 9, "status": "ok"}}
                return 200, {"orders": {"order": {"id": 9, "status": "filled", "exec_quantity": 0}}}

        tradier_http_place_order(
            Capture(),
            endpoint=TRADIER_SANDBOX_ENDPOINT,
            token="t",
            account_id="VA0001",
            request=request,
            instrument_id="AAPL",
        )
        self.assertEqual(captured["form"]["class"], "equity")
        self.assertEqual(captured["form"]["type"], "market")


class HarnessReadyScoringTests(unittest.TestCase):
    def test_ready_run_scores_fixture_pairs_without_claiming_calibrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteForwardTestRepository(LocalStateConnection(Path(tmp) / "s.sqlite3"))
            decision = _decision()
            repo.put_decision(decision)
            correlation = forward_test_correlation_id(decision.forward_test_id)
            result = run_calibration_campaign(
                env=SANDBOX_ENV,
                now_ns=T0,
                decision=decision,
                repository=repo,
                comparator_payload=TRADIER_BINDING,
                session_label="REGULAR",
                imp_fills=[
                    {
                        "order_id": "imp-1",
                        "filled": True,
                        "correlation_id": correlation,
                        "fill_price": 10.0,
                        "paper_account_id": "paper-a",
                        "instrument_id": "AAPL",
                    }
                ],
                comparator_fills=[
                    {
                        "order_id": "tr-1",
                        "filled": True,
                        "correlation_id": correlation,
                        "fill_price": 10.0,
                        "paper_account_id": "paper-a",
                        "instrument_id": "AAPL",
                    }
                ],
            )
            self.assertEqual(result.status, STATUS_HARNESS_READY)
            self.assertEqual(result.pair_count, 1)
            self.assertFalse(result.calibrated)
            loaded = repo.get_decision(decision.forward_test_id)
            self.assertEqual(len(loaded.observations), 1)


if __name__ == "__main__":
    unittest.main()
