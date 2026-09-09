# 14l — G14 Current-State Matrix (Unified Selector + Query Keys + Options/Futures Surfaces)

**Status:** CLOSED (2026-09-09 G14 implementation + closure validation pass)  
**Starting FULL baseline:** 4380 / 48 / 0 / 0  
**G14 closure FULL:** **4391/48/0/0** (2026-09-09 closure session)  
**G14 scope:** Canonical multi-asset selector, query-key factory, Options/Futures product surfaces wired to G12/G13 runtime

## Archaeology summary (pre-G14)

| Surface | Current identity key | Account scoped? | Mode scoped? | Provider scoped? | As-of scoped? | Canonical identity? | Duplicate schema? | G14 disposition |
|---|---|---|---|---|---|---|---|---|
| `/symbols/search` (live) | provider symbol | NO | NO | PARTIAL | NO | SYMBOL_KEYED | DUPLICATE vs canonical | **COMPATIBILITY** — retained for live observational |
| `/instruments/search` (new) | `instrument_id` | NO | NO | provenance only | NO | **CANONICAL** | shared selector DTO | **CANONICAL** |
| Route `:symbol` param | display symbol uppercased | NO | NO | NO | NO | SYMBOL_KEYED | — | **PARTIAL → CANONICAL codec** (`encode/decode`) |
| `queryKeys.workspace*` | symbol string | NO | implicit via mode routes | NO | partial (`dataMode`) | SYMBOL_KEYED | ad-hoc arrays | **PARTIAL** — legacy lanes retained; G14 factory for product keys |
| `queryKeys.paperPortfolio` | mode only | PARTIAL | YES | NO | NO | N/A | — | **SAFE_TO_RETAIN** + factory mirror |
| Options workspace `/workspace/:symbol/options` | symbol | NO | route mode | NO | NO | SYMBOL_KEYED | whale fixture schema | **COMPATIBILITY** research lane preserved |
| Futures workspace `/workspace/:symbol/futures` | symbol (ES) | NO | route mode | NO | NO | SYMBOL_KEYED | whale depth schema | **COMPATIBILITY** research lane preserved |
| `/workspace/:id/options-product` | canonical `instrument_id` | YES (`account_id`) | YES (`mode`) | YES (`provider` in runtime) | via `as_of_context` | **CANONICAL** | G14 envelope | **CANONICAL** |
| `/workspace/:id/futures-product` | canonical `instrument_id` | YES | YES | YES | via `as_of_context` | **CANONICAL** | G14 envelope | **CANONICAL** |
| Paper preview/submit | canonical via G3 admission | YES | YES | NO | replay cursor | **CANONICAL** | shared preview schema | **CANONICAL** (unchanged authority) |
| `portfolio/options_ledger.py` | symbol | NO | NO | NO | NO | LEGACY | DUPLICATE | **LEGACY** — not used by G14 surfaces |
| `CanonicalPortfolio` | `instrument_id` | YES | YES | NO | NO | **CANONICAL** | — | **AUTHORITATIVE** for G14 product positions |

## G14 delivered components

| Component | Path | Role |
|---|---|---|
| Instrument selector API | `ui_api/instrument_selector.py` | Canonical backend discovery + actionability |
| Route codec | `ui_api/instrument_route_codec.py` | Deterministic URL round-trip |
| Product projections | `ui_api/g14_product_projections.py` | Options/Futures G12 runtime + G13 Paper state |
| Query key factory | `ui/src/api/queryKeyFactory.ts` | Deterministic cache isolation |
| Instrument identity helpers | `ui/src/api/instrumentIdentity.ts` | Route serialization + selection semantics |
| Selector UI | `ui/src/components/instrument-selector/CanonicalInstrumentSelector.tsx` | Unified multi-asset selector |
| Options product UI | `ui/src/components/options/OptionsProductSurface.tsx` | Contract-centric Paper surface |
| Futures product UI | `ui/src/components/futures/FuturesProductSurface.tsx` | Contract-centric margin truth |

## Query-key isolation matrix (G14 factory)

| Case | Isolated? | Evidence |
|---|---|---|
| same equity / two accounts | YES | `queryKeyFactory.paperPortfolio` / `optionsProduct` account dimension |
| same equity / Demo vs Paper | YES | `mode` dimension |
| same equity / two providers | YES | `provider` dimension on `canonicalQueryKey` |
| history / two as_of | YES | `asOf` on `workspaceLane` |
| equity vs option | YES | distinct `instrumentId` |
| option A vs B | YES | distinct `instrumentId` |
| future family vs contract | YES | distinct `instrumentId` + `execution_available` |
| future expiry A vs B | YES | distinct `instrumentId` |
| continuous vs contract | YES | distinct kind + non-executable family |
| BTC/USD vs BTC/USDT | YES | distinct canonical pair ids |
| same pair / two venues | YES | venue in canonical identity |
| deterministic inputs | YES | stable param ordering test |
| object ordering | YES | sorted param keys |

## Product readiness after G14

| Domain | Status | Evidence |
|---|---|---|
| EQUITIES | **PRODUCT_READY** | Existing equity flows preserved; selector includes TRADABLE_SECURITY |
| OPTIONS | **PARTIAL → PRODUCT_READY (Paper)** | Options product surface + G13 Paper lifecycle; chain research lane retained |
| FUTURES | **PARTIAL → PRODUCT_READY (Paper w/ margin facts)** | Futures product surface + explicit margin truth |
| CRYPTO | **REFERENCE_ONLY** | Selector representation; no full workspace |
| BONDS | **REFERENCE_ONLY** | Selector representation only |
| COMMODITIES | **REFERENCE_ONLY** | Not expanded in G14 |

## Backlog / root-cause movement

| Item | Pre-G14 | Post-G14 |
|---|---|---|
| RC-010 query-key isolation | OPEN | **MATERIALLY ADDRESSED** — canonical factory + tests |
| RC-011 frontend/backend schema duplication | OPEN | **PARTIAL** — G14 envelope for product surfaces; legacy lanes retained |
| Multi-asset selector | MISSING | **CANONICAL** |
| Options/Futures product surfaces | PARTIAL | **OPERATIONAL (Paper)** |
