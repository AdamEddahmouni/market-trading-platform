# Main Screener universe architecture

Status: **canonical — owner decision (recorded 2026-09-27, Screener S9; Crypto
implemented 2026-09-28, Screener S10).**

This document fixes what a Main Screener *universe* is, which universes IMP
has, and which subjects are intelligence layers rather than universes. Agents
must not reinterpret an intelligence lens, a view, or a panel as an asset
universe.

## What a universe is

A universe is a first-class set of instruments that share materially the same:

- instrument identity (ticker, contract id, CUSIP/ISIN, trading pair);
- market structure and venue model;
- provider semantics;
- trading or publication session model;
- fields, filters, and pricing conventions;
- analytics.

Each universe is one entry in the typed registry
(`ui_api/screener_universes.py`) and runs through the one canonical query
(`ui_api/screener_query.py`: universe, filters, search, sort, direction,
offset/limit) with server-side paging and truthful counts (see
[Screener S6](SCREENER_S6.md)). A universe never gets a separate query
architecture.

## First-class core universes

| # | Universe | Registry id | Status |
|---|----------|-------------|--------|
| 1 | US Equities | `US_EQUITIES` | implemented (S1) |
| 2 | ETFs | `US_ETFS` | implemented (S5) |
| 3 | Futures | `FUTURES` | implemented (S5) |
| 4 | Bonds / Fixed Income | `BONDS` | implemented (S9) — [Screener S9](SCREENER_S9_BONDS.md) |
| 5 | Crypto | `CRYPTO` | implemented (S10) — [Screener S10](SCREENER_S10_CRYPTO.md) |

**IMPLEMENTED CORE UNIVERSES: 5/5** — US Equities, ETFs, Futures,
Bonds / Fixed Income, Crypto.

The registry holds exactly these five. Crypto rows are venue-qualified spot
pairs (XA-01 `CRYPTO_PAIR`, e.g. `BTC/USD` on Kraken): one venue's market, never
a consolidated crypto price.

### Membership (Screener S13)

Membership is decided by recorded evidence, never by which provider endpoint
returned a row ([Screener S13](SCREENER_S13_UNIVERSE_INTEGRITY.md)):

- `US_EQUITIES`: every US-listed security (Finviz `geo_usa`) that the
  reference does not classify as an exchange-traded fund. REITs, closed-end
  funds, BDCs, royalty trusts, and SPAC shells are listed equities, each with a
  recorded category.
- `US_ETFS`: exchange-traded funds only. The provider type must be `ETF`
  **and** the reference must classify the listing as an exchange-traded fund;
  anything unresolved is rejected (fail-closed). Bond ETFs are ETFs, never
  `BONDS`.
- `FUTURES`: the current dated lead contract of each provider main alias.
  Treasury futures are futures, never `BONDS`.
- `BONDS`: CUSIP-identified marketable Treasury securities. Curve points are
  reference fields, never rows.
- `CRYPTO`: venue-qualified spot pairs. Derivatives and tokenized assets are
  excluded.

An instrument belongs to one core universe; `US_EQUITIES` and `US_ETFS` are
disjoint by construction. `tests/platform/test_screener_s13.py` enforces the
cross-universe invariants.

Inside a universe, categories are filters and views, never new universes.
For example, Treasuries, corporate bonds, agency debt, and municipals are
categories inside `BONDS`; commodity futures families are categories inside
`FUTURES`.

## Options — conditional sixth universe

Options is **not** a Screener universe today. The current behavior (S7)
stays: the selected underlying opens Options context — a Preview tab and an
option-chain dock panel.

Options may become an optional sixth universe only when **both** hold:

1. the owner explicitly authorizes it; and
2. IMP has a truthful universe-wide option-contract dataset that supports
   broad filtering, sorting, paging, and result counts across all contracts.

Per-symbol selected option chains do not satisfy condition 2.

## Commodities — inside Futures

Commodities do not get a top-level universe by default. Commodity trading is
represented through the Futures universe and its contract families (energy,
metals, agriculture, livestock). Spot or reference commodity identities (for
example XA-01 `COMMODITY_SPOT`) may exist for context, macro relationships, or
pricing references; they do not justify a duplicate universe without a later
explicit owner decision. There is no `COMMODITIES` registry entry.

## Intelligence layers — never universes

These are cross-instrument evidence and analytics, delivered through views,
panels, universe-complete filters, selected-instrument context, and
disclosures:

| Layer | Delivered as |
|-------|--------------|
| Whales (large-participant evidence) | views, panels, filters where universe-complete, selected-instrument context, disclosures; implemented in [Screener S12](SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md) as CFTC positioning (Futures view and panel) with large prints linked to Order Flow, participant unknown — **never a universe** |
| Institutions (institutional activity) | the same, across instruments; implemented in [Screener S12](SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md) as the Institutional view (Form 4, 13D/13G) and the Institutional & Whale panel (plus 13F quarter-end holdings) |
| Congressional and government records | a cross-universe intelligence layer — **never a universe**; implemented in [Screener S12](SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md) (Congress view, Congress & Government panel: House PTRs, federal awards, lobbying — as filed, never scored) |
| Short Squeeze | a US Equities view and a specialist panel (S8) |
| Options | selected-underlying context and panel (S7), until the conditional rule above is met |
| Order Flow, CVD, Level 2 | specialist panels (S4) |
| Catalysts, Insiders | evidence in Preview and panels |
| Rates & Curve | a Bonds specialist panel (S9) |
| News (headlines, sentiment, analysis) | a cross-universe intelligence layer: views, panels, and Preview context across the five universes — **never a universe**; implemented in [Screener S11](SCREENER_S11_NEWS.md) (News view, News & Analysis panel, Preview News) |

## Governance rule

**No agent may create a Screener universe because a subject deserves a tab,
view, or panel.** A new universe — including Options, Commodities, News, or any other —
requires explicit owner authorization. Everything else is expressed as a
view, filter, or panel inside an existing universe.

Tests pin the registry by exact equality: `tests/platform/test_screener_s9.py`
(`UniverseArchitectureTests`) and `tests/platform/test_screener_s10.py`
(`CryptoUniverseTests`) fail if the registry is anything other than the five
implemented universes — an unauthorized sixth entry fails them.
`tests/platform/test_screener_s11.py` (`ArchitectureTests`) additionally pins
that News is not a registry entry.
