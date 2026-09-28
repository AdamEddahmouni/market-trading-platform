# Main Screener universe architecture

Status: **canonical — owner decision (recorded 2026-09-27, Screener S9).**

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
| 5 | Crypto | — | **documented only; not implemented, not in the registry** |

The registry holds exactly the implemented universes. Crypto is part of the
canonical model but has no registry entry, code, or UI until the owner
authorizes its implementation.

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
| Whales (large-participant evidence) | views, panels, filters where universe-complete, selected-instrument context, disclosures |
| Institutions (institutional activity) | the same, across instruments |
| Short Squeeze | a US Equities view and a specialist panel (S8) |
| Options | selected-underlying context and panel (S7), until the conditional rule above is met |
| Order Flow, CVD, Level 2 | specialist panels (S4) |
| Catalysts, Insiders | evidence in Preview and panels |
| Rates & Curve | a Bonds specialist panel (S9) |

## Governance rule

**No agent may create a Screener universe because a subject deserves a tab,
view, or panel.** A new universe — including Crypto, Options, or any other —
requires explicit owner authorization. Everything else is expressed as a
view, filter, or panel inside an existing universe.

Tests pin the registry: `tests/platform/test_screener_s9.py`
(`UniverseArchitectureTests`) fails if any universe other than the four
implemented ones appears.
