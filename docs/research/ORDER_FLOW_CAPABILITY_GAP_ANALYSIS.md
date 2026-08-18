# Order Flow Capability Gap Analysis (Deliverable 7)

**Date:** 2026-08-18

---

## Provider capability matrix (current vs required)

| Capability | NVDA fixture | ES fixture | Live adapters | Required for |
|---|---|---|---|---|
| Trade prints | Bar aggregates only | — | None authorized | CVD, velocity |
| Native aggressor | Metadata (`quality=tick`) | — | None | OF1 confidence |
| L1 quotes | BBO in depth fixture | BBO in depth fixture | FuturesX bridge | OF3 |
| L2/MBP | 10 levels (NVDA) | 10 levels (ES) | Partial bridge | OF4, OF5 |
| MBO | No | No | No | OF10 |
| Sequence numbers | No | No | No | Book reconstruction |
| Exchange timestamps | ISO bar times | ISO snapshot times | Bridge partial | PIT correctness |
| Historical trades | Fixture slice | — | No | Walk-forward |
| Historical L2 | Fixture | Fixture | No | OFI research |
| Historical MBO | No | No | No | Queue sim |
| Venue consolidation | Single venue implied | CME centralized | — | Equity fragmentation |

---

## Feature gap by roadmap phase

| Phase | Capability | Status |
|---|---|---|
| OF1 | ClassifiedTrade + aggressor provenance | **DONE** (module) |
| OF2 | CVD + confidence metrics | **DONE** (module + workspace) |
| OF3 | L1 + microprice + QI | **DONE** (module + workspace) |
| OF4 | OFI book-flow (adds/cancels) | NOT STARTED |
| OF5 | Multi-level OFI | NOT STARTED |
| OF6 | Liquidity dynamics | NOT STARTED |
| OF7 | Absorption / exhaustion | NOT STARTED |
| OF8 | Short-horizon forecasts | NOT STARTED |
| OF9 | Execution forecasts | NOT STARTED |
| OF10 | MBO / queue modeling | NOT STARTED |
| OF11 | Metaorder research | NOT STARTED |
| OF12 | Advanced LOB ML | NOT STARTED |

---

## Data procurement priorities

1. **ES futures L2 historical** — primary research lab (centralized book, deep data)
2. **Native aggressor trade tape** — for OF1 validation
3. **MBO sample** — for OF10 queue research (capability-gated)
4. **Equity consolidated tape** — venue-aware, not single-venue DOM as "the market"

---

## Silent substitution risks (must fail closed)

| Missing | Must NOT do |
|---|---|
| Native aggressor | Label heuristic as native |
| L2 | Synthesize deeper depth |
| MBO | Claim exact queue position |
| Partial venue coverage | Claim total-market flow |
