# IMP authority model

| Field | Value |
|---|---|
| Document ID | `IMP-AUTHORITY-MODEL` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Program authority layers and safety flow |
| Owner Role | IMP safety and program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | No prior current whole-program authority explanation |
| Superseded By | None |

Authority is narrow, explicit, and auditable. Information may be broadly
readable, but it cannot acquire authority merely by moving between components.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Authority layers

| Layer | May decide | Does not decide |
|---|---|---|
| Information authority | What a source, normalized record, research result, or model output says and how it is attributed | Data quality, causal truth, risk, or execution |
| Data quality authority | Whether data meets scoped quality, temporal, provenance, and selection rules | Prediction correctness or trading permission |
| Prediction | A frozen forecast at a declared cutoff with model/source lineage | Its later outcome, qualification, risk, or order submission |
| Evidence | What observations and artifacts belong to a governed campaign | Sufficiency except through the campaign's policy; never order authority |
| Settlement | When and how a prediction receives a separate outcome record | Retrospective rewriting of the prediction or policy |
| Qualification | Whether evidence satisfies an explicitly scoped frozen policy | Live-session authorization, order confirmation, or broker submission |
| Risk authority | Whether a proposal is acceptable and how it is constrained/sized | Human intent or transport submission |
| Execution state | Whether a governed order intent may advance through executable gates | Independent creation of human authorization |
| Human live-session authority | Whether a bounded live session may operate | Confirmation of an individual order |
| Per-order human authority | Whether one exact order intent is confirmed | Broker acceptance or fill |
| Release governance | Whether a software candidate is eligible under release policy | Trading authorization |
| Broker reality | What the external broker accepted, rejected, acknowledged, or filled | Canonical internal state until reconciled |
| Reconciliation | How broker facts and internal ledgers are compared and discrepancies preserved/resolved | Silent mutation or invention of broker facts |

## Required flow

```text
source information
  -> temporal/provenance/quality gates
  -> intelligence and prediction
  -> evidence and settlement
  -> scoped qualification
  -> opportunity and risk authority
  -> live-safety gate
  -> human live-session authorization
  -> exact per-order human confirmation
  -> execution state and broker transport
  -> broker response/fill
  -> reconciliation into canonical state

software release evidence
  -> release approval
  -> candidate eligibility only
```

The live-readiness ladder is therefore:

```text
REAL MARKET OBSERVATION
  != LIVE EXECUTION TRANSPORT
  != OPERATIONALLY ACCEPTED LIVE EXECUTION
  != AUTHORIZED LIVE SESSION
  != AUTHORIZED ORDER
  != BROKER FILL
  -> RECONCILED CANONICAL STATE
```

## Forbidden shortcuts

The program forbids these authority edges:

```text
LLM -> broker
Agent -> broker
Research -> broker
Prediction -> broker
Qualification -> broker
Release approval -> broker
Provider reconnect -> automatic broker failover
```

The same prohibition applies through indirection: no UI action, environment
flag, model confidence, narrative, motive hypothesis, provider capability,
release status, or generated document may synthesize missing authority.

## Current execution invariants

- Autonomous live trading is disabled.
- Human live-session authorization is required.
- Per-order human confirmation is required.
- Automatic broker failover is disabled.
- Production live broker transport is not implemented or operationally
  accepted.
- Broker fills, if produced by an authorized future transport, must reconcile
  into canonical state.

Representative executable and frozen authorities are
[`live_execution_safety/`](../../src/market_platform_foundation/intelligence/live_execution_safety/),
[`live_canary/authorization.py`](../../src/market_platform_foundation/intelligence/live_canary/authorization.py),
[`live_canary/confirmation.py`](../../src/market_platform_foundation/intelligence/live_canary/confirmation.py),
[`platform/reconciliation/engine.py`](../../src/market_platform_foundation/platform/reconciliation/engine.py),
and the historical [BUILD35 authority map](../../artifacts/full-system-acceptance/BUILD35_AUTHORITY_MAP.json)
for its accepted cutoff. These sources, not this summary, control their defined
executable or frozen scopes.
