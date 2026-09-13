"""Query/reconstruction access for campaign forward-test evidence."""

from __future__ import annotations

from typing import Any

from ...local_state.connection import LocalStateConnection
from .evaluation import compute_signal_outcome, extract_prices_from_observations
from .paper_ledger_join import paper_execution_from_ledger, paper_execution_from_observations
from .sqlite_repository import SqliteForwardTestRepository


def reconstruct_campaign(
    connection: LocalStateConnection,
    *,
    account_id: str,
    campaign_id: str,
) -> dict[str, Any]:
    repo = SqliteForwardTestRepository(connection)
    sessions = [
        session
        for session in repo.list_sessions(account_id=account_id)
        if session.campaign_id == campaign_id
    ]
    decisions = repo.list_decisions(account_id=account_id, campaign_id=campaign_id)
    reconstructed: list[dict[str, Any]] = []
    for decision in decisions:
        entry_price, exit_price = extract_prices_from_observations(decision.observations)
        signal = compute_signal_outcome(
            decision=decision,
            entry_price=entry_price,
            exit_price=exit_price,
        )
        obs_realized, obs_fills = paper_execution_from_observations(
            tuple(item.payload for item in decision.observations)
        )
        ledger_realized, ledger_fills, unrealized = paper_execution_from_ledger(
            connection,
            paper_order_id=decision.paper_order_id,
        )
        realized = ledger_realized if ledger_realized is not None else obs_realized
        fill_count = ledger_fills if ledger_fills else obs_fills
        reconstructed.append(
            {
                "forward_test_id": decision.forward_test_id,
                "session_id": decision.session_id,
                "symbol": decision.symbol,
                "strategy_id": decision.strategy_id,
                "state": decision.state.value,
                "paper_order_id": decision.paper_order_id,
                "signal_outcome": signal.to_dict(),
                "realized_pnl_minor": realized,
                "unrealized_pnl_minor": unrealized,
                "fill_count": fill_count,
                "observation_count": len(decision.observations),
                "git_sha": (decision.provenance_snapshot or {}).get("git_sha"),
                "simulator_version": (decision.provenance_snapshot or {}).get("simulator_version"),
            }
        )
    return {
        "account_id": account_id,
        "campaign_id": campaign_id,
        "session_count": len(sessions),
        "sessions": [session.to_dict() for session in sessions],
        "decision_count": len(decisions),
        "decisions": reconstructed,
    }
