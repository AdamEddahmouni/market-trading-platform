# EVIDENCE-01A — Real Forward Observation Campaign

> Operational evidence accumulation for the frozen EVIDENCE-01 qualification policy.

## Purpose

EVIDENCE-01A makes the EVIDENCE-01 qualification machinery operational against genuine forward observations collected across multiple sessions and days.

EVIDENCE-01A implementation completion does **not** close `INSUFFICIENT_FORWARD_EVIDENCE`. Only accumulation of genuine forward evidence satisfying all frozen EVIDENCE-01 gates can close it.

## Relationship to EVIDENCE-01

| Layer | Role |
| --- | --- |
| EVIDENCE-01 | Frozen sufficiency policy (`FEPOL-...`) and deterministic assessment |
| EVIDENCE-01A | Campaign orchestration, persistence, checkpoints, operator tooling |

Policy thresholds are frozen. Do not change them in response to observed campaign performance.

## Campaign lifecycle

```text
PLANNED → ACTIVE → (sessions) → EVIDENCE_INSUFFICIENT | QUALIFIED → FINALIZED
                     ↓
                   PAUSED / ABORTED / INVALIDATED
```

## Real vs fixture evidence

| Origin | Qualifies for real EVIDENCE-01 closure |
| --- | --- |
| `LIVE_FORWARD` | YES |
| `FIXTURE` | NO |
| `REPLAY` | NO |
| `SYNTHETIC` | NO (mechanism tests only) |

## Session semantics

A session counts toward the five-session requirement only when:

- duration ≥ 5 minutes (`MIN_QUALIFYING_SESSION_DURATION_NS`)
- eligible predictions ≥ 1

This prevents trivial process-restart gaming.

## Operator commands

```powershell
$env:PYTHONPATH='src'

# Create campaign (execution disabled)
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py create --name "forward-pilot-1"

# Start campaign and session
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py start --campaign-dir artifacts/forward-qualification/campaigns/<id>
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py session-start --campaign-dir ...

# Inspect progress (settlement rate shows NOT_EVALUABLE when eligible=0)
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py status --campaign-dir ...

# Settle mature outcomes, stop session, checkpoint
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py settle --campaign-dir ...
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py session-stop --campaign-dir ...
.venv\Scripts\python.exe tools/forward_qualification/forward_campaign.py checkpoint --campaign-dir ...
```

## Persistence

Campaign artifacts live under:

`artifacts/forward-qualification/campaigns/<campaign_id>/`

- `CAMPAIGN_SPEC.json` — immutable campaign definition
- `CAMPAIGN_RUNTIME_STATE.json` — lifecycle state
- `OBSERVATIONS.jsonl` — append-only observation refs
- `intelligence_records.jsonl` — forecasts, ledger entries, outcomes for restart recovery
- `sessions/SESSION_*.json`
- `checkpoints/CHECKPOINT_*.json`

## Safety invariants

- Autonomous live trading: **DISABLED**
- `execution_mode = NONE`, `execution_authority = BLOCKED`
- Orders submitted by campaign: **0**
- No model retraining, recalibration, or promotion during campaign

## Settlement rate semantics

When `eligible_predictions = 0`, settlement rate is `NOT_EVALUABLE` (not a measured 0%).

## Known limitations

- Real provider smoke requires local Moomoo/OpenD configuration
- Single-host JSONL persistence; not HA
- BUILD34 supervisor integration: campaign is operator-driven CLI (no background service fiction)

## Validation

`tests/intelligence/test_evidence01a_forward_campaign.py`
