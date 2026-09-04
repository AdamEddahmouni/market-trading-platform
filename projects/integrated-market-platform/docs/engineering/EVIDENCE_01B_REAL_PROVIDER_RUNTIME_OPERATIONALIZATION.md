# EVIDENCE-01B — Real-Provider Integration, Durable Campaign Runtime & Operational Control

Status: **implemented** (operationalization milestone; not qualification closure).

## Objective

EVIDENCE-01B closes the gap between the EVIDENCE-01A campaign framework (deterministic tests)
and an operationally capable runtime that can accumulate trustworthy real forward evidence
across multiple sessions and days without manual babysitting.

This milestone does **not** require five completed trading days of real evidence.
It builds the runtime architecture required before a later qualification campaign (EVIDENCE-01C shakedown).

## Relationship to prior milestones

| Milestone | Scope |
|---|---|
| EVIDENCE-01 | Frozen qualification policy (`FEPOL-2f34a5a175890869faa8456a9af2a49244ed702ac667bd495f590de266cc165e`) |
| EVIDENCE-01A | Campaign framework, sessions, checkpoints, operator CLI, `LIVE_FORWARD` origin enforcement |
| EVIDENCE-01B | Real-provider bridge, durable runtime, settlement/checkpoint workers, health, continuity, preflight, shakedown |
| EVIDENCE-01C | Bounded real-provider shakedown and operational acceptance (next) |

## Provider choice

**MOOMOO (OpenD)** is the authoritative first provider:

- Mature observational path via `LiveObservationalRuntime` (`market_data/live_runtime.py`)
- Push feed, reconnect, subscription quota, quality admission
- Read-only; no execution authority
- Documented in `docs/providers/MOOMOO_OBSERVATIONAL.md`

Provider bridge: `evidence01b/provider_bridge.py` maps runtime admission results to campaign quality states.

## Runtime architecture

```text
CampaignRuntimeService (operator CLI)
        ↓
CampaignRuntime (orchestration)
        ↓
├── FakeProviderAdapter / LiveObservationalRuntime (MOOMOO)
├── CampaignService (EVIDENCE-01A)
├── SettlementWorker → OutcomeSettlementService
├── CampaignRuntimeStore (durable JSONL + runtime artifacts)
└── Health / Preflight / Events
```

Startup order:

1. Persistence available
2. Configuration snapshot frozen (`CONFIGURATION_SNAPSHOT.json`)
3. Preflight passes
4. Campaign state ACTIVE
5. Provider connected (or fake adapter in tests)
6. Session opened
7. Settlement/checkpoint loops on tick

## Configuration freeze

`CampaignConfigurationSnapshotV1` captures:

- `campaign_configuration_fingerprint` (`CFGFP-…`)
- policy, source SHA, provider, universe, predictor, settlement/quality/calendar identities
- execution authority (`BLOCKED`)

Semantic drift (predictor, provider, universe, policy) blocks resume.
Non-semantic source SHA changes are tolerated when fingerprint is unchanged.

## Continuity semantics

`evidence01/continuity.py` implements **expected-observation-window-aware** gap calculation:

- US equity regular session 09:30–16:00 ET
- Weekends and frozen holidays excluded from qualifying gap
- Qualifying gap = longest span within expected observation windows between consecutive decisions
- Raw wall-clock gaps spanning weekends/overnight do not automatically fail the 24-hour policy threshold

Gap categories (`evidence01b/continuity.py`): `EXPECTED_MARKET_CLOSURE`, `PROVIDER_DISCONNECT`, `RUNTIME_DOWN`, `UNKNOWN`, etc.

## Session qualification

Sessions require (EVIDENCE-01A rules, unchanged):

- `eligible_prediction_count >= 1`
- `duration >= 5 minutes`

Empty restart sessions do not satisfy the five-session requirement.

## Settlement automation

`SettlementWorker` uses canonical `OutcomeSettlementService`:

- Skips immature predictions
- Idempotent settlement
- Bounded retries (`MAX_SETTLEMENT_RETRIES = 5`)
- Backlog exposed in health

## Checkpoint automation

Triggers: session close, explicit operator request, runtime tick (30-minute minimum interval).

## Campaign health

States: `HEALTHY_AND_ACCUMULATING`, `WAITING_FOR_MARKET`, `PROVIDER_DISCONNECTED`, `SETTLEMENT_BACKLOG`, `CONTINUITY_AT_RISK`, `PAUSED`, `INVALIDATED`, etc.

Market closed → `INFO`, not failure.

## Shakedown mode

`REAL_FORWARD_SHAKEDOWN` via `shakedown start` — exercises runtime with real provider data, excluded from qualification cohort.

Statuses: `SHAKEDOWN_NOT_STARTED` → `SHAKEDOWN_ACTIVE` → `SHAKEDOWN_PASSED` / `SHAKEDOWN_FAILED`.

## Operator CLI

Extended `tools/forward_qualification/forward_campaign.py`:

```text
create | preflight | start | pause | resume
session-start | session-stop | settle | checkpoint
status | health | shakedown | finalize | abort | invalidate
```

## Safety guarantees

```text
autonomous_live_trading = DISABLED
human_session_authorization = REQUIRED
per_order_confirmation = REQUIRED
orders_submitted_by_evidence_runtime = 0
automatic_broker_failover = DISABLED
```

## Known limitations

- Real-provider end-to-end smoke requires local OpenD credentials and market hours
- Mongo durable backend not wired; campaign uses file-backed JSONL (accepted EVIDENCE-01A mode)
- BUILD34 background supervisor not used; runtime is operator-driven with heartbeat persistence
- Predictor integration from live events is bridged but full forecast pipeline requires active session + market data

## Validation

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.intelligence.test_evidence01b_forward_runtime -v
.venv\Scripts\python.exe -m unittest tests.intelligence.test_evidence01a_forward_campaign -v
.venv\Scripts\python.exe -m unittest tests.intelligence.test_evidence01_forward_qualification -v
.venv\Scripts\python.exe tools/validate.py changed
.venv\Scripts\python.exe tools/validate.py full
```
