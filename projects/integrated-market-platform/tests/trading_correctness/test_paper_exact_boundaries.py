"""SOFTWARE_CONTROLLED: exact native quantities; existing minimum-one policy."""
from decimal import Decimal
import unittest
from types import SimpleNamespace
from market_platform_foundation.paper.preview import PreviewStore, PreviewRecord, verify_preview_submit, portfolio_state_revision
from market_platform_foundation.paper.execution import cancel_interactive_order
from market_platform_foundation.intelligence.execution import PreTradeRiskEngine, build_execution_policy
from market_platform_foundation.intelligence.execution.snapshot import snapshot_from_paper_ledger
from market_platform_foundation.intelligence.execution.serialization import risk_decision_v1_to_dict, risk_decision_v1_from_dict, paper_portfolio_snapshot_v1_to_dict, paper_portfolio_snapshot_v1_from_dict
from market_platform_foundation.intelligence.contracts.trade_proposal import trade_proposal_v1_to_dict, trade_proposal_v1_from_dict
from market_platform_foundation.ui_api.paper_projections import _parse_order_body
from tests.trading_correctness.test_paper_exact_execution import crypto, ledger, submit, bars
from tests.intelligence.execution_fixtures import flat_portfolio, sample_opportunity, sample_quote
from tests.intelligence.outcome_fixtures import T

class ExactBoundaryTests(unittest.TestCase):
    def test_preview_restores_and_compares_exact_quantity(self):
        store = PreviewStore()
        claims = dict(account_id="acct", mode="PAPER", instrument_id="BTC/USD", intent_digest="digest", side="BUY",
            quantity="1.125", order_type="MARKET", risk_policy_revision="risk", portfolio_revision="state", observation_time=100)
        record = store.issue(**claims, now_ns=100)
        self.assertEqual(record.quantity, "1.125")
        self.assertEqual(PreviewRecord.from_dict(record.to_dict()), record)
        verification = dict(claims, preview_id=record.preview_id, limit_price_minor=None, now_ns=101)
        verification.pop("observation_time")
        verify_preview_submit(store, **verification)
        with self.assertRaisesRegex(ValueError, "PREVIEW_INTENT_MISMATCH"):
            verify_preview_submit(store, **dict(verification, quantity="1.126"))

    def test_fractional_position_preview_revision_and_build22_snapshot(self):
        book = ledger()
        submit(book, quantity="1.125", feed=bars("10.0000", volume="2"))
        book.apply_live_mark(instrument_id="BTC/USD", mark_minor=120000, mark_provider="CONTROLLED_FIXTURE", mark_as_of_ns=300, mark_quality="PASS")
        revision = portfolio_state_revision(book)
        self.assertEqual(revision, portfolio_state_revision(book))
        snap = snapshot_from_paper_ledger(book, captured_at_ns=300)
        self.assertEqual(snap.positions[0].quantity, Decimal("1.125"))
        self.assertEqual(snap.positions[0].market_value_minor, 1350)
        self.assertEqual(snap.equity_minor, 100225)
        self.assertEqual(paper_portfolio_snapshot_v1_from_dict(paper_portfolio_snapshot_v1_to_dict(snap)), snap)

    def test_fractional_cancel_receipt_preserves_filled_units(self):
        book = ledger()
        result = submit(book, quantity="1.125", feed=bars("10.0000", volume="1"))
        cancelled = cancel_interactive_order(ledger=book, order_id=result["order_id"])
        self.assertEqual(cancelled["filled_quantity"], "1")
        self.assertEqual(cancelled["working_remaining"], 0)
        self.assertEqual(book.reserved_cash_minor(), 0)

    def test_equity_parser_rejects_bool_and_fraction_without_truncation(self):
        for quantity in (True, 1.5, "1.5"):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                _parse_order_body(dict(quantity=quantity, side="BUY", client_order_id="fixture"), SimpleNamespace())

    def test_build22_exact_native_units_preserve_minimum_one(self):
        engine, policy = PreTradeRiskEngine(), build_execution_policy()
        opportunity, portfolio, quote = sample_opportunity(), flat_portfolio(), sample_quote()
        instrument = crypto("inst-biya")
        for quantity, decision in (("1.125", "APPROVE"), ("0.125", "REJECT")):
            with self.subTest(quantity=quantity):
                proposal = engine.build_proposal(opportunity=opportunity, policy=policy, portfolio=portfolio, quote=quote,
                    proposal_time_ns=T+2_000_000_000, instrument_id="inst-biya", symbol="BTC/USD", instrument=instrument,
                    allocation_desired_quantity=quantity)
                self.assertEqual(proposal.requested_quantity, Decimal(quantity))
                self.assertEqual(trade_proposal_v1_from_dict(trade_proposal_v1_to_dict(proposal)), proposal)
                risk = engine.assess(proposal=proposal, opportunity=opportunity, policy=policy, portfolio=portfolio,
                    decision_time_ns=T+2_000_000_000, symbol="BTC/USD")
                self.assertEqual(str(risk.decision), decision)
                self.assertEqual(risk_decision_v1_from_dict(risk_decision_v1_to_dict(risk)), risk)
        self.assertEqual(policy.minimum_quantity, 1)


    def test_crypto_position_event_and_episode_keep_exact_opening_quantity(self):
        from market_platform_foundation.intelligence.inference.trade_lifecycle import episodes_from_trades
        from market_platform_foundation.risk.sma_trailing_stop import position_epoch
        book = ledger()
        submit(book, quantity="1.125", feed=bars("10.0000",volume="2"))
        changed = [e["payload"] for e in book.events if e["event_type"] == "PositionChanged"][-1]
        self.assertEqual(changed["position_shares"], "1.125")
        episodes = episodes_from_trades(book.project_trades(), account_id=book.paper_account_id, experiment_id=book.experiment_id)
        self.assertEqual((len(episodes),episodes[0]["side"],episodes[0]["open"]),(1,"LONG",True))
        self.assertIsNotNone(position_epoch(book.events,account_id=book.paper_account_id,session_id=book.session_id,
            instrument_id="BTC/USD",side="LONG",experiment_id=book.experiment_id))

    def test_crypto_portfolio_mark_uses_native_scale_without_new_demand(self):
        from market_platform_foundation.ui_api.live_projections import _apply_portfolio_marks
        from unittest.mock import patch
        book = ledger()
        submit(book, quantity="1.125", feed=bars("10.0000",volume="2"))
        book.data_mode = "LIVE_OBSERVATIONAL"
        store = SimpleNamespace(paper_ledger=book,data_mode="LIVE_OBSERVATIONAL")
        quote = dict(admissible=True,last_price_minor=120000,source="CONTROLLED_CRYPTO_STREAM",as_of_time_ns=300)
        with patch("market_platform_foundation.ui_api.paper_market_evidence.PaperMarketEvidence.quote",return_value=quote) as reader:
            _apply_portfolio_marks(store,None)
        self.assertEqual(book.project_positions()[0]["market_value_minor"],1350)
        self.assertEqual(reader.call_args.kwargs["instrument"]["price_scale"],10000)

from unittest.mock import patch
from tests.trading_correctness.test_paper_automation import AutoBase
from tests.support.paper_automation_harness import Automation, EquityAi, policy_body
from market_platform_foundation.ui_api import screener_crypto


class CryptoAi(EquityAi):
    @staticmethod
    def _query(body):
        if body.get("universe") not in ("CRYPTO", "US_EQUITIES"):
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        return dict(EquityAi._query(dict(body, universe="US_EQUITIES")), universe=body["universe"])

    def candidate(self, iid, now):
        candidate = super().candidate(iid, now)
        candidate["instrument"] = dict(instrument_id=iid, symbol="BTC/USD", universe="CRYPTO", asset_class="CRYPTO", venue_id="KRAKEN")
        return candidate


class ExactCryptoLifecycleTests(AutoBase):
    """Only provider/model/evidence/clock/opportunity are fixtures; all execution gates are real."""
    def setUp(self):
        super().setUp()
        self.catalog_calls = 0
        payload = {"error": [], "result": {"BTC/USD": dict(base="BTC", quote="USD", aclass_base="currency", aclass_quote="currency",
            status="online", ordermin="0.001", costmin="1", tick_size="0.0001", lot_decimals=3, pair_decimals=4, cost_decimals=2)}}
        def catalog():
            self.catalog_calls += 1
            return payload
        self.crypto_source = screener_crypto.CryptoScreener(client=SimpleNamespace(asset_pairs=catalog), env={"IMP_CRYPTO_LIVE":"1"})
        rows, _, error = self.crypto_source._catalog()
        self.assertIsNone(error)
        self.iid = rows[0]["instrument"]["instrument_id"]
        patcher = patch.object(screener_crypto, "_SERVICE", self.crypto_source)
        patcher.start(); self.addCleanup(patcher.stop)
        ai = CryptoAi(self.clock, self.auto.provider)
        ai.rows = {}; ai.selected = []
        self.auto = Automation(self.store, clock=self.clock, feed=self.feed, ai=ai, provider=self.auto.provider)
        # The feed's marks use the admitted instrument scale, exactly like the real crypto evidence path.
        def mark(store, instrument_id, price, quality="PASS"):
            from market_platform_foundation.local_state.startup import persist_ledger
            ref = store.paper_ledger.instrument_for(instrument_id)
            store.paper_ledger.apply_live_mark(instrument_id=instrument_id,
                mark_minor=int(Decimal(price) * int(ref.get("price_scale",100))), mark_provider="CONTROLLED_FIXTURE",
                mark_as_of_ns=self.feed.now_ns(), mark_quality=quality, freshness_ms=0)
            persist_ledger(store.paper_ledger)
        self.feed.mark = mark

    def start_crypto(self, *, opportunity=True):
        a = self.auto
        a.quote(self.iid, 800, 2)
        if opportunity:
            a.opportunity(self.iid)
        body = policy_body(risk=dict(allowed_universes=["US_EQUITIES","CRYPTO"], max_position_notional_minor=90000))
        body["scopes"] = [dict(scope=dict(body["scope"]), sessions=["REGULAR"]), dict(scope=dict(universe="CRYPTO"),sessions=["CONTINUOUS"])]
        a.session_label = "CLOSED"
        a.service.configure(body); a.arm(); a.service.start(threaded=False)
        a.cycle()
        run_id = a.service._controller()["universes"]["CRYPTO"]["universe"]["active_run_id"]
        a.runs.finish(run_id,[self.iid])
        return a.cycle()

    def test_governed_exact_entry_close_pnl_restart_and_duplicate_suppression(self):
        a = self.auto
        receipt = self.start_crypto()
        entries = [r for r in receipt["actions"] if r["outcome"] == "SUBMITTED"]
        self.assertEqual(len(entries), 1, receipt)
        self.assertEqual(entries[0]["quantity"], "1.125")
        self.assertEqual(entries[0]["filled_quantity"], "1.125")
        self.assertEqual(a.position(self.iid)["quantity"], "1.125")
        self.assertEqual(a.store.paper_ledger.project_account()["cash_minor"], 9910000)
        self.assertEqual(a.store.paper_ledger.project_fills()[0]["fill_price_minor"], 8000000)
        order = a.orders()[0]
        risk = a.store.strategy_repository.get_risk_decision(order["risk_decision_id"])
        self.assertEqual(risk.approved_notional_minor,90000)
        proposal = a.store.strategy_repository.get_trade_proposal(risk.trade_proposal_id)
        self.assertEqual(proposal.reference_price_minor,80000)
        self.assertEqual(proposal.metadata["instrument"]["price_scale"],10000)
        entry_decision = a.actions.history(self.iid)[0]
        self.assertEqual(entry_decision["action_state"], "ENTER")
        self.assertIsNone(a.service.execute_decision(entry_decision, a.service.status()["policy"], a.service._controller(), a.session(self.clock())))
        self.assertEqual(len(a.orders()), 1)
        a.quote(self.iid, 820, -2)
        closing = a.cycle(400)
        self.assertEqual(closing["actions"][0]["outcome"], "SUBMITTED", closing)
        self.assertEqual(closing["actions"][0]["quantity"], "1.125")
        self.assertIsNone(a.position(self.iid))
        self.assertEqual(a.store.paper_ledger.project_account()["cash_minor"], 10002250)
        self.assertEqual(a.store.paper_ledger.project_account()["realized_pnl_minor"], 2250)
        history = a.store.paper_ledger.project_trades()
        self.assertEqual(len(history), 2)
        self.assertEqual([t["filled_quantity"] for t in history], ["1.125","1.125"])
        restarted = self.restart()
        self.assertEqual(restarted.store.paper_ledger.project_trades(), history)
        self.assertEqual(restarted.store.paper_ledger.project_account()["cash_minor"], 10002250)
        self.assertIsNone(restarted.service.execute_decision(entry_decision, restarted.service.status()["policy"], restarted.service._controller(), restarted.session(self.clock())))
        self.assertEqual(len(restarted.orders()), 2)
        self.assertEqual(self.catalog_calls, 1)  # admission never starts another provider request

    def test_missing_governed_opportunity_blocks_all_orders(self):
        receipt = self.start_crypto(opportunity=False)
        self.assertEqual(self.auto.orders(), [])
        self.assertTrue(any("NO_GOVERNED_OPPORTUNITY" in d["blocker_codes"] for d in self.auto.actions.history(self.iid)), receipt)

    def test_cached_economics_stale_missing_and_malformed_are_fail_closed(self):
        from market_platform_foundation.ui_api.paper_projections import _admit_focus_instrument
        rules = _admit_focus_instrument(self.store, self.iid)
        self.assertEqual((rules["quantity_step"],rules["minimum_quantity"],rules["price_scale"]), ("0.001","0.001",10000))
        cached = self.crypto_source._catalog_cache
        self.crypto_source._catalog_cache = (cached[0]-1000,*cached[1:])
        with self.assertRaisesRegex(ValueError,"CRYPTO_ECONOMICS_STALE"):
            _admit_focus_instrument(self.store,self.iid)
        self.crypto_source._catalog_cache = cached
        cached[2][0]["base_increment"] = None
        with self.assertRaisesRegex(ValueError,"CRYPTO_ECONOMICS_INVALID"):
            _admit_focus_instrument(self.store,self.iid)
        self.assertEqual(self.catalog_calls,1)


    def test_non_usd_spot_execution_is_rejected_before_mutation(self):
        from market_platform_foundation.ui_api.paper_projections import preview_paper_order
        payload = {"error":[],"result":{"ETH/BTC":dict(base="ETH",quote="BTC",aclass_base="currency",aclass_quote="currency",
            status="online",ordermin="0.001",costmin="0.001",tick_size="0.0001",lot_decimals=3,pair_decimals=4,cost_decimals=4)}}
        rows = screener_crypto.project_catalog(payload,as_of="2026-10-18T00:00:00Z")
        cached = self.crypto_source._catalog_cache
        self.crypto_source._catalog_cache = (cached[0],cached[1],cached[2]+rows,None)
        iid = rows[0]["instrument"]["instrument_id"]
        before = list(self.store.paper_ledger.events)
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_SETTLEMENT_CURRENCY"):
            preview_paper_order(self.store,dict(instrument_id=iid,side="BUY",quantity="1.125",client_order_id="nonusd"))
        self.assertEqual(self.store.paper_ledger.events,before)

    def test_venue_minimum_notional_blocks_order_without_mutation(self):
        from market_platform_foundation.ui_api.paper_projections import preview_paper_order
        self.feed.prices[self.iid] = "0.10"
        before = list(self.store.paper_ledger.events)
        with self.assertRaisesRegex(ValueError,"ORDER_NOTIONAL_MINIMUM_INVALID"):
            preview_paper_order(self.store,dict(instrument_id=self.iid,side="BUY",quantity="1.125",client_order_id="toosmall"))
        self.assertEqual(self.store.paper_ledger.events,before)
