from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest

from market_platform_foundation.intelligence.contracts import ContractReference
from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from market_platform_foundation.portfolio.attribution import (
    AttributionFillV1,
    StrategyAttributionV1,
    attribution_v1_from_dict,
    attribution_v1_to_dict,
    validate_attribution_scope,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.portfolio.attribution_materializer import (
    AttributionMaterializationError,
    get_latest_complete_strategy_attribution,
    materialize_strategy_attribution,
)


def _ref(kind: str, identifier: str) -> ContractReference:
    return ContractReference(kind=kind, id=identifier)


def _fill(
    fill_id: str,
    *,
    direction: str,
    quantity: int,
    price_minor: int,
    fill_time_ns: int,
    commission_minor: int = 0,
    fees_minor: int = 0,
) -> AttributionFillV1:
    return AttributionFillV1(
        fill_id=fill_id,
        execution_ref=_ref("execution", f"exec-{fill_id}"),
        fill_time_ns=fill_time_ns,
        direction=direction,
        quantity=quantity,
        price_minor=price_minor,
        commission_minor=commission_minor,
        fees_minor=fees_minor,
    )


def _attribution(
    attribution_id: str,
    *,
    fills: tuple[AttributionFillV1, ...] = (),
    allocation_quantity: int = 10,
    allocation_direction: str = "LONG",
    prediction_outcome_refs: tuple[ContractReference, ...] = (),
) -> StrategyAttributionV1:
    return StrategyAttributionV1(
        attribution_id=attribution_id,
        schema_version="1",
        account_id="account-1",
        mode="PAPER",
        instrument_id="NVDA",
        allocation_ref=_ref("allocation", f"allocation-{attribution_id}"),
        intent_ref=_ref("intent", f"intent-{attribution_id}"),
        opportunity_ref=_ref("opportunity", "opp-1"),
        cluster_thesis_ref=_ref("thesis_cluster", "cluster-1"),
        strategy_match_ref=_ref("strategy_match", f"match-{attribution_id}"),
        strategy_id=f"strategy-{attribution_id}",
        strategy_identity_hash=f"strategy-hash-{attribution_id}",
        allocation_quantity=allocation_quantity,
        allocation_direction=allocation_direction,
        allocation_time_ns=100,
        point_in_time_ns=100,
        fills=fills,
        execution_refs=tuple(fill.execution_ref for fill in fills if fill.execution_ref),
        forecast_refs=(_ref("forecast", "forecast-1"),),
        prediction_outcome_refs=prediction_outcome_refs,
        created_at_ns=100,
    )


class _MaterializerRepository:
    def __init__(self, allocation: object, match: object, opportunity: object) -> None:
        self.allocation = allocation
        self.match = match
        self.opportunity = opportunity
        self.attributions: dict[str, StrategyAttributionV1] = {}
        self.proposal = None
        self.risk = None

    def get_allocation_decision(self, allocation_decision_id: str) -> object | None:
        if allocation_decision_id == self.allocation.allocation_decision_id:
            return self.allocation
        return None

    def get_strategy_match(self, match_id: str) -> object | None:
        if match_id == self.match.match_id:
            return self.match
        return None

    def get_opportunity(self, opportunity_id: str) -> object | None:
        if opportunity_id == self.opportunity.opportunity_id:
            return self.opportunity
        return None

    def get_trade_proposal(self, proposal_id: str) -> object | None:
        if self.proposal is not None and proposal_id == self.proposal.proposal_id:
            return self.proposal
        return None

    def get_risk_decision(self, risk_decision_id: str) -> object | None:
        if self.risk is not None and risk_decision_id == self.risk.risk_decision_id:
            return self.risk
        return None

    def put_strategy_attribution(self, attribution: StrategyAttributionV1) -> RepositoryPutResult:
        if attribution.attribution_id in self.attributions:
            return RepositoryPutResult.ALREADY_PRESENT
        self.attributions[attribution.attribution_id] = attribution
        return RepositoryPutResult.INSERTED

    def get_strategy_attribution(self, attribution_id: str) -> StrategyAttributionV1 | None:
        return self.attributions.get(attribution_id)


def _materializer_fixtures() -> tuple[_MaterializerRepository, SimpleNamespace]:
    allocation = SimpleNamespace(
        allocation_decision_id="allocation-decision-1",
        status="SELECTED",
        account_id="account-1",
        mode="PAPER",
        decision_time_ns=100,
        opportunity_ref=_ref("opportunity", "opp-1"),
        strategy_match_ref=_ref("strategy_match", "match-1"),
        forecast_refs=(_ref("forecast", "forecast-1"),),
        cluster_ref=_ref("cluster", "cluster-1"),
        economic_assessment_ref=_ref("economic_assessment", "economics-1"),
        portfolio_snapshot_ref=_ref("paper_portfolio_snapshot", "snapshot-1"),
        allocation_intent_ref=_ref("capital_allocation_intent", "intent-1"),
        allocated_capital_minor=1_000,
    )
    match = SimpleNamespace(
        match_id="match-1",
        strategy_id="strategy-1",
        strategy_identity_hash="strategy-hash-1",
    )
    opportunity = SimpleNamespace(
        opportunity_id="opp-1",
        scope=SimpleNamespace(instrument_ids=("NVDA",)),
        side="LONG",
    )
    proposal = SimpleNamespace(
        proposal_id="proposal-1",
        requested_quantity=10,
        requested_notional_minor=1_000,
        reference_price_minor=100,
        lineage_refs=(
            _ref("allocation_decision", "allocation-decision-1"),
            _ref("trade_proposal", "proposal-1"),
        ),
    )
    risk = SimpleNamespace(
        risk_decision_id="risk-1",
        trade_proposal_id="proposal-1",
        approved_quantity=10,
        approved_notional_minor=1_000,
        lineage_refs=(
            _ref("allocation_decision", "allocation-decision-1"),
            _ref("risk_decision", "risk-1"),
        ),
    )
    repository = _MaterializerRepository(allocation, match, opportunity)
    repository.proposal = proposal
    repository.risk = risk
    return repository, SimpleNamespace(proposal=proposal, risk=risk)


def _append_materialized_order(
    ledger: PaperExecutionLedger,
    *,
    proposal: SimpleNamespace,
    risk: SimpleNamespace,
) -> str:
    intent = {
        "intent_id": "intent-event-1",
        "client_order_id": risk.risk_decision_id,
        "correlation_id": "opp-1",
        "created_time": 100,
        "desired_quantity": proposal.requested_quantity,
        "direction": "long",
        "instrument_id": "NVDA",
        "side": "BUY",
        "lineage_refs": [
            {"kind": "allocation_decision", "id": "allocation-decision-1"},
            {"kind": "trade_proposal", "id": proposal.proposal_id},
            {"kind": "risk_decision", "id": risk.risk_decision_id},
        ],
    }
    ledger.append_intent(intent)
    order = {
        "order_id": "order-1",
        "intent_id": intent["intent_id"],
        "instrument_id": "NVDA",
        "quantity": risk.approved_quantity,
        "state": "ACTIVATED",
        "lineage_refs": intent["lineage_refs"],
    }
    ledger.append_order(order, intent=intent)
    return str(order["order_id"])


class StrategyAttributionTests(unittest.TestCase):
    def test_netted_broker_position_keeps_strategy_slices_independent(self) -> None:
        first = _attribution(
            "attr-a",
            fills=(
                _fill("a-open", direction="LONG", quantity=10, price_minor=100, fill_time_ns=110),
                _fill("a-close", direction="SHORT", quantity=10, price_minor=150, fill_time_ns=120),
            ),
        )
        second = _attribution(
            "attr-b",
            fills=(
                _fill("b-open", direction="LONG", quantity=10, price_minor=200, fill_time_ns=110),
                _fill("b-close", direction="SHORT", quantity=10, price_minor=150, fill_time_ns=120),
            ),
        )

        self.assertEqual(first.trading_outcome.realized_pnl_minor, 500)
        self.assertEqual(second.trading_outcome.realized_pnl_minor, -500)
        self.assertEqual(first.trading_outcome.ending_position_quantity, 0)
        self.assertEqual(second.trading_outcome.ending_position_quantity, 0)

    def test_long_scale_in_scale_out_and_reversal_use_slice_cost_basis(self) -> None:
        record = _attribution(
            "scale-long",
            fills=(
                _fill("open-1", direction="LONG", quantity=10, price_minor=100, fill_time_ns=110),
                _fill("open-2", direction="LONG", quantity=10, price_minor=120, fill_time_ns=111),
                _fill("close-1", direction="SHORT", quantity=5, price_minor=130, fill_time_ns=112),
                _fill("close-2", direction="SHORT", quantity=15, price_minor=100, fill_time_ns=113),
            ),
        )
        self.assertEqual(record.trading_outcome.realized_pnl_minor, -50)
        self.assertEqual(record.trading_outcome.ending_position_quantity, 0)

        reversal = _attribution(
            "reverse-long",
            fills=(
                _fill("open", direction="LONG", quantity=10, price_minor=100, fill_time_ns=110),
                _fill("reverse", direction="SHORT", quantity=15, price_minor=120, fill_time_ns=111),
            ),
            allocation_quantity=5,
            allocation_direction="SHORT",
        )
        self.assertEqual(reversal.trading_outcome.realized_pnl_minor, 200)
        self.assertEqual(reversal.trading_outcome.ending_position_quantity, -5)
        self.assertEqual(reversal.trading_outcome.ending_cost_basis_minor, -600)

    def test_short_scale_in_scale_out_and_reversal_are_signed(self) -> None:
        record = _attribution(
            "scale-short",
            allocation_direction="SHORT",
            fills=(
                _fill("open-1", direction="SHORT", quantity=10, price_minor=125, fill_time_ns=110),
                _fill("open-2", direction="SHORT", quantity=10, price_minor=100, fill_time_ns=111),
                _fill("close-1", direction="LONG", quantity=5, price_minor=90, fill_time_ns=112),
                _fill("close-2", direction="LONG", quantity=15, price_minor=110, fill_time_ns=113),
            ),
        )
        self.assertEqual(record.trading_outcome.realized_pnl_minor, 150)
        self.assertEqual(record.trading_outcome.ending_position_quantity, 0)

        reversal = _attribution(
            "reverse-short",
            allocation_direction="LONG",
            fills=(
                _fill("open", direction="SHORT", quantity=10, price_minor=100, fill_time_ns=110),
                _fill("reverse", direction="LONG", quantity=15, price_minor=80, fill_time_ns=111),
            ),
            allocation_quantity=5,
        )
        self.assertEqual(reversal.trading_outcome.realized_pnl_minor, 200)
        self.assertEqual(reversal.trading_outcome.ending_position_quantity, 5)
        self.assertEqual(reversal.trading_outcome.ending_cost_basis_minor, 400)

    def test_explicit_initial_cost_basis_is_used_for_a_partial_close(self) -> None:
        record = _attribution(
            "initial-basis",
            allocation_direction="SHORT",
            allocation_quantity=10,
            fills=(
                _fill("close", direction="LONG", quantity=5, price_minor=100, fill_time_ns=110),
            ),
        )
        record = replace(
            record,
            initial_position_quantity=-10,
            initial_cost_basis_minor=-1_250,
        )

        self.assertEqual(record.trading_outcome.realized_pnl_minor, 125)
        self.assertEqual(record.trading_outcome.ending_position_quantity, -5)
        self.assertEqual(record.trading_outcome.ending_cost_basis_minor, -625)

    def test_lineage_is_explicit_prediction_and_trading_are_separate(self) -> None:
        record = _attribution(
            "lineage",
            fills=(_fill("fill-1", direction="LONG", quantity=2, price_minor=100, fill_time_ns=110),),
            prediction_outcome_refs=(_ref("outcome", "outcome-1"),),
        )
        payload = attribution_v1_to_dict(record)
        restored = attribution_v1_from_dict(payload)

        self.assertEqual(restored, record)
        self.assertEqual(restored.prediction_outcome_refs, (_ref("outcome", "outcome-1"),))
        self.assertEqual(restored.prediction_outcome_kind.value, "PREDICTION")
        self.assertEqual(restored.trading_outcome_kind.value, "TRADING")
        self.assertEqual(restored.trading_outcome.realized_pnl_minor, 0)
        self.assertEqual(payload["strategy_match_ref"]["id"], "match-lineage")
        self.assertEqual(payload["fill_refs"][0]["id"], "fill-1")
        self.assertNotIn("prediction_outcome", payload)

    def test_account_mode_and_point_in_time_guards_fail_closed(self) -> None:
        record = _attribution(
            "guards",
            fills=(_fill("fill-1", direction="LONG", quantity=1, price_minor=100, fill_time_ns=110),),
        )
        validate_attribution_scope(record, account_id="account-1", mode="PAPER", as_of_ns=110)
        for kwargs in (
            {"account_id": "other", "mode": "PAPER", "as_of_ns": 110},
            {"account_id": "account-1", "mode": "LIVE", "as_of_ns": 110},
            {"account_id": "account-1", "mode": "PAPER", "as_of_ns": 105},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    validate_attribution_scope(record, **kwargs)

    def test_repository_round_trip_is_immutable_and_account_scoped(self) -> None:
        record = _attribution("persist")
        repo = InMemoryIntelligenceRepository()

        self.assertEqual(repo.put_strategy_attribution(record), RepositoryPutResult.INSERTED)
        self.assertEqual(repo.put_strategy_attribution(record), RepositoryPutResult.ALREADY_PRESENT)
        self.assertEqual(repo.get_strategy_attribution(record.attribution_id), record)
        with self.assertRaises(ValueError):
            repo.get_strategy_attribution(
                record.attribution_id,
                account_id="other",
                mode="PAPER",
                as_of_ns=100,
            )
        with self.assertRaises(RepositoryConflictError):
            repo.put_strategy_attribution(replace(record, strategy_id="different"))

    def test_materializer_returns_none_when_selected_allocation_has_no_fill(self) -> None:
        repository, lineage = _materializer_fixtures()
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="materializer-no-fill",
            instrument_id="NVDA",
            symbol="NVDA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        _append_materialized_order(ledger, proposal=lineage.proposal, risk=lineage.risk)

        self.assertIsNone(
            materialize_strategy_attribution(
                repository=repository,
                ledger=ledger,
                allocation_decision_id="allocation-decision-1",
                proposal_id=lineage.proposal.proposal_id,
                risk_decision_id=lineage.risk.risk_decision_id,
                account_id="account-1",
                mode="PAPER",
                as_of_ns=200,
            )
        )

    def test_materializer_ignores_paper_fills_without_backend_lineage(self) -> None:
        repository, lineage = _materializer_fixtures()
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="materializer-unrelated",
            instrument_id="NVDA",
            symbol="NVDA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        intent = {
            "intent_id": "unrelated-intent",
            "client_order_id": "unrelated-risk",
            "correlation_id": "unrelated-opportunity",
            "created_time": 100,
            "desired_quantity": 10,
            "direction": "long",
            "instrument_id": "NVDA",
            "side": "BUY",
        }
        order = {
            "order_id": "unrelated-order",
            "intent_id": intent["intent_id"],
            "instrument_id": "NVDA",
            "quantity": 10,
            "state": "ACTIVATED",
        }
        ledger.append_intent(intent)
        ledger.append_order(order, intent=intent)
        ledger.append_fill(
            {
                "fill_id": "unrelated-fill",
                "order_id": order["order_id"],
                "instrument_id": "NVDA",
                "direction": "long",
                "fill_quantity": 10,
                "fill_price_minor": 100,
                "fill_time": 110,
            },
            order=order,
        )

        self.assertIsNone(
            materialize_strategy_attribution(
                repository=repository,
                ledger=ledger,
                allocation_decision_id="allocation-decision-1",
                proposal_id=lineage.proposal.proposal_id,
                risk_decision_id=lineage.risk.risk_decision_id,
                account_id="account-1",
                mode="PAPER",
                as_of_ns=200,
            )
        )

    def test_materializer_cumulates_fill_set_without_double_counting_account_pnl(self) -> None:
        repository, lineage = _materializer_fixtures()
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="materializer-cumulative",
            instrument_id="NVDA",
            symbol="NVDA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        order_id = _append_materialized_order(
            ledger,
            proposal=lineage.proposal,
            risk=lineage.risk,
        )
        ledger.policy["commission_minor_per_share"] = 2
        ledger.policy["fee_minor_per_order"] = 3
        entry_fill = {
            "fill_id": "fill-entry",
            "order_id": order_id,
            "instrument_id": "NVDA",
            "direction": "long",
            "fill_quantity": 10,
            "fill_price_minor": 100,
            "fill_time": 110,
        }
        ledger.append_fill(entry_fill, order={"order_id": order_id})
        first = materialize_strategy_attribution(
            repository=repository,
            ledger=ledger,
            allocation_decision_id="allocation-decision-1",
            proposal_id=lineage.proposal.proposal_id,
            risk_decision_id=lineage.risk.risk_decision_id,
            account_id="account-1",
            mode="PAPER",
            as_of_ns=200,
        )
        assert first is not None
        self.assertEqual(first.materialization_semantics, "CUMULATIVE")
        self.assertEqual(first.coverage_algorithm_version, "fill-set-coverage-v1")
        self.assertEqual(first.fill_refs, (_ref("fill", "fill-entry"),))
        self.assertEqual(first.trading_outcome.realized_pnl_minor, -23)

        exit_order = {
            "order_id": "order-2",
            "intent_id": "intent-event-2",
            "instrument_id": "NVDA",
            "quantity": 10,
            "state": "ACTIVATED",
            "lineage_refs": [
                {"kind": "allocation_decision", "id": "allocation-decision-1"},
                {"kind": "trade_proposal", "id": "proposal-1"},
                {"kind": "risk_decision", "id": "risk-1"},
            ],
        }
        exit_intent = {
            "intent_id": "intent-event-2",
            "client_order_id": "risk-1",
            "created_time": 120,
            "desired_quantity": 10,
            "direction": "short",
            "instrument_id": "NVDA",
            "side": "SELL",
            "lineage_refs": exit_order["lineage_refs"],
        }
        ledger.append_intent(exit_intent)
        ledger.append_order(exit_order, intent=exit_intent)
        ledger.append_fill(
            {
                "fill_id": "fill-partial-exit",
                "order_id": "order-2",
                "instrument_id": "NVDA",
                "direction": "short",
                "fill_quantity": 4,
                "fill_price_minor": 150,
                "fill_time": 130,
            },
            order=exit_order,
        )
        second = materialize_strategy_attribution(
            repository=repository,
            ledger=ledger,
            allocation_decision_id="allocation-decision-1",
            proposal_id=lineage.proposal.proposal_id,
            risk_decision_id=lineage.risk.risk_decision_id,
            account_id="account-1",
            mode="PAPER",
            as_of_ns=200,
        )
        assert second is not None
        self.assertNotEqual(first.attribution_id, second.attribution_id)
        self.assertEqual(
            {ref.id for ref in second.fill_refs},
            {"fill-entry", "fill-partial-exit"},
        )
        self.assertEqual(second.trading_outcome.realized_pnl_minor, 166)

        ledger.append_fill(
            {
                "fill_id": "fill-final-exit",
                "order_id": "order-2",
                "instrument_id": "NVDA",
                "direction": "short",
                "fill_quantity": 6,
                "fill_price_minor": 150,
                "fill_time": 140,
            },
            order=exit_order,
        )
        third = materialize_strategy_attribution(
            repository=repository,
            ledger=ledger,
            allocation_decision_id="allocation-decision-1",
            proposal_id=lineage.proposal.proposal_id,
            risk_decision_id=lineage.risk.risk_decision_id,
            account_id="account-1",
            mode="PAPER",
            as_of_ns=200,
        )
        assert third is not None
        self.assertNotEqual(second.attribution_id, third.attribution_id)
        self.assertEqual(
            {ref.id for ref in third.fill_refs},
            {"fill-entry", "fill-partial-exit", "fill-final-exit"},
        )
        self.assertEqual(third.trading_outcome.realized_pnl_minor, 454)
        self.assertEqual(
            ledger.project_account()["realized_pnl_minor"],
            third.trading_outcome.realized_pnl_minor,
        )
        self.assertIs(
            materialize_strategy_attribution(
                repository=repository,
                ledger=ledger,
                allocation_decision_id="allocation-decision-1",
                proposal_id=lineage.proposal.proposal_id,
                risk_decision_id=lineage.risk.risk_decision_id,
                account_id="account-1",
                mode="PAPER",
                as_of_ns=200,
            ),
            third,
        )

    def test_repository_lookup_returns_cumulative_snapshots_for_allocation(self) -> None:
        first = replace(
            _attribution(
                "allocation-snapshot-1",
                fills=(
                    _fill(
                        "fill-entry",
                        direction="LONG",
                        quantity=10,
                        price_minor=100,
                        fill_time_ns=110,
                    ),
                ),
            ),
            allocation_ref=_ref("allocation_decision", "allocation-decision-1"),
        )
        second = replace(
            first,
            attribution_id="allocation-snapshot-2",
            fill_refs=(),
            fills=(
                first.fills[0],
                _fill(
                    "fill-exit",
                    direction="SHORT",
                    quantity=10,
                    price_minor=150,
                    fill_time_ns=120,
                ),
            ),
        )
        repository = InMemoryIntelligenceRepository()
        empty = replace(
            _attribution("allocation-snapshot-empty"),
            allocation_ref=_ref("allocation_decision", "allocation-decision-1"),
        )
        repository.put_strategy_attribution(empty)
        repository.put_strategy_attribution(first)
        repository.put_strategy_attribution(second)

        snapshots = repository.get_strategy_attributions_by_allocation(
            "allocation-decision-1",
            account_id="account-1",
            mode="PAPER",
        )
        self.assertEqual(
            tuple(snapshot.attribution_id for snapshot in snapshots),
            (
                "allocation-snapshot-empty",
                "allocation-snapshot-1",
                "allocation-snapshot-2",
            ),
        )
        self.assertEqual(
            get_latest_complete_strategy_attribution(
                repository,
                "allocation-decision-1",
                account_id="account-1",
                mode="PAPER",
            ).attribution_id,
            "allocation-snapshot-2",
        )

    def test_materializer_rejects_fill_before_allocation_decision(self) -> None:
        repository, lineage = _materializer_fixtures()
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="materializer-temporal",
            instrument_id="NVDA",
            symbol="NVDA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        order_id = _append_materialized_order(
            ledger,
            proposal=lineage.proposal,
            risk=lineage.risk,
        )
        ledger.append_fill(
            {
                "fill_id": "fill-too-early",
                "order_id": order_id,
                "instrument_id": "NVDA",
                "direction": "long",
                "fill_quantity": 10,
                "fill_price_minor": 100,
                "fill_time": 99,
            },
            order={"order_id": order_id},
        )

        with self.assertRaises(AttributionMaterializationError):
            materialize_strategy_attribution(
                repository=repository,
                ledger=ledger,
                allocation_decision_id="allocation-decision-1",
                proposal_id=lineage.proposal.proposal_id,
                risk_decision_id=lineage.risk.risk_decision_id,
                account_id="account-1",
                mode="PAPER",
                as_of_ns=200,
            )


if __name__ == "__main__":
    unittest.main()
