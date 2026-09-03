"""Live execution kill switch (BUILD 28 default ACTIVE_BLOCK)."""

from __future__ import annotations

from .identity import derive_kill_switch_id
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    KillSwitchState,
    LiveExecutionKillSwitchV1,
)

BUILD28_KILL_SWITCH_SCOPE = "LIVE_EXECUTION_GLOBAL"


def build_production_kill_switch(*, effective_from_ns: int) -> LiveExecutionKillSwitchV1:
    """BUILD 28 mandatory default: live submission blocked."""
    ks = LiveExecutionKillSwitchV1(
        kill_switch_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        scope=BUILD28_KILL_SWITCH_SCOPE,
        state=KillSwitchState.ACTIVE_BLOCK,
        reason="BUILD28_ZERO_SUBMIT_MANDATORY",
        effective_from_ns=effective_from_ns,
        source="BUILD28_PRODUCTION_CONFIG",
        lineage={"build": "BUILD_28"},
    )
    object.__setattr__(ks, "kill_switch_id", derive_kill_switch_id(ks))
    return ks


def build_test_inactive_kill_switch(*, effective_from_ns: int) -> LiveExecutionKillSwitchV1:
    """Isolated test-only inactive kill switch — never production default."""
    ks = LiveExecutionKillSwitchV1(
        kill_switch_id="",
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        scope=BUILD28_KILL_SWITCH_SCOPE,
        state=KillSwitchState.INACTIVE,
        reason="BUILD28_ISOLATED_TEST_FIXTURE",
        effective_from_ns=effective_from_ns,
        source="BUILD28_TEST_CONFIG",
        lineage={"isolated_test_fixture": True},
    )
    object.__setattr__(ks, "kill_switch_id", derive_kill_switch_id(ks))
    return ks
