# 14b — G5 Current-State Matrix (Canonical Incremental L2 Order Book Engine)

**Status:** G5 checkpoint A evidence (2026-09-08). Companion to 14a (G4 matrix).
Baseline: G4 closed (BL-0211), FULL 3929/48/0 · FAST 21/0 · CHANGED 3347/48/0.

| Concern | Current behavior | Correct? | G5 target |
|---|---|---:|---|
| Full snapshot ingestion | `ObservationalStateStore.books` replaced wholesale per DEPTH event; `update_semantics: "SNAPSHOT"` hardcoded; providers/whale ledger store snapshot rows | No (ARCH-003) | `replace_from_snapshot` = explicit ingestion compatibility mode; incremental ops authoritative |
| Bid/ask side model | Raw dict rows `{price, size, order_count, order_details}` sorted ad hoc by consumers (`_sorted_bids`/`_sorted_asks` in `order_flow/ofi.py`) | Partial | Canonical per-side ordered levels keyed by exact price |
| Incremental insert | none | No | INSERT |
| Incremental update | none (whole-book replacement only) | No | UPDATE |
| Incremental delete | none | No | DELETE |
| Position/rank semantics | Implicit by consumer re-sort; no slot identity | No | Explicit position + deterministic gap-closing on delete |
| Sequence continuity | Optional `book_sequence` pair check in snapshot OFI only (`snapshot_pair_sequence_valid`); live store ignores | Partial | Engine sequence state machine; status truthfully exposed |
| Duplicate handling | No book-level dedupe | No | Duplicate → no-op `DUPLICATE` result |
| Out-of-order events | Not modeled for book | No | Regression/out-of-order → fail closed |
| Reset/clear | none at book level (admission resets sequences on reconnect only) | No | RESET op semantics |
| Subscription restart | reconnect resets admission seq; no book rebuild protocol | No | Generation identity; late old-generation events rejected |
| Stale detection | Freshness only for L1 quote (`freshness_ms` on quotes); book excluded | No | Pure `evaluate_book_freshness(book, as_of, policy)` |
| Book validity | `book_state_valid: True` hardcoded in `ui_api/live_projections.py:265`; structure-only checks in `order_flow/ofi.py` | No (ARCH-009) | Derived truth from engine state + explicit status/freshness fields |
| Snapshot projection | Raw dicts consumed directly by order-flow | Yes | Canonical incremental state → deterministic projection to legacy snapshot shape |
| CVD interoperability | CVD consumes trades only; book consumed by OFI/liquidity/impact/forecast | Yes | Engine projections feed existing order-flow without touching CVD session authority |
| Replay determinism | none for books | No | `replay(events)` → identical state + hash; no wall clock |
| OFI rank-shift | `compute_multilevel_ofi` pairs rank N→N across snapshots (ARCH-006) | No | Price-level / event-derived OFI path (new versioned method); legacy v1 kept for snapshot compat |
| Numeric policy | book prices/sizes binary float end-to-end | No | Decimal-exact inside engine; float normalized at adapter/projection boundary |
| Empty book | consumers treat empty as invalid | Partial | Explicit UNAVAILABLE vs INVALID semantics |
| One-sided book | treated invalid by snapshot validity fns | Partial | Structurally valid; two-sided metrics unavailable (never fabricate) |
| Crossed book | `assess_book` flags only in market_data quality; order-flow computes on crossed silently | Partial | Explicit crossed representation; no silent spread from corrupt state |
| instrument scoping | by provider symbol string | Partial | scoped by canonical instrument identity string (engine owner) |

Defect evidence (from 06-architecture-correctness.md §18 / WS05):
- ARCH-003: snapshot-replacement only; `update_semantics="SNAPSHOT"`; no insert/update/delete/reset/TTL.
- ARCH-006: multi-level OFI rank-based pairing approximation; level insert/delete mis-pairs.
- ARCH-009: live book no staleness control; payload hardcodes `book_state_valid: True`.

Target (11-target-architecture.md OrderBook row): "New incremental depth engine:
INSERT/UPDATE/DELETE/CLEAR per side+price, per-level sequence, full snapshot on
subscribe/reconnect, TTL + stale eviction, `book_sequence` mandatory on live streams."

G5 implements the canonical provider-neutral incremental book engine behind that target.
IBKR `reqMktDepth` mapping is documented for G6 only — no runtime IBKR work here.

## IBKR → canonical DepthUpdate mapping (G6 plan only, NOT implemented)

G6 will adapt the IBKR TWS `marketDepth` callback
(`reqId, position, operation, side, price, size, marketMaker`)
to the canonical contract at the adapter boundary. No provider field
leaks past the adapter except as explicit `provenance` metadata.

| IBKR `marketDepth` field | Canonical `DepthUpdate` field | Notes |
|---|---|---|
| `operation` (0=INSERT, 1=UPDATE, 2=DELETE) | `operation` → `DepthOperation.INSERT/UPDATE/DELETE` | Canonical RESET has no direct IBKR event — G6 maps subscribe/reconnect to a canonical `RESET` (or `replace_from_snapshot` after a full-depth snapshot on subscribe) |
| `side` (0=ASK, 1=BID) | `side` → `DepthSide.ASK/BID` | BID/ASK reversed at the boundary |
| `position` (0 = inside best) | `position` (advisory rank metadata) | Canonical engine cross-checks price-order rank; disagreement is rejected STRUCTURALLY_CORRUPT, never silently re-ranked |
| `price` | `price` (Decimal via `Decimal(str(v))`) | binary float normalized deliberately at the boundary |
| `size` | `size` (Decimal) | `size==0` only legal on DELETE in the canonical engine; IBKR zero-size updates must map to DELETE when the feed semantics imply removal |
| `marketMaker` (when supplied) | `provenance["market_maker"]` | explicit provenance, never a state-machine field |
| reqId (subscription) | `subscription_id` | feeds the generation gate; a new reqId without an explicit RESET/snapshot is REJECTED (GENERATION_MISMATCH) until recovery |
| TWS tick time / client receive time | `source_time_ns` / `received_time_ns` | ns epoch; engine never reads a wall clock |
| per-event counter (when TWS pacing allows deriving one) | `sequence` (optional) | IBKR does not guarantee a usable monotone sequence — `NO_SEQUENCE` is the truthful default; G6 must not fabricate continuity |

G6 scope (per G5 §18, not started): entitlement/pacing/subscription lifecycle,
full-depth snapshot on subscribe via `replace_from_snapshot`, incremental
`DepthUpdate` application to the same `IncrementalOrderBook`, and L1 quote
wiring. No canonical-domain change is expected to be required.
