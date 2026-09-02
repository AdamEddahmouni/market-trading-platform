# IMP authority model

| Field | Value |
|---|---|
| Document ID | `IMP-AUTHORITY-MODEL` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Information, permission, authorization, execution, and reconciliation relationships |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | No single current whole-program authority explanation |
| Superseded By | None |

This is an explanatory map, not a policy, gate, registry, or authorization
record. The executable sources in the
[Canonical Truth Map](CANONICAL_TRUTH_MAP.md) control their own scopes.

## Authority flow

```text
information / evidence / model output
                  |
                  v
         prediction and research
                  |
                  v
          opportunity candidate
                  |
                  v
        independent risk decision
                  |
                  v
       live-safety prerequisite gate
                  |
                  v
      human live-session authorization
                  |
                  v
       per-order human confirmation
                  |
                  v
         execution-state handling
                  |
                  v
     broker acceptance / rejection / fill
                  |
                  v
             reconciliation
                  |
                  v
            canonical state
```

Release governance is a separate branch that governs release eligibility. It
does not join the trading-authorization chain as a substitute for session
authorization or order confirmation.

## Distinct roles

| Role | What it may do | What it cannot do |
|---|---|---|
| Information | Describe observations, claims, context, or state | Grant permission |
| Quality | Assess fitness and defects within a data/domain contract | Predict, qualify, or authorize |
| Prediction | Freeze a decision-time estimate and its lineage | Settle itself or grant permission |
| Evidence | Support or contradict an assessment at a defined cutoff | Replace risk, release, session, or order authority |
| Risk | Permit or block within the applicable risk policy | Authorize a live session, confirm an order, or create a broker fill |
| Execution state | Manage intent, sizing, mode, lifecycle, and guarded submission behavior | Bypass safety, authorization, confirmation, persistence, or reconciliation |
| Human session authorization | Permit a bounded live session within policy | Confirm every order or guarantee broker acceptance |
| Per-order authorization | Confirm one reviewed candidate action | Authorize unrelated orders or guarantee a fill |
| Release governance | Determine release eligibility and approval under its policy | Authorize a live session or order |
| Broker external reality | Accept, reject, or fill a transmitted request | Rewrite canonical internal state directly |
| Reconciliation | Incorporate external reality and surface mismatch | Manufacture, hide, or infer a broker fill |

## Current executable anchors

- Risk decisions: [`risk/decision.py`](../../src/market_platform_foundation/risk/decision.py)
  and [`risk/policy.py`](../../src/market_platform_foundation/risk/policy.py).
- Execution state: [`intelligence/execution/`](../../src/market_platform_foundation/intelligence/execution)
  and guarded paper/mock paths.
- Live safety: [`live_execution_safety/gate.py`](../../src/market_platform_foundation/intelligence/live_execution_safety/gate.py).
- Human session authorization:
  [`live_canary/authorization.py`](../../src/market_platform_foundation/intelligence/live_canary/authorization.py).
- Per-order confirmation:
  [`live_canary/confirmation.py`](../../src/market_platform_foundation/intelligence/live_canary/confirmation.py).
- Broker boundary:
  [`live_canary/submission.py`](../../src/market_platform_foundation/intelligence/live_canary/submission.py);
  current runners instantiate `MockBrokerTransport`.
- Reconciliation:
  [`live_canary/reconciliation.py`](../../src/market_platform_foundation/intelligence/live_canary/reconciliation.py),
  [`portfolio/reconciliation.py`](../../src/market_platform_foundation/portfolio/reconciliation.py),
  and [`platform/reconciliation/engine.py`](../../src/market_platform_foundation/platform/reconciliation/engine.py).
- Release governance:
  [`live_canary/release_governance/`](../../src/market_platform_foundation/intelligence/live_canary/release_governance)
  and the historical [BUILD35 authority map](../../artifacts/full-system-acceptance/BUILD35_AUTHORITY_MAP.json).

## Forbidden shortcuts

None of the following directly grants broker authority:

- an LLM or agent;
- research, narrative, or a motive hypothesis;
- a signal, forecast, prediction, model output, or opportunity;
- evidence sufficiency or qualification;
- release approval;
- provider connectivity, reconnect, capability, or availability;
- a mode flag, UI state, or runbook step.

They may inform a governed decision or satisfy one prerequisite only. They
cannot collapse the independent risk, safety, authorization, confirmation,
transport, and reconciliation boundaries.

## Current safety state

- Autonomous live trading is disabled.
- Human live-session authorization is required.
- Per-order human confirmation is required.
- Automatic broker failover is disabled.
- Accepted production live broker transport is absent.
- Broker abstractions, sandbox/paper execution, mock transport, live-safety
  gates, authorization, confirmation, and reconciliation code exist; their
  existence does not establish production live transport.

## Live-readiness ladder

```text
REAL OBSERVATIONAL MARKET DATA
!=
LIVE PROVIDER CONNECTIVITY
!=
PRODUCTION LIVE EXECUTION TRANSPORT
!=
OPERATIONALLY ACCEPTED LIVE EXECUTION
!=
AUTHORIZED LIVE SESSION
!=
AUTHORIZED INDIVIDUAL ORDER
!=
BROKER ACCEPTANCE / FILL
```

```text
broker fill -> reconciliation -> canonical state
```

The word `LIVE` must always name its layer. Observation is not transport;
transport is not operational acceptance; operational acceptance is not session
authorization; session authorization is not an order; an order is not a fill.
