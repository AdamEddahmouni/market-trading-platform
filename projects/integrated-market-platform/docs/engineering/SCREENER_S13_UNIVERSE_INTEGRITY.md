# Main Screener S13 — Universe integrity, classification & catalog hardening

Status: **implemented; live catalog acceptance passed on the owner workstation
2026-09-29** (see [Acceptance](#acceptance)). Registry unchanged: exactly five universes
([architecture](SCREENER_UNIVERSE_ARCHITECTURE.md)).

S13 answers one question for every row of every Screener universe: **why is
this instrument in this universe?** The answer is deterministic and recorded:
provider classification, reference classification, canonical XA-01 identity,
an admission decision, and a reason when rejected. S13 adds no universe,
view, panel, or feature.

## The defect

During S12 live acceptance the ETF universe contained EQIX and WY (equity
REITs) and AIO (a closed-end fund), and the ETF Congress view matched
disclosures on them because they were universe members.

**Root cause.** `project_etf_catalog` admitted every row that Moomoo OpenD
`get_stock_basicinfo(Market.US, SecurityType.ETF)` returned with
`stock_type == "ETF"`. That provider type is a broad pooled/pass-through
bucket, not "exchange-traded fund": it also returns equity REITs, closed-end
funds, and OTC grantor trusts (S6 already met OTC trusts such as BCHG in this
catalog through snapshot refusals). The provider row carries no REIT, CEF, ETN,
or fund-structure flag. The fields it does carry are `code`, `name`,
`stock_type`, `stock_child_type`, `exchange_type`, `listing_date`, `delisting`,
and `stock_owner`; none separates an ETF from a REIT. S5 recorded
**6,306 provider-typed "ETFs"** (2026-09-27) as the ETF universe.

A second defect sat behind the first. US Equities is the Finviz Elite export
(`geo_usa,ind_stocksonly`), which already contained EQIX and WY, so those two
REITs were in **both** exchange-listed universes. The duplicate was invisible to
id checks because the universes use different identity schemes: US Equities
uses the ticker as `instrument_id`, and ETFs use an XA-01 `ETF_FUND` registry id.

## Universe definitions

| Universe | Exact definition | Catalog source | Identity |
|----------|------------------|----------------|----------|
| `US_EQUITIES` | Every US-listed (Finviz `geo_usa`) security that Finviz does **not** classify as an exchange-traded fund: common stock, REITs, closed-end funds, BDCs, royalty trusts, SPAC shells, each with its recorded category | Finviz Elite export, filter `geo_usa` | XA-01 `EQUITY` / `TRADABLE_SECURITY`; ticker |
| `US_ETFS` | Exchange-traded funds: rows the provider types `ETF` **and** the reference classifies as industry `Exchange Traded Fund` | Moomoo OpenD ETF catalog, admitted against the Finviz reference | XA-01 `ETF_FUND` / `TRADABLE_SECURITY`; ticker alias |
| `FUTURES` | The current dated lead contract of each Moomoo futures main alias; provider type `FUTURE`, not delisted, not expired | Moomoo OpenD futures catalog | XA-01 `FUTURE` / `FUTURE_CONTRACT` |
| `BONDS` | Marketable US Treasury securities (bills, notes, bonds, TIPS, FRNs) identified by CUSIP | Treasury Fiscal Data auctions + MSPD | XA-01 `SOVEREIGN_DEBT` / `SOVEREIGN_SECURITY`; CUSIP |
| `CRYPTO` | Kraken spot pairs with provider asset class `currency` on both legs and status `online` | Kraken Spot `AssetPairs` | XA-01 `CRYPTO` / `CRYPTO_PAIR`; base, quote, venue, `SPOT` |

`US_EQUITIES` and `US_ETFS` are **disjoint by construction**, because both
decisions read the same Finviz classification. An instrument appears in one
core universe only.

## Classification pipeline

```
provider catalog (raw rows, every classification field kept)
  → normalized classification  (screener_admission.reference_category: Finviz industry → category)
  → canonical XA-01 identity   (register_etf_fund / finviz_to_canonical — unchanged taxonomy)
  → admission decision         (admit_etf / admit_equity)
  → rejection reason           (deterministic code; audit/debug only)
```

All rules live in `src/market_platform_foundation/ui_api/screener_admission.py`.
There are no ETF checks in React. Classification runs once per catalog load,
alongside the existing catalog projection, and is cached with it. There are no
per-row or per-query remote calls.

**Categories** (`classification.category`) describe a listing *inside* a
universe, the way Treasury/corporate are categories inside `BONDS`. They are
not asset classes: XA-01 `EQUITY` and `ETF_FUND` remain the only structural
taxonomy.

| Finviz industry | Category |
|-----------------|----------|
| `Exchange Traded Fund` | `EXCHANGE_TRADED_FUND` |
| `REIT - …` (any) | `REIT` |
| `Closed-End Fund - …` (any) | `CLOSED_END_FUND` |
| `Shell Companies` | `SHELL_COMPANY` |
| any other industry | `LISTED_EQUITY` |
| empty | `UNCLASSIFIED` (never guessed) |

**Provenance.** Every admitted US Equities and ETF row carries
`classification`: universe, category, status, reason, basis, the raw provider
fields (ETF rows), and the reference sector/industry/country with its `as_of`.
That answers "why is this an ETF?" per row. The page envelope carries
`admission` (raw, accepted, rejected, reasons), and ETF `provider_health` gains
a `CLASSIFICATION_SOURCE` entry. The normal UI does not render any of this.

### Rejection reasons

| Reason | Universe | Meaning |
|--------|----------|---------|
| `WRONG_MARKET` | ETFs | provider code is not `US.` |
| `WRONG_PRODUCT_TYPE` | ETFs | provider type is not `ETF` |
| `DELISTED` | ETFs | provider delisting flag set |
| `INVALID_SYMBOL` | ETFs | provider ticker is not a listing symbol |
| `CLASSIFICATION_UNAVAILABLE` | ETFs | no reference classification has ever loaded (fail-closed) |
| `UNRESOLVED_SECURITY_TYPE` | ETFs | listing absent from the reference, or reference industry empty (fail-closed) |
| `REIT` | ETFs | reference industry `REIT - …` |
| `CLOSED_END_FUND` | ETFs | reference industry `Closed-End Fund - …` |
| `NOT_ETF` | ETFs | any other listed equity (BDC, royalty trust, shell, operating company) |
| `DUPLICATE_LISTING` | ETFs | a second provider row for an already admitted listing |
| `ETF_BELONGS_TO_US_ETFS` | US Equities | reference industry `Exchange Traded Fund` |

### Fail-closed behaviour

- **ETFs require positive evidence.** A provider "ETF" that the reference does
  not classify as an exchange-traded fund is rejected, never admitted as
  `UNKNOWN`. With no reference at all, the ETF universe shows no rows. It says
  why with `source_error = CLASSIFICATION_UNAVAILABLE`, a `CLASSIFICATION_SOURCE`
  health entry, and a specific UI message, instead of an empty "healthy"
  universe.
- **A failed reference refresh keeps the last good classification**, just as
  the equity rows are kept. It does not empty the ETF universe.
- **Sparse metadata does not drop valid ETFs.** Admission needs only the
  provider type and the reference industry. Holdings, AUM, issuer, and other
  fund metadata are not required.
- **US Equities admits `UNCLASSIFIED` rows.** The source is an equity export,
  and only the narrower ETF claim requires positive evidence. These rows are
  counted as `ambiguous` in the audit.

## Category decisions

| Category | Decision | Reason |
|----------|----------|--------|
| Open-end index ETFs (SPY, AGG) | `US_ETFS` | exchange-traded funds |
| Leveraged / inverse ETFs (TQQQ, SH) | `US_ETFS` | exchange-traded funds; leverage is a fund property, not a structure change |
| Actively managed ETFs (JEPI) | `US_ETFS` | exchange-traded funds |
| Bond ETFs (TLT, AGG) | `US_ETFS`, never `BONDS` | a fund share, not a CUSIP-identified debt security (S9: TLT ≠ Treasury bond) |
| Commodity ETPs as grantor trusts / LPs (GLD, IBIT) | `US_ETFS` when the reference classifies them as ETFs | exchange-listed pooled vehicles with creation/redemption, classified as ETFs by the reference |
| Unit investment trusts (SPY) | `US_ETFS` | a legal structure of an exchange-traded fund |
| Equity REITs (EQIX, WY) and mortgage REITs | `US_EQUITIES`, category `REIT` | listed operating equities |
| Closed-end funds (AIO) | `US_EQUITIES`, category `CLOSED_END_FUND` | listed shares of a closed-end investment company: fixed share count, no creation/redemption, trades at a premium or discount to NAV. With no CEF universe, the semantically closest existing treatment is a listed equity with a category distinction. Before S13, Finviz's opaque `ind_stocksonly` ("ex-Funds") filter decided whether CEFs appeared at all. |
| BDCs, royalty trusts, SPAC shells | `US_EQUITIES` (`LISTED_EQUITY` / `SHELL_COMPANY`), rejected from ETFs as `NOT_ETF` | listed operating/holding equities |
| OTC grantor trusts not on a US exchange | rejected from ETFs (`UNRESOLVED_SECURITY_TYPE`) | not exchange-listed, so absent from the exchange-listing reference |
| ADRs | neither | unchanged: US Equities is `geo_usa`, and ADRs are not ETFs |
| Preferred shares | neither | not in either catalog; a preferred in the provider ETF list would be unresolved and rejected |
| ETNs | see [limitations](#known-limitations) | debt notes, not funds; the current sources do not separate them |
| Treasury futures (ZN) | `FUTURES`, never `BONDS` | a contract, not a cash Treasury (S9 invariant) |
| Treasury curve points (10Y CMT) | a reference field on bond rows, never a row | a curve observation, not a CUSIP (S9 invariant) |
| Spot crypto pairs | `CRYPTO` | venue-qualified `CRYPTO_PAIR` |
| Crypto derivatives, tokenized assets, offline pairs | excluded | the Kraken spot endpoint carries no perpetuals, futures, or options; tokenized assets fail the `currency` class check and offline/delisted pairs fail the status check |

## Other universes (audited, unchanged)

- **FUTURES** admits only the dated lead contract of a provider main alias,
  with provider type `FUTURE`, not delisted, not expired. Index, option, and
  derivative-typed rows (`IDX`, `OPTION`, `DRVT`) are excluded by type. The
  commodity-family model is unchanged. No misclassification found.
- **BONDS** rows come only from Treasury Fiscal Data, keyed by CUSIP. Bond
  ETFs, Treasury futures, and curve points cannot enter: their sources are
  different catalogs. No misclassification found.
- **CRYPTO** admits Kraken spot pairs by provider asset class and status. It is
  never name-based, and identity stays venue-qualified. No misclassification found.

## Cross-universe invariants

`integrity_report` (the audit tool and `test_screener_s13.py`) enforces the following:

1. every row's XA-01 asset class and instrument kind are admitted by its universe spec;
2. every ETF row has category `EXCHANGE_TRADED_FUND` and status `ADMITTED`;
3. no US Equities row has category `EXCHANGE_TRADED_FUND`;
4. every Futures row is a lead contract with root and expiry; every Bonds row has a CUSIP; every Crypto row is a venue `SPOT` pair;
5. no XA-01 instrument id appears in two universes, and no exchange listing appears in both US Equities and ETFs.
   Listings are compared by normalized ticker, so `BRK.B` and `BRK-B` match.

An unexpected duplicate or row-contract violation fails the tests, and the audit
command exits non-zero on one.

## Counts

"Before" figures are taken from earlier live acceptances. "After" is the live
audit of 2026-09-29 05:07 UTC (see [Acceptance](#acceptance)); the provider and
reference catalogs move daily, so these are a dated observation, not constants.

| Universe | Before (recorded) | After (live, 2026-09-29) |
|----------|-------------------|--------------------------|
| `US_EQUITIES` | 4,291 (S12, 2026-09-28; `geo_usa,ind_stocksonly`) | **4,625** of 10,361 export rows; 5,736 rejected `ETF_BELONGS_TO_US_ETFS`; 0 ambiguous. The +334 is exactly Finviz's closed-end funds (195 Debt, 110 Equity, 29 Foreign), which `ind_stocksonly` had excluded |
| `US_ETFS` | 6,306 provider-typed rows (S5, 2026-09-27) | **5,734** of 6,312 provider-typed rows; 578 rejected: `CLOSED_END_FUND` 331, `REIT` 145, `UNRESOLVED_SECURITY_TYPE` 73, `NOT_ETF` 29 |
| `FUTURES` | 178 lead contracts (S5) | 178 (unchanged rules) |
| `BONDS` | 463 CUSIPs (S9) | 463 (unchanged rules) |
| `CRYPTO` | 1,354–1,355 pairs (S10) | 1,355 (unchanged rules) |

Fixture impact (`test_screener_s13.py`): 17 provider-typed "ETFs" → 8
admitted, 9 rejected (`REIT` 3, `NOT_ETF` 3, `UNRESOLVED_SECURITY_TYPE` 2,
`CLOSED_END_FUND` 1). An 18-row export → 10 US Equities (1 `UNCLASSIFIED`),
8 rejected `ETF_BELONGS_TO_US_ETFS`.

## Audit command

```
python tools/screener/universe_audit.py [--sample EQIX,WY,AIO,SPY,...] [--json]
python tools/screener/universe_audit.py --synthetic 12000     # offline performance run
```

For each universe it reports the raw provider count, accepted, rejected,
ambiguous, the top rejection reasons, and cold/warm catalog and query latency.
It also lists cross-universe duplicates, row-contract violations, and a
per-symbol explanation (where the symbol landed, whether the provider typed it
"ETF", the decision and reason, and the reference industry). It also reports
`REFERENCE_HAS_NO_ETF_INDUSTRY` when the reference classified no listing as an
ETF. It reads through the canonical query path and writes nothing. Exit
status: 0 clean, 1 integrity finding, 2 a universe did not load.

## Downstream impact

- **S11 News** and **S12 Congress / Institutional** build their universe
  index from the canonical query (`read_screener`), so they follow the
  corrected catalogs with no downstream special case. An EQIX disclosure now
  matches US Equities, not ETFs. Tests: `DownstreamTests` (the News and
  participant catalogs, and a Congress view where a provider-"ETF"-typed
  operating company no longer matches the ETF view).
- **Saved screens.** The schema is unchanged and no migration runs. A saved
  ETF screen still loads with its filters untouched. Removed instruments no
  longer match, and a screen that only matched them returns zero rows with no
  error.
- **Result counts** (`result_count`, `unfiltered_count`) are computed on the
  admitted catalog, never the provider raw count.
- **Search** runs over admitted rows: `EQIX` is found in US Equities, not in ETFs.
- **Filters.** The ETF filter catalog is unchanged (identity, exchange, and
  snapshot market fields). Equity-only fields (float, short, P/E) remain
  unavailable for ETFs.
- **Page tokens.** An ETF `result_set_id` now pins both the provider catalog
  and a fingerprint of the classification (every listing's category). A
  reclassification starts a new result set and cannot shift an in-flight page
  chain. A Finviz refresh that classifies every listing the same way keeps the
  token, so the 120 s export TTL does not break page chains.

## Performance

Classification is catalog-time work. Finviz is fetched once per 120 s TTL and
shared with US Equities; the ETF projection is memoized per (provider catalog,
classification fingerprint, trading date).

| Measurement (cloud container, synthetic, `--synthetic`) | Result |
|---------------------------------------------------------|--------|
| Pre-S13 ETF projection, 9,000 provider rows | 449 ms (all rows registered) |
| S13 ETF projection, 9,000 provider rows → 3,000 admitted | 186 ms (rejected rows are never registered) |
| US Equities export parse + admission, 12,000 rows | ≈195 ms over the 250 ms simulated download |
| Warm first page / warm search (ETFs, 3,000 rows) | 0.05 ms / 2.6 ms |

Live, owner workstation (Windows 11, Python 3.11.15, OpenD 10.10.7008, Finviz Elite), 2026-09-29:

| Universe | Cold catalog, all pages | Warm first page | Warm search |
|----------|-------------------------|-----------------|-------------|
| `US_EQUITIES` | 1,282 ms | 0.02 ms | 5.5 ms |
| `US_ETFS` | 1,734 ms | 0.04 ms | 9.8 ms |
| `FUTURES` | 3,428 ms | 0.06 ms | 0.21 ms |
| `BONDS` | 7,417 ms | 0.09 ms | 2.2 ms |
| `CRYPTO` | 817 ms | 5.4 ms | 6.3 ms |

The whole audit, with five cold catalogs, ran in 17 s. Through the HTTP API
(`/screener?universe=US_ETFS`), the ETF first page took 5.2 s cold (catalog
plus snapshot) and 82 ms warm; ETF searches took 70–115 ms.

## Tests

- `tests/platform/test_screener_s13.py` (29): category rules; EQIX, WY, AIO
  regression cases; generalization (mortgage REIT, BDC, royalty trust, SPAC);
  valid ETF structures (broad, bond, commodity trust, leveraged, inverse,
  active, spot-bitcoin trust); fail-closed unknown and unavailable reference;
  provider type, market, and delisting checks; share-class spelling; the ETF
  and equity pipelines with counts; search; last-good reference; page pinning and
  classification-fingerprint tokens;
  removed rows unknown to windows and previews; catalog-time classification;
  the five-universe integrity report and exact cross-universe placement
  (REIT, CEF, ETF, bond ETF, Treasury future, spot crypto, tokenized asset,
  cash Treasury, 10Y reference, common equity); misplaced-row and duplicate
  detection; futures type admission; News and Congress downstream behaviour;
  saved screens; ETF filters; the audit command (clean run, samples, the
  missing-ETF-industry finding, and closing the OpenD transport so a live run exits).
- `test_screener_s1.py` pins the new `geo_usa` export filter. S5/S6 ETF
  fixtures now supply explicit reference evidence (an ETF with no evidence is
  not admitted).
- UI: `ScreenerPage.test.tsx` shows the `CLASSIFICATION_UNAVAILABLE` message
  instead of an empty ETF grid.

## Acceptance

**Cloud validation** (Linux container, Python 3.11.15, Node 22.22.2, live
provider gates unset, no OpenD, IBKR, or MongoDB):

| Gate | Result |
|------|--------|
| `python tools/imp.py validate changed --paths-file <changed vs origin/main>` with isolated `APPDATA`/`LOCALAPPDATA` | **PASSED**: 33 suites, 5,912 tests, 43 skipped (environmental), 0 failures, 0 errors |
| `python tools/imp.py validate fast` | passed, 23 tests |
| Screener backend S1–S13 (`unittest`) | passed |
| `format`, `lint`, `tools/check_docs_links.py`, `git diff --check` | passed |
| `cd ui && npm test` | 154 files, 1,154 tests passed |
| `npm run typecheck`, `npm run build` | passed; initial JS 201.37 KiB gzip (budget 203 KiB) |

The first changed run failed on one genuine S13 omission: the new
`tools/screener/` directory was not yet in the repository-closure
classification. It is now classified with the provider and lane tooling. An
earlier attempt failed only because the container's symlinked venv resolved to
the system interpreter, and passed after recreating the venv with `--copies`.

The cloud container had no Moomoo OpenD and no Finviz Elite credentials, and
its egress policy denied the provider hosts, so live acceptance ran on the
owner workstation.

**Owner-workstation live acceptance (2026-09-29, 05:07–11:10 UTC).** Real
Moomoo OpenD catalog, real Finviz Elite export, live Treasury and Kraken; no
fixtures.

`universe_audit.py --sample EQIX,WY,AIO,SPY,AGG,GLD,TQQQ,SH,JEPI,TLT,IBIT`
**exit 0**. Row-contract violations 0, cross-universe duplicates 0, no findings.
Counts are in [Counts](#counts).

| Symbol | Universe | ETF decision | Finviz industry (live) |
|--------|----------|--------------|------------------------|
| EQIX | US Equities only | `REJECTED/REIT` | `REIT - Specialty` |
| WY | US Equities only | `REJECTED/REIT` | `REIT - Specialty` |
| AIO | US Equities only | `REJECTED/CLOSED_END_FUND` | `Closed-End Fund - Equity` |
| SPY, AGG, GLD, TQQQ, SH, JEPI, TLT, IBIT | ETFs only | `ADMITTED` | `Exchange Traded Fund` |

**Live Finviz strings** (the spellings the rules match, now verified): normal,
bond (AGG, TLT), commodity-trust (GLD), leveraged (TQQQ), inverse (SH), active
(JEPI), and spot-bitcoin (IBIT) funds are all `Exchange Traded Fund`, 5,736
listings. REITs are `REIT - <type>`: Mortgage (AGNC), Retail, Residential,
Office, Specialty (EQIX, WY), Diversified, Healthcare Facilities, Hotel & Motel,
and Industrial. CEFs are `Closed-End Fund - Debt` (PDI), `- Equity` (AIO), and
`- Foreign`. SPAC shells are `Shell Companies` (287). BDCs (ARCC, MAIN) are
`Asset Management`. Royalty trusts carry their operating industry (PBT:
`Oil & Gas Midstream`). The ETN VXX is filed as `Exchange Traded Fund` (see
[limitations](#known-limitations)). The export has 148 distinct industries. No
classifier change was needed.

**Every rejected provider "ETF" was inspected.** The 29 `NOT_ETF` rows are
CEFs and interval funds filed under `Asset Management` (GUG, PDX, NMAI, RFM,
WDI, …), BDCs (KBDC, MSDL), royalty trusts (CRT, PBT, SBR, SJT, MSB, …), and one
mortgage-finance company. The 73 `UNRESOLVED_SECURITY_TYPE` rows are
exchange-listed notes and baby bonds, OTC grantor trusts and foreign UCITS
lines (17 on `US_PINK`), Sprott physical trusts (PHYS, PSLV, CEF, SPPP), and
about 25 genuine ETFs that the Finviz export does not carry (newly listed or
delisted). The last group is excluded by the designed fail-closed rule
(positive evidence required), not misplaced. Two Finviz ETFs (ATTR, CBLS) are
absent from the provider catalog. No provider fallback is shown as a
classification.

**UI** (in-app browser against the local API and Vite):

- ETF Overview: 5,738 results. Finviz's export had refreshed since the audit.
- Search `EQIX` in ETFs: "No instruments match this search", 0 results. In
  US Equities it appears once, category `REIT`.
- `SPY` (SPDR S&P 500 ETF) is in ETFs. All eight controls are present in
  ETFs, and none of them is in US Equities (API exact-symbol check).
- Saved screen "S13 ETF acceptance" (ETFs, `Exchange = US_NYSE`, Performance
  view): reloaded from the menu with its filter chip and columns restored.
  It showed 832 of 5,738 results; the NYSE-listed EQIX and WY are simply
  absent. No migration ran.
- ETF News: live (Finviz Elite 13, RSS 7), and every matched instrument is an
  ETF (UNG, USO, IBIT, GLD, DIA, …).
- ETF Congress: `NO_DISCLOSURES` over 60 and 90 days, with coverage "0 match
  this universe · 677 name other tickers · 85 have no ticker". Every one of the
  35 distinct tickers outside US Equities in the window was checked: foreign
  issuers and ADRs (`geo_usa` excludes them), Litecoin, and Alphabet depositary
  shares. None is an ETF. The 24 ETF matches S12 showed were the REIT/CEF
  contamination S13 removed. In US Equities, Kevin Hern's AIO trades now
  match.

**Defect found and fixed:** the audit printed its report and then never exited.
The OpenD quote context runs non-daemon SDK threads, and the command did not
close the shared transport. The live entry point now closes it in a `finally`
block (`0213799d`), with a regression test in `AuditCommandTests`.

## Known limitations

- **ETNs are not separated.** Neither the Moomoo row nor the Finviz industry
  distinguishes an exchange-traded note from an ETF. An ETN that Finviz files
  under `Exchange Traded Fund` is admitted. Separating ETNs needs a
  fund-structure field that no integrated source currently provides.
- **BDCs** are recorded as `LISTED_EQUITY`, because Finviz files them under
  `Asset Management`, and they cannot be told apart from asset managers.
  Their placement (US Equities) is still correct.
- **The reference is Finviz.** ETF admission depends on Finviz Elite. Without
  it the ETF universe is fail-closed, not degraded to provider-only
  membership. The last good classification is kept across failed refreshes
  while the process lives.
- **Finviz industry names** are matched as documented above (`Exchange Traded
  Fund`, `REIT - …`, `Closed-End Fund - …`, `Shell Companies`), and were
  verified live on 2026-09-29. If Finviz renames them later, a different REIT
  or CEF spelling still cannot admit a REIT or CEF to ETFs; such rows are
  rejected as `NOT_ETF`. A different `Exchange Traded Fund` spelling would empty
  the ETF universe (fail-closed) and leave ETFs in US Equities. The audit
  reports that as the finding `REFERENCE_HAS_NO_ETF_INDUSTRY` and exits 1.
- **ETFs absent from the Finviz export are excluded.** About 25 genuine
  provider-typed ETFs (new or delisted listings) were rejected as
  `UNRESOLVED_SECURITY_TYPE` on 2026-09-29. That is the fail-closed rule
  working as designed; no fallback admits them.
