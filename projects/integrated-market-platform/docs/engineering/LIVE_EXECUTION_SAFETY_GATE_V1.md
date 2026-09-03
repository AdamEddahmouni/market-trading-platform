# Live Execution Safety Gate V1 (BUILD 28)

> **BUILD 28 certifies the safety boundary in front of real broker execution but does not authorize or submit real orders.**

## Core Principle

Passing BUILD 28 means the platform has a rigorously tested **pre-live execution safety boundary**. It does **not** grant permission to place live orders.

```text
PRELIVE_SAFETY_GATE_COMPLETE ≠ LIVE EXECUTION AUTHORIZED
```

## Authorization Semantics

```text
connection ≠ capability ≠ certification ≠ authorization ≠ submission
```

- A connected broker is not an authorized broker.
- An authorized broker is not an authorized account.
- An authorized account is not an authorized order.
- An authorized order is not submit-enabled unless every independent gate agrees.

## Multi-Gate Live Submission Model

Future live submission requires **all** of:

1. Runtime activation allows live-capable mode
2. `LiveExecutionAuthorizationV1` exists and is `ENABLED`
3. Broker/account capability certification passes (`BrokerCapabilityCertificationV1`)
4. `OpportunityV1` valid and unexpired
5. `TradeProposalV1` valid and unexpired
6. `RiskDecisionV1` `APPROVE` or authorized reduced size
7. Order intent unexpired (`BrokerOrderIntentV1`)
8. Broker execution health healthy
9. Reconciliation healthy
10. Kill switch `INACTIVE`
11. Idempotency key unused

Missing **any** gate blocks submission. BUILD 28 proves this with adversarial scenarios; production configuration never enables the full conjunction.

## BUILD 28 Production Configuration

| Control | State |
| --- | --- |
| Live authorization | `NOT_AUTHORIZED` / `DISABLED` |
| Kill switch | `ACTIVE_BLOCK` |
| Live submit | `FORBIDDEN` (`BUILD28_LIVE_SUBMIT_FORBIDDEN`) |
| Real order submissions | `0` |

## Contracts

| Contract | Purpose |
| --- | --- |
| `LiveExecutionAuthorizationV1` | Future explicit live authority (design-only in BUILD 28) |
| `BrokerCapabilityCertificationV1` | Zero-submit broker capability inventory |
| `BrokerOrderIntentV1` | Broker-neutral order intent with risk-approved quantity |
| `LiveExecutionGateDecisionV1` | Deterministic gate outcome |
| `LiveExecutionKillSwitchV1` | Fail-safe override |
| `BrokerReconciliationSnapshotV1` | Local/broker mismatch detection |
| `DryRunTransportResultV1` | Payload hash evidence without network submit |
| `LiveExecutionSafetyReportV1` | Aggregate certification disposition |

## Kill Switch

Default production state: **`ACTIVE_BLOCK`**.

Kill switch precedence overrides authorization, risk approval, and broker health. Models and LLMs cannot clear it in BUILD 28.

## Idempotency

Same approved intent (`TradeProposal` + `RiskDecision` + broker + account environment) produces the same deterministic `client_order_id`.

After ambiguous transport outcome (`SUBMISSION_STATUS_UNKNOWN`):

```text
NO BLIND RESUBMIT → RECONCILE FIRST
```

## Reconciliation

Local submission intent is not broker truth. Critical events:

- **Broker-only order**: broker has order unknown locally → block new submits until resolved
- **Local-only order**: local believes submitted, broker has no evidence → block retry until reconciled

## Account / Environment Isolation

Explicit environments: `SIMULATED`, `PAPER`, `SANDBOX`, `LIVE`, `UNKNOWN`.

`UNKNOWN` fails closed. Paper and live accounts must never be ambiguous.

## Asset-Class Certification

BUILD 28 certifies **US cash equities only** (`MARKET`, `LIMIT`). Options, futures, crypto: `NOT_CERTIFIED`.

## Broker-Specific Limitations

| Broker | Status |
| --- | --- |
| Tradier paper | `LIVE_CERTIFIABLE_DRY_RUN` — sandbox fixture only |
| Moomoo paper | `LIVE_CERTIFIABLE_DRY_RUN` — simulated env only |
| IBKR | `MARKET_DATA_ONLY` — no execution adapter |
| Moomoo observational | `MARKET_DATA_ONLY` |
| tastytrade | `UNSUPPORTED` |
| Internal simulator | `PAPER_ONLY` |

Replace/order-modification: **not certified**.

Broker preview/what-if: **not safely callable** — local dry-run only.

## Zero-Submit Transport

`DryRunExecutionAdapter` validates payloads, records canonical hash, and **never transmits**.

`ZeroSubmitGuard` raises `LiveSubmitForbiddenError` on any real `place_order` / `cancel_order` / `replace_order` call.

## BUILD 29 Boundary

A future BUILD 29 may design a **Limited Live Execution Authorization Program** only if explicitly requested and supported by BUILD 26–28 evidence. BUILD 28 grants no such authority.

## Package Location

```text
src/market_platform_foundation/intelligence/live_execution_safety/
tests/intelligence/test_live_execution_safety.py
artifacts/live-execution-safety/
tools/live_execution_safety/generate_build28_manifests.py
```

## Validation

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.intelligence.test_live_execution_safety -v
.venv\Scripts\python.exe tools/live_execution_safety/generate_build28_manifests.py
.venv\Scripts\python.exe tools/validate.py changed
```
