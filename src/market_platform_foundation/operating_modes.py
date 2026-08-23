"""Orthogonal operating-mode semantics for platformization."""

from __future__ import annotations

from typing import Any

DATA_MODES: tuple[str, ...] = (
    "FIXTURE_REPLAY",
    "HISTORICAL_CAPTURE",
    "LIVE_OBSERVATIONAL",
    "BROKER_DELAYED",
)

EXECUTION_MODES: tuple[str, ...] = (
    "NONE",
    "INTERNAL_SIMULATION",
    "BROKER_PAPER",
    "LIVE",
)

EXECUTION_AUTHORITIES: tuple[str, ...] = (
    "BLOCKED",
    "AUTHORIZED",
    "PAPER_ONLY",
)

PAPER_EXECUTION_AUTHORITIES: frozenset[str] = frozenset({"AUTHORIZED", "PAPER_ONLY"})

PROVIDER_IDS: tuple[str, ...] = (
    "INTERNAL",
    "MOOMOO",
    "TRADIER",
    "IBKR",
    "ALPACA",
)


def legacy_mode_label(*, data_mode: str, execution_mode: str) -> str:
    """Derive UI-001 compatible single mode label from orthogonal dimensions."""

    if execution_mode == "LIVE":
        return "LIVE"
    if execution_mode == "BROKER_PAPER":
        return "PAPER"
    if execution_mode == "INTERNAL_SIMULATION":
        return "SIMULATION"
    if data_mode == "FIXTURE_REPLAY":
        return "REPLAY"
    if data_mode == "LIVE_OBSERVATIONAL":
        return "LIVE"
    return "REPLAY"


def build_operating_context(
    *,
    as_of_time: str,
    timezone: str,
    replay_session_id: str | None,
    data_mode: str = "FIXTURE_REPLAY",
    execution_mode: str = "NONE",
    execution_authority: str = "BLOCKED",
    data_provider: str = "INTERNAL",
    execution_provider: str | None = None,
) -> dict[str, Any]:
    if data_mode not in DATA_MODES:
        raise ValueError("OPERATING_DATA_MODE_INVALID")
    if execution_mode not in EXECUTION_MODES:
        raise ValueError("OPERATING_EXECUTION_MODE_INVALID")
    if execution_authority not in EXECUTION_AUTHORITIES:
        raise ValueError("OPERATING_EXECUTION_AUTHORITY_INVALID")
    if data_provider not in PROVIDER_IDS:
        raise ValueError("OPERATING_DATA_PROVIDER_INVALID")
    if execution_provider is not None and execution_provider not in PROVIDER_IDS:
        raise ValueError("OPERATING_EXECUTION_PROVIDER_INVALID")

    ctx: dict[str, Any] = {
        "as_of_time": as_of_time,
        "data_mode": data_mode,
        "data_provider": data_provider,
        "execution_authority": execution_authority,
        "execution_mode": execution_mode,
        "mode": legacy_mode_label(data_mode=data_mode, execution_mode=execution_mode),
        "timezone": timezone,
    }
    if replay_session_id:
        ctx["replay_session_id"] = replay_session_id
    if execution_provider:
        ctx["execution_provider"] = execution_provider
    return ctx


def live_execution_env_enabled() -> bool:
    import os

    return os.environ.get("IMP_LIVE_EXECUTION") == "1"


def paper_execution_env_enabled() -> bool:
    import os

    return os.environ.get("IMP_PAPER_EXECUTION") == "1"


def broker_paper_execution_env_enabled() -> bool:
    import os

    return os.environ.get("IMP_BROKER_PAPER_EXECUTION") == "1"


def resolve_execution_authority(*, requested_mode: str) -> str:
    if requested_mode == "LIVE":
        return "AUTHORIZED" if live_execution_env_enabled() else "BLOCKED"
    if requested_mode == "INTERNAL_SIMULATION":
        return "AUTHORIZED" if paper_execution_env_enabled() else "BLOCKED"
    if requested_mode == "BROKER_PAPER":
        # Audit F4: broker paper runs under its own distinct gate and authority
        # (PAPER_ONLY), separate from INTERNAL_SIMULATION's AUTHORIZED.
        return "PAPER_ONLY" if broker_paper_execution_env_enabled() else "BLOCKED"
    return "BLOCKED"
