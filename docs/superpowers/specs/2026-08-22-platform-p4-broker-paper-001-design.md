# PLATFORM-P4-001 — External Broker Paper Adapters, Idempotency, and Reconciliation (design spec)

**Status:** Design — pending principal review
**Spec date:** 2026-08-22
**Scope:** Platformization **P4** — first external execution-contract adapter
(**Tradier sandbox**), broker-neutral paper execution behind the existing
`PaperExecutionProvider` contract, idempotent order submission, and
ledger↔broker reconciliation. **Paper only. No live order path.**
**Prerequisites:** Platformization P0–P3.3 landed (`main` at `59b3716`),
DECISION-RESEARCH-001 milestone A landed, Phase 0 no-live safety `PASS`,
Phase 1 ADR acceptance-index drift resolved (FULL green)

## 1. Purpose

The platform can already run internal paper execution (P0/P1) on live
observational marks (P2/P2.1) with durable local state (P3), unified operator
workstation (P3.2), and governed decision research (DECISION-RESEARCH-001
milestone A). Every one of those paths executes **inside** the IMP ledger with
the internal `BarConservativeSimulator`.

What the platform cannot yet do is prove its execution-contract semantics
against a **real broker's paper API**: real order lifecycle transitions, broker
order ids, partial fills, rejects, cancels, and the ambiguity of a network
failure after a broker accepted an order. P4 closes that gap with the **Tradier
sandbox first** — the cheapest, lowest-risk execution-contract test bed — under
the exact same fail-closed discipline as every prior milestone:

- every submission is **idempotent** (a retry can never create a second broker
  order);
- every broker event carries **provider, entitlement, event-time, receive-time,
  symbol mapping, latency/quality, and raw-source reference** (ADR-PROV-001);
- every broker record is **reconciled** against the event-sourced IMP ledger,
  and any unexplained mismatch is surfaced, never silently absorbed;
- there is **no live order method** callable without a separate explicit
  enablement, and `LIVE` execution remains unauthorized (`LIVE-001`).

This is Platformization **P4** per the [platformization roadmap](../research/PLATFORMIZATION_ROADMAP.md)
and is explicitly deferred out of DECISION-RESEARCH-001's completion definition
("no P4 implementation has begun"). It is split into two sub-milestones so the
first execution-contract adapter (4A) can land and gate before the second (4B).

## 2. Sub-milestones

| Milestone | Goal | Status |
|---|---|---|
| **P4-4A** | Tradier sandbox paper adapter: `PaperExecutionProvider` implementation, broker order lifecycle mapping, idempotent submission, sandbox-contract fixtures, `/paper/broker/*` observability | Not started |
| **P4-4B** | Reconciliation engine: broker order/position/activity snapshot reconciliation against the IMP ledger, mismatch ledger, replay-safe correction events | Not started |
| **P4-4C** | Moomoo execution adapter (separate from the observational data adapter) behind the same contract; IBKR deferred until funded | Not started |

4A is the hard dependency for 4B (reconciliation needs a real broker record).
4C is independent once the contract is frozen by 4A.

## 3. Authorization matrix (extends PLATFORM-DATA-001)

| data_mode | execution_mode | execution_provider | Status |
|---|---|---|---|
| `BROKER_DELAYED` | `BROKER_PAPER` | `TRADIER` | **AUTHORIZED (4A)** — sandbox-only endpoints, token gate, paper account |
| `FIXTURE_REPLAY` | `BROKER_PAPER` | `TRADIER` | **AUTHORIZED (4A)** — sandbox-contract fixture replay, no network |
| `LIVE_OBSERVATIONAL` | `BROKER_PAPER` | any external | **NOT AUTHORIZED** — live observational data never feeds broker orders (unchanged from PLATFORM-DATA-001) |
| any | `BROKER_PAPER` | `IBKR` / `ALPACA` | **NOT AUTHORIZED** until a P4 amendment lands each adapter |
| any | `LIVE` | any | **NOT AUTHORIZED** (`LIVE-001` separate authorization) |

The Tradier sandbox executes at **simulated prices on delayed market data** —
it is a contract and lifecycle test bed, not an L2/CVD source and not a
fill-quality source. Nothing in P4 asserts Tradier fills are economically
meaningful; fills remain the internal simulator's product. Broker paper is used
to validate **execution-contract semantics**, not to produce research signals.

## 4. Broker-neutral contract (frozen in 4A)

The existing `PaperExecutionProvider` protocol
(`src/market_platform_foundation/providers/contracts.py`, per ADR-PROV-001)
is the single execution contract. P4 adds the canonical broker-facing payloads
that every adapter maps onto and off of:

| Canonical model | Meaning | Key fields |
|---|---|---|
| `BrokerPaperOrderRequest` | Outbound submission | `intent_id`, `idempotency_key`, `client_order_id`, instrument (`SymbolMapping`), side, order_type, quantity, limit_price_minor, requested_time_ns |
| `BrokerOrderStatusEvent` | Broker lifecycle push/poll | `broker_order_id`, `status` (mapped to IMP `ORDER_LIFECYCLE_STATES`), filled_quantity, avg_fill_price_minor, event_time, receive_time, raw-source reference |
| `BrokerFillEvent` | Executions | `broker_fill_id`, quantity, price_minor, event_time, receive_time, raw-source reference |
| `BrokerPositionSnapshot` | Reconciliation input | broker_position_id, quantity, avg_price_minor, as-of time |
| `BrokerAccountSnapshot` | Cash/buying-power reconciliation | cash_minor, as-of time |

Every broker event envelope carries the ADR-PROV-001 provenance fields —
`provider`, `entitlement`, `event_time`, `receive_time`, `symbol_mapping`,
`latency_ms`, `quality_flags`, `raw_source_ref` — and is serialized as a
canonical IMP event before any downstream consumer touches it. Provider-native
fields live only in envelope provenance (same rule as PLATFORM-DATA-001).

State mapping is explicit and fail-closed: a broker status with no IMP mapping
maps to a broker-side state recorded verbatim in the envelope **and** the IMP
order state transitions only on a known mapping. Unknown broker statuses never
advance the IMP lifecycle.

## 5. Tradier sandbox adapter (4A)

### 5.1 What 4A delivers

- `TradierPaperExecutionProvider` implementing `PaperExecutionProvider`
  (`place_order(intent)`) plus `cancel_order`, `fetch_order`,
  `fetch_account`, `fetch_positions` as adapter-local methods — **none of them
  callable** unless the P4 gates are set.
- Symbol mapping: Tradier symbol ↔ canonical `instrument_id` via
  `providers.SymbolMapping`; unmapped symbols fail closed at intent build.
- Broker order lifecycle mapped onto the existing IMP
  `ORDER_LIFECYCLE_STATES` and validated by `validate_order_transition`
  (`paper/contracts.py`). `WORKING` becomes reachable via broker LIMIT orders.
- Sandbox-contract fixtures: recorded Tradier JSON responses replayed without
  network so CI exercises the adapter deterministically (mirrors
  `IMP_LIVE_FIXTURE_FEED` philosophy from PLATFORM-DATA-001).
- `GET /paper/broker/orders`, `GET /paper/broker/account`,
  `GET /paper/broker/positions` — read-only observability of the broker-side
  view alongside the IMP ledger view (the two must never be conflated in the UI).

### 5.2 Sandbox semantics (verified limits — do not over-claim)

Per the [broker priority notes](../research/PLATFORMIZATION_ROADMAP.md) and the
professor-supplied brief:

- Free account yields an API token and **paper sandbox**; sandbox market data
  is **15-minute delayed**, has no delayed streaming, and Tradier documents
  **Level 1 only**. The sandbox is not a CVD/Level-2 source and not a
  fill-quality source.
- The sandbox supports US equities/options **orders, chains, and delayed quote
  testing** — the order lifecycle is the P4 subject, not Greeks or
  microstructure.
- Real-time data requires a brokerage account and is out of scope.
- Endpoint-level details (paths, payload shapes) are established empirically in
  4A against the sandbox and recorded in `docs/providers/TRADIER_PAPER.md`;
  this spec authorizes the adapter, not a fixed wire contract.

### 5.3 Fail-closed configuration

| Variable | Default | Effect |
|---|---|---|
| `IMP_TRADIER_PAPER=1` | unset | Tradier paper adapter disabled |
| `IMP_BROKER_PAPER_EXECUTION=1` | unset | `BROKER_PAPER` execution authority (separate from `IMP_PAPER_EXECUTION`; `resolve_execution_authority` must reject `BROKER_PAPER` without it) |
| `IMP_TRADIER_TOKEN` | unset | sandbox bearer token; read from env or `.private/providers.env` (never committed) |
| `IMP_TRADIER_ENDPOINT` | sandbox URL | fails closed if set to a production endpoint |
| `IMP_TRADIER_ACCOUNT_ID` | unset | sandbox account to address |

None of these are set in CI. The adapter must verify **all** of
(`IMP_TRADIER_PAPER`, `IMP_BROKER_PAPER_EXECUTION`, `IMP_TRADIER_TOKEN`,
sandbox endpoint) before any request is possible; a missing gate is
`PROVIDER_NOT_CONFIGURED` / `EXECUTION_NOT_ENABLED`, matching the existing
`providers/contracts.py` sentinels.

## 6. Idempotency (4A)

`build_user_order_intent` already requires `idempotency_key` and
`client_order_id` (DECISION-RESEARCH-001 §9 wired `research_candidate_id`
through the same intent). P4 makes those fields load-bearing at the broker
boundary:

- **Submission record first:** an `OrderSubmitted`-class broker submission
  event (with `idempotency_key`, `client_order_id`, intent hash) is appended to
  the IMP ledger **before** any broker network call. A retry after a timeout or
  crash replays the submission record and **never re-submits** when the broker
  interaction is unresolved.
- **Ambiguity handling:** a network failure after the broker may have accepted
  the order is recorded as an **ambiguous** broker state; resolution comes from
  the broker order fetch (`fetch_order`) or reconciliation (4B), never from a
  blind retry.
- **Duplicate submission under retries = 0** (roadmap correctness metric).
  Adversarial tests must prove that N retries of the same `idempotency_key`
  produce exactly one broker submission record and at most one broker order id.
- Provider-native `client_order_id` round-trip is preserved; Tradier's response
  `id` is captured as `broker_order_id` and bound to the IMP order.

## 7. Reconciliation (4B)

- **Sources:** broker order/position/account snapshots (poll) + broker-side
  activity against the IMP ledger projection. Reconcile at order level
  (quantity, state, fill count) and account level (cash, positions).
- **Output:** a per-order and per-account `ReconciliationReport` with
  `MATCHED` / `MISMATCH` / `UNAVAILABLE` per field; **mismatches are written as
  immutable ledger events**, never patched in place.
- **Correction path:** a mismatch is resolved only by an operator-initiated
  correction event carrying both observed broker values and the raw-source
  reference — the same event-sourced, append-only discipline as the P0 ledger.
- **Unexplained ledger/broker mismatches = 0** at completion (roadmap metric):
  every mismatch either has a root-cause event or is explicitly held open in a
  `RECONCILIATION_HOLD` state with the operator informed. Silent absorption of a
  difference is a P4 safety violation.
- Reconciliation must be **replay-safe**: the same snapshots + ledger replay
  produce the same report deterministically.

## 8. Architecture

```text
operator OrderTicket (existing P1 path)
      ↓
build_user_order_intent (idempotency_key, client_order_id, research_candidate_id)
      ↓
evaluate_risk → internal simulator (unchanged; fills remain internal product)
      ↓
BROKER_PAPER execution_mode, TRADIER provider (gated)
      ↓
TradierPaperExecutionProvider (PaperExecutionProvider contract)
      ↓   [submission record appended BEFORE any network call]
broker HTTP (sandbox endpoint only)
      ↓
broker status/fill events → normalization → canonical IMP events → ledger
      ↓
reconciliation engine (4B): broker snapshots vs ledger projection → report + correction events
      ↓
/paper/broker/* observability (broker view distinct from IMP view)
```

## 9. Assertions

| ID | Predicate |
|---|---|
| `P4-PROV-001` | Every broker event carries provider, entitlement, event_time, receive_time, symbol mapping, latency/quality, raw-source reference |
| `P4-IDEM-001` | N retries of one `idempotency_key` produce exactly one broker submission record and ≤ 1 broker order id |
| `P4-AMB-001` | A timeout/unknown-outcome broker response is recorded ambiguous and resolved only via fetch/reconciliation, never blind retry |
| `P4-MAP-001` | Unknown broker statuses never advance the IMP lifecycle; unmapped symbols fail closed at intent build |
| `P4-REC-001` | Reconciliation reports are deterministic under identical snapshots; mismatches are append-only events, never patched |
| `P4-REC-002` | No unexplained ledger/broker mismatch is silently absorbed; unresolved differences hold in `RECONCILIATION_HOLD` |
| `P4-SAFE-001` | No broker request possible without all of (`IMP_TRADIER_PAPER`, `IMP_BROKER_PAPER_EXECUTION`, token, sandbox endpoint) |
| `P4-SAFE-002` | `LIVE` execution remains unreachable (`IMP_LIVE_EXECUTION` never set in CI); live observational data never feeds broker orders |
| `P4-AUDIT-001` | 100% of broker orders carry audit/provenance ids (intent hash + client order id) |

## 10. Fixtures and adversarial cases

- `tests/fixtures/providers/tradier_sandbox_*.json` — recorded sandbox responses
  (order accept, partial fill, full fill, reject, cancel) as **fixture-first**
  contract tests; no network, deterministic, CI-safe.
- Adversarial fixtures: duplicate `idempotency_key` retry storm, broker accept +
  network drop (ambiguous), unknown broker status, unmapped symbol, partial-fill
  sequence out of order, reconciliation mismatch (quantity drift), stale
  position snapshot, production-endpoint guard attempt, gate-missing call
  attempt.
- `tests/platform/test_broker_paper_p4.py` — assertion + adversarial suite
  (4A/4B), plus `tests/platform/test_reconciliation_p4.py` (4B).

## 11. Tooling and gate

- `tools/platform/run_broker_paper_gate_validation.py` — runs the fixture
  adapter path, asserts `P4-*`, writes
  `evidence/platform/broker-paper-gate-report.json`.
- `tools/platform/run_reconciliation_gate_validation.py` — 4B counterpart.
- Validation cadence: `python tools/validate.py changed` after edits; gate tools
  at each sub-milestone; `python tools/validate.py full` at the final
  checkpoint. New modules live under
  `src/market_platform_foundation/platform/broker/**` (4A) and
  `src/market_platform_foundation/platform/reconciliation/**` (4B); the
  manifest suites own them via test globs (a manifest edit, if needed, is a
  governed change requiring principal approval).
- Deliverable docs: `docs/providers/TRADIER_PAPER.md` (verified wire contract
  and limits), platformization roadmap and README capability boundary updated
  to mark P4 status on landing.

## 12. Out of scope (P4)

- Live execution, any real-money order, or production endpoints (`LIVE-001`).
- IBKR adapter (requires funded account/data entitlements; separate P4
  amendment), Alpaca adapter (secondary reference only), Moomoo execution
  adapter (4C) and Moomoo paper trading product behavior.
- Hosted platform, security review, PROVIDER-COMMERCIAL-001 licensing
  (P5), shadow/forward validation (P6).
- Using broker fills as research data: fills validate execution-contract
  semantics only; research signals continue to use the internal simulator and
  admitted fixtures.
- Retroactive reconstruction of broker history as research fixtures.

## 13. Completion definition

P4 is complete when:

- `TradierPaperExecutionProvider` implements `PaperExecutionProvider` with the
  frozen broker-neutral contract, all provenance fields per `P4-PROV-001`, and
  sandbox-only fail-closed configuration;
- the idempotent submission path is proven by adversarial fixtures
  (`P4-IDEM-001`, `P4-AMB-001`, `P4-AUDIT-001`);
- the reconciliation engine produces deterministic reports and append-only
  correction events with zero silent mismatches (`P4-REC-001`, `P4-REC-002`);
- assertions `P4-*` and all adversarial fixtures pass; both gate tools report
  aggregate PASS;
- the platformization roadmap and README capability boundary mark P4 complete
  (`COMPLETE_WITH_LIMITATIONS` if 4C/IBKR remain), `docs/providers/TRADIER_PAPER.md`
  records the verified wire contract, and `LIVE-001` remains blocked and
  unauthorized.
