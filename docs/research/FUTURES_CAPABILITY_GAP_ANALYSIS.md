# Futures Capability Gap Analysis (Deliverable 7)

**Date:** 2026-08-18

---

## Data availability matrix

| Data | Available | Missing | Stale/Delayed | Provider | Research-only |
|---|---|---|---|---|---|
| ES L2 depth (fixture) | ✓ synthetic slice | Full session | Bounded 10 snapshots | fixture_futures | — |
| ES L2 depth (live) | ✓ via donor bridge | Not replay-admitted | Real-time when bridge up | FuturesX/IBKR | — |
| Contract specifications | ✓ ES baseline in code | Historical spec changes | — | ES_CONTRACT_SPEC | — |
| Full term structure quotes | — | ✗ | — | — | F3 |
| Official open interest | — | ✗ | — | CME/exchange | F4 |
| COT positioning | — | ✗ | Weekly + 3-day delay | CFTC | F4 |
| Margin requirements | — | ✗ | Daily possible | CME/broker | F8 |
| Settlement prices | — | ✗ | Daily | Exchange | F2/F10 |
| Spot/reference (basis) | — | ✗ | — | Multiple | F3 |
| Inventory (energy/ag) | — | ✗ | Weekly | EIA/DOA | F7 |
| Macro consensus/actuals | — | ✗ | Event-time critical | Multiple | F7 |
| Treasury CTD/deliverables | — | ✗ | — | Exchange | F6 |
| Options on futures chain | Partial BIYA equity | ES/CME options | — | Tradier-class | O1 |
| MBO / queue data | — | ✗ | — | IBKR/etc | Future |
| Crypto perp funding/OI | — | ✗ | — | Exchanges | Future |

---

## Capability gaps by subsystem

| Subsystem | Implemented | Gap |
|---|---|---|
| F1 Contract correctness | Schema + ES spec + tests | Wire to ingestion; multi-product specs |
| F2 Roll / continuous | Lead selection v1 | Roll execution in simulator; continuous series builders |
| F3 Curve/basis/carry | Schema only | Engines, data feeds |
| F4 OI/COT | COT PIT helper + fixture ingest | Crowding models — **DONE** (fixture scope) |
| F5 Trend/carry baselines | Settlement bars + carry history fixture | Empirical models — **DONE** (fixture scope) |
| F6 Family models | Taxonomy enum | Per-family plugins |
| F7 Macro/fundamentals | Catalyst lane partial | Family-specific interfaces |
| F8 Leverage stress | Quality flags | Margin engine, liquidation models |
| F9 Relative value | — | Spread objects, hedge ratios |
| F10 Simulator | Bar equity only | Rolls, VM, limits, spreads |
| Cross-lane | Depth publisher partial | Curve, positioning, stress publishers |
| UI | Depth workspace | Intelligence panels per spec §101–104 |
| EV | Shared research | Futures domain inputs |

---

## Provider capability requirements (F110)

| Capability | Priority | Fallback |
|---|---|---|
| Real-time futures quotes | P1 | Fixture |
| Historical futures quotes | P2 | Deferred ADR-DATA-001 |
| L2 depth | P1 (ES) | Fixture |
| Contract specifications | P1 | Hardcoded spec + quality flag |
| Open interest | P2 | Disable OI features |
| Full term structure | P2 | Single contract only |
| COT | P2 | Fail closed on positioning |
| Margin | P3 | Disable leverage stress |
| Settlement | P2 | Use last trade + flag |
| Inventory reports | P3 | Family fundamentals degraded |
| CTD data | P3 | Treasury family degraded |

---

## Reconstructable vs must-acquire

| Reconstructable | Must acquire |
|---|---|
| Lead contract from volume/OI if full chain available | COT reports |
| Calendar spreads from curve | Official margin tables |
| Implied repo (Treasury) from market | Delivery basket specs |
| Session labels from timestamps | MBO queue history |
