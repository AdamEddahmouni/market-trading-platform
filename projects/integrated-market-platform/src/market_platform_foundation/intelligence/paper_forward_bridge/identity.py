"""Deterministic forward-test identities."""

from __future__ import annotations

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes


def forward_test_session_id(
    *,
    account_id: str,
    strategy_id: str,
    strategy_version: str,
    created_at_ns: int,
    universe: tuple[str, ...],
) -> str:
    digest = sha256_bytes(
        canonical_bytes(
            {
                "account_id": account_id,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "created_at_ns": created_at_ns,
                "universe": list(universe),
            }
        )
    )
    return f"fts-{digest[:16]}"


def forward_test_decision_id(
    *,
    account_id: str,
    session_id: str | None,
    symbol: str,
    decision_time_ns: int,
    strategy_id: str,
    strategy_version: str,
    direction: str,
) -> str:
    digest = sha256_bytes(
        canonical_bytes(
            {
                "account_id": account_id,
                "session_id": session_id,
                "symbol": symbol,
                "decision_time_ns": decision_time_ns,
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "direction": direction,
            }
        )
    )
    return f"ftd-{digest[:16]}"


def forward_test_observation_id(
    *,
    forward_test_id: str,
    observed_at_ns: int,
    source_time_ns: int,
) -> str:
    digest = sha256_bytes(
        canonical_bytes(
            {
                "forward_test_id": forward_test_id,
                "observed_at_ns": observed_at_ns,
                "source_time_ns": source_time_ns,
            }
        )
    )
    return f"fto-{digest[:16]}"
