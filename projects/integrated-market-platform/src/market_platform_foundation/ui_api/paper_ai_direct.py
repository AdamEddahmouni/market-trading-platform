"""Owner-authorized AI-direct Paper entries: a gated model ENTER may proceed without a forecast Opportunity.

Off unless ``IMP_PAPER_AI_DIRECT=1`` and the ledger is the internal simulator. Every other gate stays: grounding,
direction support, quote freshness, position legality, Paper authority, the owner's automation risk policy, the
ledger hard caps and the BUILD 22 pre-trade engine. The engine needs an Opportunity, so one is built in memory from
the Action Decision itself (side, decision time, validity) and marked AI_PROPOSAL_DIRECT. It is never persisted to
the strategy repository, so it can never be found by a later candidate's Opportunity lookup.
"""

from __future__ import annotations

import os

from ..intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    QualityState,
    QualitySummary,
)
from ..intelligence.contracts.opportunity import OpportunityV1
from ..intelligence.inference.hashing import input_hash_from_dict
from ..market_data.freshness_contract import timestamp

ENV_FLAG = "IMP_PAPER_AI_DIRECT"
ORIGIN = "AI_PROPOSAL_DIRECT"


def ai_direct_enabled(ledger, environ=os.environ) -> bool:
    from ..operating_modes import paper_execution_env_enabled

    return bool(environ.get(ENV_FLAG) == "1" and paper_execution_env_enabled()
                and getattr(ledger, "execution_mode", None) == "INTERNAL_SIMULATION")


def _ns(value) -> int:
    return int(timestamp(value).timestamp() * 1e9)


def direct_opportunity(record) -> OpportunityV1:
    """The in-memory Opportunity a direct ENTER is assessed against. Deterministic per decision."""
    if record.get("action_state") != "ENTER" or record.get("direction") not in ("LONG", "SHORT"):
        raise ValueError("AI_DIRECT_ENTRY_REQUIRED")
    return OpportunityV1(
        opportunity_id="OPP-AID-" + input_hash_from_dict(dict(decision_id=record["decision_id"]))[:32],
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=IntelligenceScope(instrument_ids=(str(record["instrument_id"]),)),
        created_at_ns=_ns(record["decision_time"]),
        valid_until_ns=_ns(record["valid_until"]),
        quality=QualitySummary(state=QualityState.UNKNOWN, flags=("NO_FORECAST",)),
        opportunity_type=ORIGIN,
        side=OpportunitySide(record["direction"]),
        reason_summary=str(record.get("rationale") or "")[:240] or None,
        lineage_refs=(ContractReference("ActionDecisionV1", str(record["decision_id"])),),
        metadata=dict(origin=ORIGIN, decision_id=str(record["decision_id"])),
    )
