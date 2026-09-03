# PLATFORM-PAPER-001 — Platformization foundations (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-21  
**Scope:** Platformization P0 — orthogonal operating modes, event-sourced paper ledger, read-only paper API, CI invariants  
**Prerequisites:** Phase 8 `PASS`, UI-002 `PASS`, Phase 0 no-live safety `PASS`

## 1. Purpose

Authorize the transition from replay-only research UI toward a provider-agnostic
market operating platform. PLATFORM-PAPER-001 establishes foundations only:
operating-mode semantics, canonical order/instrument contracts, append-only paper
execution events, read-only portfolio observability, and CI no-live invariants.

Interactive order submission through the deterministic bar simulator is authorized
under explicit feature gates (`IMP_PAPER_EXECUTION=1`, never in CI).

## 2. Platformization milestones (not Phases 0–16)

| Milestone | Goal |
|---|---|
| **P0** | PLATFORM-PAPER-001, mode model, CI, contracts, event ledger, read-only `/paper/*` |
| **P1** | Interactive internal simulation (preview + submit → simulator → ledger) |
| **P2** | Portfolio daily-use UX, Moomoo observational runtime pipeline |
| **P3** | Auth (Supabase Auth + Postgres) + user-scoped persistence |
| **P4** | External paper brokers, idempotency, reconciliation |
| **P5** | Hosted platform, security, PROVIDER-COMMERCIAL-001 licensing gates |
| **P6** | Shadow/forward validation before any live execution discussion |
| **LIVE-001** | Separate authorization for production broker execution |

## 3. Operating modes (orthogonal)

Do not use a single `REPLAY | SIMULATION | PAPER | LIVE` state machine.

| Dimension | Values |
|---|---|
| **data_mode** | `FIXTURE_REPLAY`, `HISTORICAL_CAPTURE`, `LIVE_OBSERVATIONAL`, `BROKER_DELAYED` |
| **execution_mode** | `NONE`, `INTERNAL_SIMULATION`, `BROKER_PAPER`, `LIVE` |
| **execution_authority** | `BLOCKED`, `AUTHORIZED` |
| **data_provider** | `INTERNAL`, `MOOMOO`, `TRADIER`, `IBKR`, … |
| **execution_provider** | `INTERNAL`, `TRADIER`, `MOOMOO`, `IBKR`, … |

Legacy `mode` field remains derived for UI-001 backward compatibility.

## 4. Data admission (two pipelines)

**Research pipeline:** capture → integrity → PIT validation → fixture admission → reproducible research.

**Runtime pipeline:** provider event → normalization → capability → freshness → quality → UI admission (no fixture required).

## 5. Event-sourced paper ledger

Immutable append-only events. Portfolio snapshots are derived projections.

Event types (P0 minimum):

- `PaperAccountCreated`
- `PaperSessionOpened`
- `PaperSessionClosed`
- `OrderIntentCreated`
- `RiskDecisionRecorded`
- `OrderSubmitted`
- `OrderStateChanged`
- `FillRecorded`
- `PositionChanged`

## 6. API (P0 + P1)

| Method | Path | P0 |
|---|---|---|
| GET | `/paper/account` | Yes |
| GET | `/paper/positions` | Yes |
| GET | `/paper/orders` | Yes |
| GET | `/paper/fills` | Yes |
| GET | `/paper/risk` | Yes |
| POST | `/paper/orders/preview` | P1 |
| POST | `/paper/orders` | P1 (gated) |
| POST | `/paper/sessions` | P1 |

## 7. Execution path (P1)

User order ticket → `OrderIntent` → `evaluate_risk` → `BarConservativeSimulator` → fill → ledger events → projections → UI.

No cursor-price shortcuts. Same machinery as automated strategy simulation.

## 8. Acceptance assertions

| ID | Predicate |
|---|---|
| `PLAT-CTX-001` | `/context` includes orthogonal `data_mode`, `execution_mode`, `execution_authority` |
| `PLAT-LED-001` | Paper ledger events are append-only with provenance fields |
| `PLAT-P0-001` | `/paper/account` returns initial cash when no orders submitted |
| `PLAT-SIM-001` | BIYA vertical slice: intent → risk → sim → fill → position (gated test) |
| `PLAT-SAFE-001` | No path to `execution_mode=LIVE` without `IMP_LIVE_EXECUTION=1` (never set in CI) |
| `PLAT-SAFE-002` | Broker paper adapter unreachable when `IMP_PAPER_EXECUTION` unset |

## 9. Out of scope (P0)

- Supabase Auth / multi-user persistence (P3)
- Tradier/Moomoo broker adapters (P4)
- Live execution (LIVE-001)
- Container deployment (P5)

## 10. Broker notes (for P4 planning)

- **Tradier:** first execution-contract adapter; sandbox delayed data; no sandbox Greeks or microstructure.
- **Moomoo:** strategic for L2/observational data; separate data vs execution adapters even when both use Moomoo.
- **IBKR:** target multi-asset adapter; $500 minimum equity for many market-data subscriptions (not a general account hold).
- **PROVIDER-COMMERCIAL-001:** required before public multi-user release (Tradier personal-use terms).
