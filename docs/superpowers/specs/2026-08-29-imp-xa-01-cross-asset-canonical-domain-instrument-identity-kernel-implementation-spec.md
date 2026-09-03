# IMP-XA-01 implementation spec (2026-08-29)

## Purpose

Establish the cross-asset canonical identity and analytical-domain participation kernel.
XA-01 does not implement cross-asset analytics, rates engines, or live provider expansion.

## Identity audit summary

| Existing concept | Authority | Reuse decision |
|---|---|---|
| `SymbolMapping` (`providers/contracts.py`) | Provider layer | GENERALIZE → XA alias model |
| `short_intelligence.SymbolMap` | PIT equity aliases | GENERALIZE → bitemporal alias resolution |
| `FuturesContract` / `instrument_family` / `contract_id` (F1) | Futures foundation | REUSE_DIRECTLY + compatibility adapter |
| `OptionContract` / `underlying_id` / `option_id` (O1) | Options foundation | REUSE_DIRECTLY + compatibility adapter |
| `fred.canonical_indicator_id` | Macro evidence (non-tradable) | REUSE_DIRECTLY — separate identity plane |
| Envelope `instrument_id` / `venue_id` | Event normalization | ADAPT — opaque refs resolve via XA |
| `paper.build_instrument_ref` | Execution refs | REFERENCE — not canonical authority |
| `BitemporalReferenceStore` + `ReferenceKind.SYMBOL_MAPPING` | Platform P0 | REUSE_DIRECTLY for alias persistence hook |

## Canonical ownership

- **XA-01 owns:** canonical instrument identity, structural asset class, analytical-domain participation, typed relationships, external/provider aliases, denomination metadata.
- **XA-01 does not own:** OF-01 ledger identity, event UUID5 identity, macro indicator identity, market prices, portfolio positions.

## Core invariant

```text
instrument identity ≠ provider symbol ≠ display ticker ≠ analytical domain ≠ asset class ≠ contract family
```

One economic object → one canonical identity. Multiple analytical domains allowed without duplicate identities.

## Taxonomy

### AssetClass (structural)

`EQUITY`, `ETF_FUND`, `FUTURE`, `OPTION`, `SOVEREIGN_DEBT`, `COMMODITY`, `FX_PAIR`, `CURRENCY`, `INDEX_BENCHMARK`

### InstrumentKind (granularity)

`TRADABLE_SECURITY`, `COMMODITY_ECONOMIC`, `FUTURE_FAMILY`, `FUTURE_CONTRACT`, `OPTION_CONTRACT`, `SOVEREIGN_SECURITY`, `CURRENCY_UNIT`, `FX_PAIR`, `INDEX_BENCHMARK`

### AnalyticalDomain (participation, not identity)

`EQUITY`, `COMMODITY`, `MONETARY_RESERVE`, `RATES`, `SOVEREIGN`, `MACRO`, `FX`, `DERIVATIVES`, `SAFE_HAVEN`

### RelationshipType (versioned, finite)

`UNDERLYING`, `CONTRACT_ROOT`, `DENOMINATED_IN`, `BENCHMARK_OF`

## Identity granularity rules

| Object | Identity material | Distinct from |
|---|---|---|
| Equity AAPL | venue + symbol | provider symbol |
| ES family | family root `ES` | contract instances |
| ES contract | `contract_id` e.g. `ES202506` | family root |
| Option | `option_id` encoding | underlying |
| Sovereign | CUSIP or issuer+maturity+coupon | yield observations |
| Gold commodity | `commodity_code=GOLD` | GC futures |
| GC future | `contract_id` | gold economic object |
| EUR currency | ISO `EUR` | EUR/USD pair |
| EUR/USD pair | base `EUR` + quote `USD` | USD/EUR (reversed) |

## Deterministic identity

Profile: `imp-xa01-instrument-identity-v1`. Canonical ID: `XA01:{sha256_prefix}` from sorted canonical JSON of profile + kind + asset_class + identity_key.

## Alias model

Scoped by `(provider_id, identifier_type, alias_value)`. Resolution: `RESOLVED`, `AMBIGUOUS`, `UNKNOWN`, `CONFLICT`. Provider aliases do not create instruments.

## Compatibility

Legacy `instrument_id` strings (equity tickers, F1/O1 contract IDs) resolve through compatibility adapters without big-bang migration.

## Persistence

In-memory registry is authoritative for XA-01 v1. Optional bitemporal `SYMBOL_MAPPING` payload hook; Mongo not required.

## OF-03

Register `XA01.OP.STATUS`, `XA01.OP.RESOLVE`, `XA01.OP.SHOW_INSTRUMENT`, `XA01.OP.LIST_DOMAINS`, `XA01.OP.VALIDATE_REGISTRY`.

## Tests

`tests/xa01/` — vertical slice (equity, sovereign, gold multi-domain), FX, aliases, derivatives, compatibility.

## Acceptance

`artifacts/imp-rebase/XA01/` with audit, taxonomy, representative cases, compatibility evidence, file hashes, acceptance report, known limitations.
