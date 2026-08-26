"""Generate BUILD 30 supervised live operations artifacts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.live_canary import (
    build_default_program_policy,
    build_program_report,
    run_mock_incident_lifecycle,
    run_mock_program_lifecycle,
)
from market_platform_foundation.intelligence.live_canary.program_policy import BUILD30_KNOWN_LIMITATIONS
from market_platform_foundation.intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractKind,
    ContractReference,
)
from market_platform_foundation.intelligence.contracts.trade_proposal import TradeProposalV1
from market_platform_foundation.intelligence.execution.types import (
    ExposureSnapshot,
    RiskDecisionKind,
    RiskDecisionV1,
    RiskReasonCode,
)
from tests.intelligence.execution_fixtures import sample_opportunity

T = 1_700_000_000_000_000_000
OUT = ROOT / "artifacts" / "supervised-live-operations"


def _proposal_and_risk() -> tuple[TradeProposalV1, RiskDecisionV1]:
    proposal = TradeProposalV1(
        proposal_id="tp-build30",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        opportunity_id="opp-build30",
        execution_policy_id="ep-1",
        instrument_id="inst-aapl",
        side="BUY",
        requested_quantity=1,
        requested_notional_minor=25_00,
        reference_price_minor=25_00,
        proposal_time_ns=T,
        expires_at_ns=T + 600_000_000_000,
        execution_mode="PAPER",
        opportunity_ref=ContractReference(kind=ContractKind.OPPORTUNITY.value, id="opp-build30"),
        metadata={"buying_power_minor": 1_000_000_00},
    )
    risk = RiskDecisionV1(
        risk_decision_id="risk-build30",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        trade_proposal_id="tp-build30",
        opportunity_id="opp-build30",
        execution_policy_id="ep-1",
        portfolio_snapshot_id="port-1",
        decision_time_ns=T,
        requested_quantity=1,
        requested_notional_minor=25_00,
        approved_quantity=1,
        approved_notional_minor=25_00,
        decision=RiskDecisionKind.APPROVE,
        reason_codes=(RiskReasonCode.RISK_APPROVED,),
        pre_trade_exposure=ExposureSnapshot(gross_exposure_minor=0, net_exposure_minor=0),
    )
    return proposal, risk


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    program_policy = build_default_program_policy(program_effective_from_ns=T)
    policy_path = OUT / "BUILD30_PROGRAM_POLICY.json"
    policy_path.write_text(
        json.dumps(
            {
                "program_policy_id": program_policy.program_policy_id,
                "max_sessions": program_policy.max_sessions,
                "max_program_order_count": program_policy.max_program_order_count,
                "max_program_live_notional_minor": program_policy.max_program_live_notional_minor,
                "require_fresh_authorization_per_session": program_policy.require_fresh_authorization_per_session,
                "require_order_confirmation": program_policy.require_order_confirmation,
                "minimum_cooldown_between_sessions_ns": program_policy.minimum_cooldown_between_sessions_ns,
                "program_effective_until_ns": program_policy.program_effective_until_ns,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    proposal, risk = _proposal_and_risk()
    opp = sample_opportunity(opportunity_id="opp-build30")
    result = run_mock_program_lifecycle(
        program_start_ns=T,
        trade_proposal=proposal,
        risk_decision=risk,
        opportunity=opp,
        reference_price_minor=25_00,
    )

    manifest = {
        "program_run_id": result.program_run.program_run_id,
        "program_policy_ref": result.program_run.program_policy_ref,
        "session_refs": [s.session_ref for s in result.session_results],
        "disposition": result.disposition.value,
    }
    (OUT / "BUILD30_PROGRAM_RUN_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    session_index = [
        {
            "session_id": s.session_ref,
            "authorization_ref": s.authorization_id,
            "order_count": s.session_report.submit_attempts,
            "fill_count": s.session_report.fills,
            "incident_count": len(s.incidents),
            "reconciliation_status": s.session_report.reconciliation_checkpoint_ref,
            "disposition": s.disposition.value,
        }
        for s in result.session_results
    ]
    (OUT / "BUILD30_SESSION_INDEX.json").write_text(
        json.dumps(session_index, indent=2), encoding="utf-8"
    )

    incident_gate, incidents, _ = run_mock_incident_lifecycle(program_start_ns=T)
    incident_index = [
        {
            "incident_id": i.incident_id,
            "severity": i.severity.value,
            "state": i.state.value,
            "detected_at_ns": i.detected_at_ns,
        }
        for i in incidents
    ]
    (OUT / "BUILD30_INCIDENT_INDEX.json").write_text(
        json.dumps(incident_index, indent=2), encoding="utf-8"
    )

    recon_evidence = {
        "checkpoint_count": len(result.session_results),
        "total_fills": result.accounting.total_fills,
        "restart_events": result.program_report.restart_events,
    }
    (OUT / "BUILD30_RECONCILIATION_EVIDENCE.json").write_text(
        json.dumps(recon_evidence, indent=2), encoding="utf-8"
    )

    program_report_path = OUT / "BUILD30_PROGRAM_REPORT.json"
    program_report_path.write_text(
        json.dumps(
            {
                "program_report_id": result.program_report.program_report_id,
                "disposition": result.program_report.disposition.value,
                "sessions_executed": result.program_report.sessions_executed,
                "total_orders": result.program_report.total_orders,
                "total_fills": result.program_report.total_fills,
                "aggregate_notional_minor": result.program_report.aggregate_notional_minor,
                "final_kill_switch_state": result.program_report.final_kill_switch_state,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    limitations_path = OUT / "BUILD30_KNOWN_LIMITATIONS.md"
    limitations_path.write_text(
        "# BUILD 30 Known Limitations\n\n"
        + "\n".join(f"- {lim}" for lim in BUILD30_KNOWN_LIMITATIONS)
        + "\n\n- REAL_REPEATED_CANARY_NOT_EXECUTED\n"
        + "- NO_EXPLICIT_HUMAN_SESSION_AUTHORIZATION_FOR_REAL_ORDERS\n",
        encoding="utf-8",
    )

    hashes = {}
    for p in sorted(OUT.glob("BUILD30_*")):
        hashes[str(p.relative_to(ROOT)).replace("\\", "/")] = file_hash(p)
    (OUT / "BUILD30_FILE_HASHES.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )
    print(json.dumps({"artifacts": str(OUT), "disposition": result.disposition.value}))


if __name__ == "__main__":
    main()
