# Supervised Production Pilot V1 (BUILD 33)

> **BUILD 33 is a bounded supervised production pilot.** It validates sustained operational behavior, data-provider redundancy, degraded-mode safety, runbooks, and reliability discipline **without reducing human authorization or per-order confirmation**.

## Purpose

BUILD 32 established operational reliability (health, SLOs, alerts, backup, restore, DR). BUILD 33 answers:

> Can the complete system remain safe, coherent, observable, reconciled, and operationally manageable during sustained supervised operation across market sessions, provider degradation, reconnects, maintenance events, process restarts, and operator handoff cycles?

BUILD 33 is **not** unrestricted production rollout, **not** autonomous live trading, and **not** permission to remove human controls.

## Core Contracts

| Contract | Role |
| --- | --- |
| `LiveSupervisedPilotPolicyV1` | Immutable pilot envelope: caps, cadence, provider set, human controls |
| `LiveSupervisedPilotRunV1` | Pilot run lineage and initial snapshots |
| `ProviderRedundancyPolicyV1` | Deterministic primary/fallback routing per capability |
| `ProviderSelectionDecisionV1` | Auditable provider selection with provenance |
| `ProviderDivergenceAssessmentV1` | Cross-provider diagnostic comparison |
| `BrokerRedundancyAssessmentV1` | Advisory broker overlap — **AUTO_FAILOVER = NOT_AUTHORIZED** |
| `OperationalPilotCheckpointV1` | Periodic immutable operational snapshot |
| `PilotOperationalReviewV1` | Human-reviewable summary — does not authorize orders |
| `RunbookExerciseSpecV1` / `RunbookExerciseReportV1` | Testable procedures RB01–RB20 |
| `SustainedPilotQualificationSpecV1` / `ReportV1` | Honest qualification evidence |

## Provider Authority

- **One authoritative provider per capability** at each decision point
- Primary selected when healthy and fresh
- Fallback only after sustained primary failure (failure-duration threshold)
- Fallback must independently satisfy health **and** freshness
- Recovery requires stable primary health (recovery hysteresis) before switch-back
- Switch cooldown prevents flapping
- Every selection recorded in `ProviderSelectionDecisionV1` — no invisible fallback
- Historical events retain original provider attribution — no history rewrite

## Provider Failover vs Broker Failover

| Domain | Behavior |
| --- | --- |
| **Market-data failover** | May be deterministic per frozen `ProviderRedundancyPolicyV1` |
| **Live broker failover** | **NOT AUTOMATIC** — `BrokerRedundancyAssessmentV1.auto_failover_authorization = NOT_AUTHORIZED` |

After ambiguous submission to Broker A, **never** send equivalent order to Broker B.

## Degraded Mode (`PILOT_DEGRADED`)

Entered when fallback provider is active or non-critical dependencies degrade.

- Status is explicit — degraded ≠ healthy
- May reduce functionality (e.g., block order-flow-dependent opportunities)
- **Cannot expand authority** — human authorization and per-order confirmation unchanged

## Pilot Checkpoints

Produced on frozen cadence from `LiveSupervisedPilotPolicyV1.required_operational_checkpoint_interval_ns`.

Contents include: provider health, selection state, divergence, broker/reconciliation, persistence, SLO, alerts, kill switches, exposure, backup freshness, incidents.

Missed checkpoints are observable operational issues — not silently green.

## Pilot Caps

Pilot caps are **additional ceilings** over BUILD 22/29/30. Take the most restrictive.

Cumulative counters **never reset**. Success does not increase caps.

## Runbooks (RB01–RB20)

| ID | Title |
| --- | --- |
| RB01 | Primary market-data provider outage |
| RB02 | Provider divergence |
| RB03 | Provider failover and recovery |
| RB04 | Broker connectivity loss |
| RB05 | Ambiguous broker submission |
| RB06 | Broker/local order mismatch |
| RB07 | External/manual broker activity |
| RB08 | Partial fill + runtime restart |
| RB09 | Persistence/database outage |
| RB10 | Operator control-plane unavailable |
| RB11 | Telemetry/observability outage |
| RB12 | Critical alert delivery failure |
| RB13 | Global kill switch activation |
| RB14 | Program/session kill switch activation |
| RB15 | Backup restore / cold recovery |
| RB16 | Stale restored state + broker reconciliation |
| RB17 | Account/environment mismatch |
| RB18 | Authorization expiry during active session |
| RB19 | Unexpected live position |
| RB20 | Graceful pilot shutdown |

Runbooks must not instruct: force submit, ignore reconciliation, retry until success, disable kill switch, switch broker and resend.

## Maintenance / Restart

Planned maintenance procedure:

1. Block new submits
2. Reconcile broker/account
3. Persist canonical state
4. Shutdown — restart **blocked**
5. Post-restart health + reconciliation
6. Operator review
7. Fresh BUILD 29/30 authorization only afterward

**No auto-resume. No auto-submit.**

## Pilot End

At pilot end:

- Stop authorizing new sessions
- Reconcile broker/account
- Final checkpoint and qualification report
- Live remains blocked without new authorization

## Evidence Limitations

See `artifacts/supervised-production-pilot/BUILD33_KNOWN_LIMITATIONS.md`.

Typical limitations:

- Pilot duration shorter than desired multi-day target
- Provider redundancy fixture-tested when only one live provider available
- No alternate live broker certified
- Few or zero separately authorized live orders
- Single-host local qualification

## BUILD 34 Boundary

A future BUILD 34 should focus on deployment packaging, service supervision, environment promotion, and change control — **not** increased trading autonomy.

## Package Location

```
src/market_platform_foundation/intelligence/live_canary/supervised_production_pilot/
```

## API

- `GET /canary/pilot` — read-only pilot snapshot (operator control plane)

## Canonical Laws

```
pilot ready ≠ order authorized
provider failover ≠ broker failover
green SLO ≠ cap increase
successful pilot ≠ autonomy increase
BUILD 33 ≠ autonomous live trading
```
