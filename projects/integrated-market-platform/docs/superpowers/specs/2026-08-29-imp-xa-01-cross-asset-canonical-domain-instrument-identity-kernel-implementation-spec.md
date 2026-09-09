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

### AssetClass (structural) — ONE canonical vocabulary

`EQUITY`, `ETF_FUND`, `FUTURE`, `OPTION`, `SOVEREIGN_DEBT`, `BOND`, `COMMODITY`, `CRYPTO`, `FX_PAIR`, `CURRENCY`, `INDEX_BENCHMARK`

This is the single canonical asset-class vocabulary (G1 / CON-01 / RC-004).
`paper.contracts.ASSET_CLASSES` is a **deprecated** backward-compatibility view
over this vocabulary and must not be used by new code.

### InstrumentKind (granularity)

`TRADABLE_SECURITY`, `COMMODITY_ECONOMIC`, `COMMODITY_SPOT`, `FUTURE_FAMILY`, `FUTURE_CONTRACT`, `CONTINUOUS_SERIES`, `OPTION_CONTRACT`, `SOVEREIGN_SECURITY`, `BOND`, `CRYPTO_PAIR`, `CURRENCY_UNIT`, `FX_PAIR`, `INDEX_BENCHMARK`

- Specific-contract/security kinds are executable forms: `TRADABLE_SECURITY`, `FUTURE_CONTRACT`, `OPTION_CONTRACT`, `CRYPTO_PAIR`.
- Family/reference/aggregate kinds are never executable: `FUTURE_FAMILY`, `CONTINUOUS_SERIES`, `COMMODITY_ECONOMIC`, `COMMODITY_SPOT`, `SOVEREIGN_SECURITY`, `BOND`, `CURRENCY_UNIT`, `FX_PAIR`, `INDEX_BENCHMARK`.

### Tradability (executable-vs-reference semantics, G1)

`TRADABLE` · `REFERENCE_ONLY` · `SYNTHETIC` · `CONTINUOUS_SERIES`

Every canonical identity carries explicit tradability. Only `TRADABLE` may
become an order target; `REFERENCE_ONLY`/`SYNTHETIC`/`CONTINUOUS_SERIES`
fail closed at every execution boundary (`xa01.tradability.assert_executable`,
`paper.contracts._assert_instrument_executable`).

### AnalyticalDomain (participation, not identity)

`EQUITY`, `COMMODITY`, `MONETARY_RESERVE`, `RATES`, `SOVEREIGN`, `MACRO`, `FX`, `DERIVATIVES`, `SAFE_HAVEN`

### RelationshipType (versioned, finite)

`UNDERLYING`, `CONTRACT_ROOT`, `DENOMINATED_IN`, `BENCHMARK_OF`

## Identity granularity rules

| Object | Identity material | Distinct from | Tradability |
|---|---|---|---|
| Equity AAPL | venue + symbol | provider symbol | TRADABLE |
| ES family | family root `ES` | contract instances | REFERENCE_ONLY |
| ES contract | `contract_id` e.g. `ES202506` | family root | TRADABLE |
| ES continuous | family root + methodology | family and every contract | CONTINUOUS_SERIES (never executable) |
| Option | `option_id` encoding | underlying | TRADABLE |
| Sovereign | CUSIP or issuer+maturity+coupon | yield observations | REFERENCE_ONLY |
| Corporate bond | security_id (CUSIP/ISIN) or issuer+maturity+coupon | sovereign securities and equity tickers | REFERENCE_ONLY |
| Gold commodity | `commodity_code=GOLD` | GC futures | REFERENCE_ONLY |
| Gold spot reference | commodity_code + quote currency (+venue) | gold economic object and GC futures | REFERENCE_ONLY |
| GC future | `contract_id` | gold economic object | TRADABLE |
| BTC/USD pair | base `BTC` + quote `USD` (+venue/network) | BTC/USDT, USD/BTC, bare BTC | TRADABLE |
| EUR currency | ISO `EUR` | EUR/USD pair | REFERENCE_ONLY |
| EUR/USD pair | base `EUR` + quote `USD` | USD/EUR (reversed) | REFERENCE_ONLY |

## Deterministic identity

Profile: `imp-xa01-instrument-identity-v1`. Canonical ID: `XA01:{sha256_prefix}` from sorted canonical JSON of profile + kind + asset_class + identity_key.

## Alias model

Scoped by `(provider_id, identifier_type, alias_value)`. Resolution: `RESOLVED`, `AMBIGUOUS`, `UNKNOWN`, `CONFLICT`. Provider aliases do not create instruments.

## Compatibility

Legacy `instrument_id` strings (equity tickers, F1/O1 contract IDs) resolve through compatibility adapters without big-bang migration.

## Continuous-future non-execution invariant (G1, mandatory)

A continuous futures series (`InstrumentKind.CONTINUOUS_SERIES`), a futures
family/root (`FUTURE_FAMILY`), or any other synthetic/reference identity can
never become an executable order target — regardless of naming conventions
such as `ES1!` and regardless of which provider alias resolves to it.

The guard lives at two fail-closed boundaries:

1. **Canonical resolution** — `xa01.tradability.assert_executable(record)` raises
   `Xa01Error(NON_EXECUTABLE_INSTRUMENT)`; `xa01.resolver.resolve_executable_alias`
   applies it after alias resolution.
2. **Order-intent creation** — `paper.contracts.build_user_order_intent` rejects
   any instrument reference carrying a non-executable `instrument_kind` or a
   non-`TRADABLE` `tradability` (`INSTRUMENT_NOT_EXECUTABLE`).

Specific futures contracts stay tradable; existing futures analytics (including
continuous series data builders in `futures/continuous.py`) are unchanged.

## Persistence

In-memory registry is authoritative for XA-01 v1. Optional bitemporal `SYMBOL_MAPPING` payload hook; Mongo not required.

## OF-03

Register `XA01.OP.STATUS`, `XA01.OP.RESOLVE`, `XA01.OP.SHOW_INSTRUMENT`, `XA01.OP.LIST_DOMAINS`, `XA01.OP.VALIDATE_REGISTRY`.

## Tests

`tests/xa01/` — vertical slice (equity, sovereign, gold multi-domain), FX, aliases, derivatives, compatibility.

## Acceptance

`artifacts/imp-rebase/XA01/` with audit, taxonomy, representative cases, compatibility evidence, file hashes, acceptance report, known limitations.
