# Platformization roadmap (P0–P6)

**Status:** Active — supersedes informal "Phase 1–5" platform sequencing  
**Authority:** [PLATFORM-PAPER-001](../superpowers/specs/2026-08-21-platform-paper-001-design.md), [PLATFORM-STATE-001](../superpowers/specs/2026-08-21-platform-state-001-design.md)  
**Date:** 2026-08-21

This document tracks the transition from replay-only research UI to a provider-agnostic
market operating platform. It uses **Platformization P0–P6** naming to avoid collision
with governed Phases 0–16.

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| **P0** | Orthogonal modes, event ledger, `/paper/*` API, portfolio observability, CI | **COMPLETE** |
| **P1** | Interactive internal simulation (preview + submit → BarConservativeSimulator) | **COMPLETE_WITH_LIMITATIONS** |
| **P2** | Live observational market data (Moomoo), runtime admission, capability-aware Explore | **COMPLETE_WITH_LIMITATIONS** |
| **P2.1** | Live L1/trades/L2 admission, CVD, internal paper on live marks | **COMPLETE_WITH_LIMITATIONS** |
| **P3** | Durable local SQLite state, operator workflow, restart recovery | **COMPLETE_WITH_LIMITATIONS** |
| **P3.1** | Live internal paper on admitted L1, operator instrument, restart marks | **COMPLETE_WITH_LIMITATIONS** — [P3.1 closure](../superpowers/specs/2026-08-21-platform-p31-live-execution-closure.md) |
| **P3.2** | Unified live decision workstation (`/workspace/{symbol}/evidence`, What Matters Now, evidence drawer) | **COMPLETE** — [P3.2](../superpowers/specs/2026-08-21-platform-p32-unified-live-workstation.md) |
| **P3.3** | Finviz Elite discovery, prospective PIT capture, decision-research foundation | **COMPLETE** — [P3.3](../superpowers/specs/2026-08-21-platform-p33-finviz-discovery-research.md) · [DECISION-RESEARCH-001 milestone A](../superpowers/specs/2026-08-22-decision-research-001-design.md) (OOS gate PASS) |
| **P4** | Tradier/Moomoo paper adapters, idempotency, reconciliation | **4A + 4B COMPLETE_WITH_LIMITATIONS** — Tradier sandbox adapter + idempotent submission and the reconciliation engine landed, both gates PASS ([PLATFORM-P4-001](../superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md)); **4C COMPLETE_WITH_LIMITATIONS** — Moomoo paper adapter landed fixture-first (`src/market_platform_foundation/providers/adapters/moomoo_paper.py`), real-wire unconfirmed (OpenD gateway TCP-only); `/paper/broker/*` observability implemented (fixture-level) |
| **P5** | Hosted platform, security, PROVIDER-COMMERCIAL-001 | **Local auth enforcement complete** (TD-005 closed): LOOPBACK_TRUST/ENFORCED modes, principals registry, session API, route capability + account ACL (ADR-0008); security foundations offline-proven (`platform/security/**`); **hosted deployment and OIDC/SSO not started** |
| **P6** | Shadow/forward validation | **IN PROGRESS — EVIDENCE COLLECTION**: infrastructure + Shadow Run 1 machinery offline-proven (`shadow/**`, `run_shadow_run.py`); protocol preregistered 2026-09-01 ([P6_SHADOW_RUN_1_PROTOCOL.md](../engineering/P6_SHADOW_RUN_1_PROTOCOL.md), [SOP](../engineering/sops/FORWARD_SHADOW_VALIDATION.md)); **no ACTUAL_FORWARD observations yet** — Moomoo observational path blocked in current environment |
| **LIVE-001** | Production execution (separate authorization) | Blocked |

### P4 status (2026-08-22)

[PLATFORM-P4-001](../superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md)
defines the broker-neutral paper execution contract, the Tradier sandbox
adapter, idempotent submission, and the reconciliation engine. The code-grounded
audit (`.planning/2026-08-22-platform-p4-broker-paper-code-audit.md`) verified
12/12 code-facing claims; findings F1–F8 are applied to the spec (F9 deferred).

**Sub-milestone 4A landed (offline, fixture-first):**

- `TradierPaperExecutionProvider` at
  `src/market_platform_foundation/providers/adapters/tradier_paper.py` with
  dedicated `submit_broker_paper_order` / `cancel_broker_paper_order` entry
  points (`paper/broker_paper.py`); the `INTERNAL_SIMULATION` guard in
  `paper/execution.py` is unchanged (`P4-SAFE-003`).
- Idempotent submission (submission record appended **before** any broker call),
  ambiguous-outcome handling with no blind retry (`P4-IDEM-001`, `P4-AMB-001`),
  broker lifecycle mapping onto `ORDER_LIFECYCLE_STATES` (`P4-MAP-001`), and
  per-mode fill authority (`P4-FILL-001`).
- Composition wiring (`with_broker_paper_execution` into
  `ProviderComposition.paper_execution`), `BROKER_PAPER → PAPER_ONLY` under
  `IMP_BROKER_PAPER_EXECUTION` (`operating_modes.resolve_execution_authority`),
  populated execution-trace broker fields (`P4-TRACE-001`), sandbox-contract
  fixtures, and updated `.env.example` gates.
- Gate: `tools/platform/run_broker_paper_gate_validation.py` → **aggregate
  PASS** (P4-AMB/P4-AUDIT/P4-FILL/P4-IDEM/P4-PROV/P4-SAFE-001, 0 failures;
  `evidence/platform/broker-paper-gate-report.json`); the P4 test suite
  `tests/platform/test_broker_paper_p4.py` is green. `LIVE` execution remains
  unreachable (`IMP_LIVE_EXECUTION` is never set in CI).

**Sub-milestone 4B landed (offline, deterministic):**

- Reconciliation engine at
  `src/market_platform_foundation/platform/reconciliation/**`: pure,
  replay-safe `build_reconciliation_report` (content-derived report id, no
  wall clock), order/position/account comparisons against the ledger
  projection, and broker-side order absence detection.
- `ReconciliationRecorded` / `ReconciliationCorrectionRecorded` ledger event
  types (append-only; a mismatch is never patched) and the
  `project_risk.reconciliation_status` extension (`BROKER_RECONCILED` /
  `MISMATCH` / `RECONCILIATION_HOLD`, `RECONCILIATION_PENDING` before the
  first report; `INTERNAL_AUTHORITATIVE` unchanged outside `BROKER_PAPER`).
- Operator correction path: per-field RESOLVED events carrying the observed
  broker value + raw-source reference, or report-level HELD events;
  `assert_no_unexplained_mismatch` fails closed on silent absorption
  (`P4-REC-002`).
- Gate: `tools/platform/run_reconciliation_gate_validation.py` → **aggregate
  PASS** (`evidence/platform/reconciliation-gate-report.json`);
  `tests/platform/test_reconciliation_p4.py` is green (18 tests).

**Sub-milestone 4C landed (offline, fixture-first):**

- `MoomooPaperExecutionProvider` at
  `src/market_platform_foundation/providers/adapters/moomoo_paper.py`
  (18-test module `tests/platform/test_moomoo_paper_p4c.py`), with a
  composition mutual-exclusion guard against the Tradier broker-paper
  adapter, a six-gate fail-closed enable matrix, and SIMULATE
  trade-environment-only operation.
- Transport is an injectable interface exercised by recorded-replay fixtures.
  Limitation: the Moomoo OpenAPI is reachable only through the proprietary
  OpenD gateway (TCP-only), so a stdlib transport is infeasible in this
  repository; real-wire confirmation requires the proprietary SDK outside the
  repository. Status: **COMPLETE_WITH_LIMITATIONS** — fixture-proven,
  real-wire unconfirmed. Fixture tests here are not forward validation.

**Broker observability endpoints landed (fixture-level):**

- Read-only `/paper/broker/*` routes — orders / account / positions /
  reconciliation / health — implemented in `ui_api/server.py` +
  `ui_api/broker_projections.py` (18-test module
  `tests/platform/test_broker_observability_p44.py`), smoke-tested over live
  HTTP against the disabled stub. Still fixture-level until a Tradier sandbox
  wire exercise; this is not yet observational-live or execution authority.

**Limitations / remaining P4 scope:** wire specifics for 4A/4B depend on
exercising the real Tradier sandbox and are tracked in
`docs/providers/TRADIER_PAPER.md`; 4C real-wire behavior remains unconfirmed
(OpenD gateway limitation above).

## Architecture decisions (locked)

1. **Two-dimensional modes:** `data_mode` × `execution_mode` × `execution_authority` (see `operating_modes.py`).
2. **Event-sourced paper ledger:** append-only events; portfolio is projected (`paper/ledger.py`).
3. **Single execution truth:** user orders use `BarConservativeSimulator`, not cursor-price shortcuts.
4. **Execution bar window:** `bars_for_execution()` from replay cursor forward (no chart look-ahead, valid fill path).
5. **Dual data admission:** research fixture pipeline vs runtime quality pipeline (documented in PLATFORM-PAPER-001).
6. **Local durable state (P3):** SQLite event-sourced paper ledger + operator state. No custom JWT, no hosted auth.
7. **CI in P0:** `.github/workflows/imp-validate.yml` (FAST + CHANGED offline on push/PR; landed 2026-08-22).

## Broker priority (P4)

| Provider | Role |
|---|---|
| **Tradier sandbox** | First execution-contract adapter (order lifecycle; no sandbox Greeks/L2) |
| **Moomoo** | Strategic L2/observational data; separate execution adapter even if same vendor |
| **IBKR** | Multi-asset target when funded ($500 min for many data subscriptions) |
| **Alpaca** | Secondary reference only |

## Correctness metrics

| Metric | Target |
|---|---:|
| Orders with audit/provenance IDs | 100% |
| Duplicate submission under retries | 0 |
| LIVE execution without `IMP_LIVE_EXECUTION=1` | 0 paths |
| Unexplained ledger/broker mismatches (P4+) | 0 |

Enforcement (F9, landed): `tools/validate.py` strips `IMP_LIVE_EXECUTION` —
its `LIVE_GATES["execution"]` entry — from every offline run, so a leaked
environment value can never arm real execution; `IMP_LIVE_OBSERVATIONAL`
is stripped the same way offline. Both gates are settable only inside an
explicit LIVE_EXCLUSIVE child run.
