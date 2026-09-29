# Main Screener S15 — Futures CFTC positioning coverage

S15 makes sure every Futures root in the Main Screener has an explicit, evidence-backed
CFTC Commitments of Traders (COT) coverage decision. It also corrects the S12 mapping
defect and shows the decisions in the existing Positioning view, the Institutional &
Whale panel, and the Quick Preview. It adds no universe, panel, score, or analytics.

S15 is complete when every root is **classified**, not when every root is mapped. A root
without an official COT market is recorded as such and is never forced onto a nearby
market.

## Baseline (S12 / S14)

- S12 configured 33 root → market mappings. The live OpenD Futures catalog listed
  178 roots, and only **32 of 178** were mapped
  ([S12 acceptance](SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md), repeated in
  [S14](SCREENER_S14_DISCLOSURE_COVERAGE.md)). The other 146 roots appeared only as a list
  of unmapped roots, with no reason given.
- **The METH defect.** S12 keyed Micro Ether as `MET`, which is the CME product code. The
  provider root is `METH`, so the configured mapping never matched a live root. That is
  why S12 had 33 configured mappings but only 32 mapped live roots.

Both historical S12/S14 records are kept as they were, with a note pointing here.

## Official sources audited

All data comes from CFTC Public Reporting (`publicreporting.cftc.gov`, Socrata), and
all of it is public:

| Report | Dataset | Use in S15 |
|--------|---------|------------|
| Traders in Financial Futures, futures only | `gpe5-46if` | primary report for financial futures |
| Disaggregated, futures only | `72hh-3qpy` | primary report for physical commodities |
| Legacy, futures only | `6dca-aqww` | mapping reference only (market codes, names, exchanges) |

The audit covered the latest release (report of 2026-09-22, released 2026-09-25
15:30 ET) and every market code reported since 2012 in all three reports. The
registry was verified on 2026-09-29 against the Moomoo OpenD Futures catalog observed
that day: 178 roots, one dated lead contract per root.

## Root accounting (2026-09-29, 178 roots)

| Decision | Status · reason | Roots |
|----------|-----------------|------:|
| Mapped to one CFTC market | `MAPPED` | **67** |
| Single-stock future, no COT market | `NO_CFTC_REPORT · PRODUCT_NOT_COVERED` | **77** |
| No CFTC market for this contract | `NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND` | **33** |
| Ambiguous (Mini VIX) | `AMBIGUOUS · AMBIGUOUS_MAPPING` | **1** |
| Unsupported / missing reference data | — | 0 |
| **Unclassified** | `UNCLASSIFIED · ROOT_NOT_IN_COVERAGE_REGISTRY` | **0** |

67 of 178 is 37.6% mapped. This is accounting, not a quality score. No coverage, whale,
or positioning score exists.

### Mapped roots (67)

Each root maps to exactly one CFTC contract market code in exactly one report family.
No code is used twice, micro contracts are separate CFTC markets (never merged into the
full-size parent), and no mapped market appears in both TFF and Disaggregated.

| Root | Code | Report | CFTC market | Basis |
|------|------|--------|-------------|-------|
| ES | `13874A` | TFF | E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| MES | `13874U` | TFF | MICRO E-MINI S&P 500 INDEX - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| EMD | `33874A` | TFF | E-MINI S&P 400 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| NQ | `209742` | TFF | NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| MNQ | `209747` | TFF | MICRO E-MINI NASDAQ-100 INDEX - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| RTY | `239742` | TFF | RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| M2K | `239747` | TFF | MICRO E-MINI RUSSELL 2000 INDX - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| YM | `124603` | TFF | DJIA x $5 - CHICAGO BOARD OF TRADE (formerly DOW JONES INDUSTRIAL AVG- x $5 - CHICAGO BOARD OF TRADE) | EXCHANGE_PLUS_PRODUCT |
| MYM | `124608` | TFF | MICRO E-MINI DJIA (x$0.5) - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| NIY | `240743` | TFF | NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| NKD | `240741` | TFF | NIKKEI STOCK AVERAGE - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| ZN | `043602` | TFF | UST 10Y NOTE - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZB | `020601` | TFF | UST BOND - CHICAGO BOARD OF TRADE (formerly U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE) | EXCHANGE_PLUS_PRODUCT |
| ZF | `044601` | TFF | UST 5Y NOTE - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZT | `042601` | TFF | UST 2Y NOTE - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| UB | `020604` | TFF | ULTRA UST BOND - CHICAGO BOARD OF TRADE (formerly ULTRA U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE) | EXCHANGE_PLUS_PRODUCT |
| TN | `043607` | TFF | ULTRA UST 10Y - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| 10Y | `04360Y` | TFF | MICRO 10 YEAR YIELD - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| SR3 | `134741` | TFF | SOFR-3M - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| 6E | `099741` | TFF | EURO FX - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6J | `097741` | TFF | JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6B | `096742` | TFF | BRITISH POUND - CHICAGO MERCANTILE EXCHANGE (formerly BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE) | EXCHANGE_PLUS_PRODUCT |
| 6A | `232741` | TFF | AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6C | `090741` | TFF | CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6L | `102741` | TFF | BRAZILIAN REAL - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6M | `095741` | TFF | MEXICAN PESO - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6N | `112741` | TFF | NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6S | `092741` | TFF | SWISS FRANC - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| 6Z | `122741` | TFF | SO AFRICAN RAND - CHICAGO MERCANTILE EXCHANGE (formerly SOUTH AFRICAN RAND - CHICAGO MERCANTILE EXCHANGE) | EXCHANGE_PLUS_PRODUCT |
| RP | `299741` | TFF | EURO FX/BRITISH POUND XRATE - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| RY | `399741` | TFF | EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| VX | `1170E1` | TFF | VIX FUTURES - CBOE FUTURES EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| BTC | `133741` | TFF | BITCOIN - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| MBT | `133742` | TFF | MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| ETH | `146021` | TFF | ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| METH | `146022` | TFF | MICRO ETHER - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| SOL | `177741` | TFF | SOL - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| MSL | `177742` | TFF | MICRO SOL - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| XRP | `176740` | TFF | XRP - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| MXP | `176741` | TFF | MICRO XRP - CHICAGO MERCANTILE EXCHANGE | CURATED_OFFICIAL_ALIAS |
| CL | `067651` | DISAGGREGATED | WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| BZ | `06765T` | DISAGGREGATED | BRENT LAST DAY - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| NG | `023651` | DISAGGREGATED | NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| QG | `023655` | DISAGGREGATED | E-MINI NATURAL GAS - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| HO | `022651` | DISAGGREGATED | NY HARBOR ULSD - NEW YORK MERCANTILE EXCHANGE (formerly NY HARBOR USLD - NEW YORK MERCANTILE EXCHANGE) | CURATED_OFFICIAL_ALIAS |
| RB | `111659` | DISAGGREGATED | GASOLINE RBOB - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| GC | `088691` | DISAGGREGATED | GOLD - COMMODITY EXCHANGE INC. | EXCHANGE_PLUS_PRODUCT |
| MGC | `088695` | DISAGGREGATED | MICRO GOLD - COMMODITY EXCHANGE INC. | EXCHANGE_PLUS_PRODUCT |
| SI | `084691` | DISAGGREGATED | SILVER - COMMODITY EXCHANGE INC. | EXCHANGE_PLUS_PRODUCT |
| SIL | `084694` | DISAGGREGATED | MICRO SILVER - COMMODITY EXCHANGE INC. | EXCHANGE_PLUS_PRODUCT |
| HG | `085692` | DISAGGREGATED | COPPER- #1 - COMMODITY EXCHANGE INC. (formerly COPPER-GRADE #1 - COMMODITY EXCHANGE INC.) | EXCHANGE_PLUS_PRODUCT |
| MHG | `085699` | DISAGGREGATED | MICRO COPPER - COMMODITY EXCHANGE INC. | EXCHANGE_PLUS_PRODUCT |
| PA | `075651` | DISAGGREGATED | PALLADIUM - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| PL | `076651` | DISAGGREGATED | PLATINUM - NEW YORK MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| ALI | `191691` | DISAGGREGATED | ALUMINUM - COMMODITY EXCHANGE INC. | EXCHANGE_PLUS_PRODUCT |
| ZC | `002602` | DISAGGREGATED | CORN - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZS | `005602` | DISAGGREGATED | SOYBEANS - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| XK | `005603` | DISAGGREGATED | MINI SOYBEANS - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZW | `001602` | DISAGGREGATED | WHEAT-SRW - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| KE | `001612` | DISAGGREGATED | WHEAT-HRW - CHICAGO BOARD OF TRADE (formerly WHEAT - KANSAS CITY BOARD OF TRADE) | CURATED_OFFICIAL_ALIAS |
| ZL | `007601` | DISAGGREGATED | SOYBEAN OIL - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZM | `026603` | DISAGGREGATED | SOYBEAN MEAL - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZO | `004603` | DISAGGREGATED | OATS - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| ZR | `039601` | DISAGGREGATED | ROUGH RICE - CHICAGO BOARD OF TRADE | EXCHANGE_PLUS_PRODUCT |
| LE | `057642` | DISAGGREGATED | LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| GF | `061641` | DISAGGREGATED | FEEDER CATTLE - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |
| HE | `054642` | DISAGGREGATED | LEAN HOGS - CHICAGO MERCANTILE EXCHANGE | EXCHANGE_PLUS_PRODUCT |

### Unmapped roots (other than single-stock futures)

| Root | Decision | Evidence |
|------|----------|----------|
| 1OZ | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No 1-ounce gold market on CME Group. The similarly named GOLD -1 TROY OUNCE is a Coinbase Derivatives market (a different exchange) and is rejected. Candidate `088LM1`. |
| 2YY | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports MICRO 10 YEAR YIELD only; there is no 2-year yield market. |
| 5YY | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports MICRO 10 YEAR YIELD only; there is no 5-year yield market. |
| 30Y | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports MICRO 10 YEAR YIELD only; there is no 30-year yield market. |
| M6A | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports the full-size AUSTRALIAN DOLLAR market only; there is no micro market, and micro positions are never merged into the parent. |
| M6B | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports the full-size BRITISH POUND market only; there is no micro market, and micro positions are never merged into the parent. |
| M6E | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports the full-size EURO FX market only; there is no micro market, and micro positions are never merged into the parent. |
| MCD | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports the full-size CANADIAN DOLLAR market only; there is no micro market, and micro positions are never merged into the parent. |
| MJY | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports the full-size JAPANESE YEN market only; there is no micro market, and micro positions are never merged into the parent. |
| MSF | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | CFTC reports the full-size SWISS FRANC market only; there is no micro market, and micro positions are never merged into the parent. |
| MIR | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No Indian rupee market in any COT report. |
| SIR | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No Indian rupee market in any COT report. |
| PJY | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No British pound / Japanese yen cross-rate market; CFTC reports only the EUR/GBP and EUR/JPY cross rates. |
| MCL | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro WTI market; WTI-PHYSICAL is the full-size contract and is never used for the micro. |
| QM | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No E-mini crude oil market; WTI-PHYSICAL is the full-size contract. |
| MNG | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro Henry Hub market; E-MINI NATURAL GAS is the QG contract, not this one. |
| QC | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No E-mini copper market; COPPER- #1 is the full-size contract. |
| QI | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No E-mini silver market; SILVER is the full-size contract. |
| QO | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No E-mini gold market; GOLD is the full-size contract. |
| SIC | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No 100-ounce silver market; SILVER (5,000 oz) and MICRO SILVER (1,000 oz) are other contracts. |
| SGU | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No Shanghai gold market in any COT report. |
| MNI | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro Nikkei market; CFTC reports the full-size yen- and dollar-denominated Nikkei only. |
| MNK | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro Nikkei market; CFTC reports the full-size yen- and dollar-denominated Nikkei only. |
| TPD | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No TOPIX market in any COT report. |
| MTN | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro Ultra 10-year market; ULTRA UST 10Y is the full-size contract. |
| MWN | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro Ultra bond market; ULTRA UST BOND is the full-size contract. |
| MZC | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro corn market; CORN is the full-size contract. |
| MZL | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro soybean oil market; SOYBEAN OIL is the full-size contract. |
| MZM | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro soybean meal market; SOYBEAN MEAL is the full-size contract. |
| MZS | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro soybean market; SOYBEANS and MINI SOYBEANS are other contracts. |
| MZW | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No micro wheat market; WHEAT-SRW is the full-size contract. |
| XC | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No mini-sized corn market; MINI SOYBEANS is the only mini grain market CFTC reports. |
| XW | NO_CFTC_REPORT · NO_CFTC_MARKET_FOUND | No mini-sized wheat market; MINI SOYBEANS is the only mini grain market CFTC reports. |
| VXM | AMBIGUOUS · AMBIGUOUS_MAPPING | CFTC publishes one VIX FUTURES market; its identity does not state whether Mini VIX positions are included, so it is not shown as Mini VIX positioning. Candidate `1170E1`. |

### Single-stock futures (77)

No COT report (Legacy, TFF, or Disaggregated, 2012 onward) contains a single-stock
market. These roots are listed by name, so a new stock root must be decided explicitly
and is never inferred from how its symbol is spelled. S15 does not map them to the
underlying stock, 13F, insider data, or any equity proxy. Other Screener intelligence
layers cover the company separately.

`SAAPL`, `SABBV`, `SADBE`, `SAMAT`, `SAMD0`, `SAMGN`, `SAMZN`, `SAVGO`, `SBA00`, `SBAC0`, `SBKNG`, `SBRKB`, `SCAT0`, `SCMCS`, `SCOP0`, `SCOST`, `SCRM0`, `SCSCO`, `SCVX0`, `SDIS0`, `SGOOG`, `SHD00`, `SIBM0`, `SINTC`, `SJNJ0`, `SJPM0`, `SKO00`, `SLLY0`, `SLMT0`, `SMA00`, `SMCD0`, `SMETA`, `SMRK0`, `SMSFT`, `SMU00`, `SNEM0`, `SNFLX`, `SNVDA`, `SORCL`, `SPANW`, `SPEP0`, `SPFE0`, `SPG00`, `SPLD0`, `SPLTR`, `SQCOM`, `SSBUX`, `SSPCX`, `STSLA`, `STXN0`, `SUNH0`, `SV000`, `SVZ00`, `SWMT0`, `SXOM0`, `XAAPL`, `XAMD0`, `XAMZN`, `XAVGO`, `XBA00`, `XBAC0`, `XCSCO`, `XGOOG`, `XINTC`, `XJPM0`, `XMETA`, `XMSFT`, `XMU00`, `XNEM0`, `XNFLX`, `XNVDA`, `XPFE0`, `XPLTR`, `XSPCX`, `XTSLA`, `XWMT0`, `XXOM0`

### VXM (Mini VIX)

The CFTC publishes a single `VIX FUTURES - CBOE FUTURES EXCHANGE` market (`1170E1`). Its
official identity does not say whether Mini VIX positions are included, so VXM stays
`AMBIGUOUS` with `1170E1` recorded as the candidate. It is never shown as VIX
positioning. It will change only if an official source establishes the aggregation.

## Mapping evidence

- **Basis** (`cftc.screener_positioning.MappingBasis`):
  - `EXCHANGE_PLUS_PRODUCT` (confidence `EXACT`): the provider venue is the CFTC
    market's exchange, and the product is the same contract.
  - `CURATED_OFFICIAL_ALIAS` (confidence `SUPPORTED_ALIAS`): the provider gives no venue
    (CME crypto, Nikkei, SOFR), or the product has a different official name (NYMEX `HO`
    is NY Harbor ULSD, `KE` is HRW wheat). Every such mapping carries a written note.
- **No name matching.** The XA-03 / Workspace `CotProductMapper` and its fuzzy
  `NAME_PATTERNS` belong to a different lane and are not used here. The Screener
  registry is keyed by root and CFTC code.
- **Exchange check.** The CFTC exchange (the suffix of the official market name) maps to
  a provider venue (`CHICAGO MERCANTILE EXCHANGE → US_CME`, `CHICAGO BOARD OF TRADE →
  US_CBOT`, `NEW YORK MERCANTILE EXCHANGE → US_NYMEX`, `COMMODITY EXCHANGE INC. →
  US_COMEX`, `CBOE FUTURES EXCHANGE → US_CBOE`). If a mapped root's provider venue
  contradicts its CFTC exchange, the root becomes `AMBIGUOUS · EXCHANGE_MISMATCH`: it is
  not shown as positioning, the view turns `PARTIAL`, and the audit fails. A root with
  no provider venue (93 of 178 on 2026-09-29) has nothing to contradict. On 2026-09-29
  there were 0 mismatches.
- **Identity follows the code, not the name.** Market descriptions change while the
  CFTC code stays the same. Code `001612` was published as `WHEAT - KANSAS CITY BOARD OF
  TRADE` and is now `WHEAT-HRW - CHICAGO BOARD OF TRADE`. Former official names are
  recorded per market (`former_names`), and history is shown as it was published. An
  unknown new name is flagged `MARKET_NAME_DIFFERS_FROM_REFERENCE` but stays mapped by
  code. A difference in whitespace alone is not a rename: the live `MICRO ETHER` row
  carries a double space.
- **Root, not contract.** The key is the IMP root. A lead-contract roll (for example
  ESZ26 → ESH27) keeps the same market (regression-tested).

## Report families

- Financial futures (equity indices, rates, FX, VIX, crypto) use **Traders in Financial
  Futures**: Dealer / intermediary, Asset manager / institutional, Leveraged funds,
  Other reportables, Non-reportables.
- Physical commodities (energy, metals, agriculture, livestock) use **Disaggregated**:
  Producer / merchant / processor / user, Swap dealers, Managed money, Other
  reportables, Non-reportables.
- The two category sets are official and different, and they are never mapped onto each
  other (Asset manager is not Managed money). The UI labels each report by its official
  name.
- **Legacy** (commercial / non-commercial) is never the primary report in the Screener.
  Every mapped market is published in TFF or Disaggregated, which separate the categories
  Legacy merges. Legacy was used only as mapping reference (`REPORT_SELECTION_POLICY`).

## Positioning semantics

| Field | Class | Rule |
|-------|-------|------|
| long, short, spreading | OBSERVED | as published; spreading is shown only where the report has a spreading column (TFF non-reportables and Disaggregated producer/merchant have none: `—`) |
| weekly change long / short / spreading, OI change | OBSERVED | the CFTC's own `change_in_*` columns |
| net | DERIVED | long − short; `null` if either side is missing, never long − 0 |
| net change | DERIVED | published change long − published change short |
| % of OI long / short | DERIVED | category ÷ total open interest of the same report × 100; `null` if the value or OI is missing **or OI is 0** (no division by zero, no 0 substituted) |

Zero is not the same as missing: a published `0` is shown as `0`, and a missing column is
shown as `—`. Unmapped roots carry no position fields at all, so they can never be shown
as "0 positions".

### Data quality

- **Duplicates.** Rows for one (market code, report date) are ordered by the Socrata row
  id, so the same inputs always resolve to the same row. Identical duplicates →
  `DUPLICATE_ROW_IGNORED`. Conflicting duplicates → `quality_state:
  CONFLICTING_DUPLICATE_ROWS`: categories and OI are withheld, and the panel section is
  `UNAVAILABLE`.
- **Known market, not in the latest release.** The CFTC omits a market from a week's
  report when it falls below the reporting threshold. That is not the same as "no CFTC
  market":
  - rows in the 35-day window, but not the newest → the newest report is shown, flagged
    `KNOWN_MARKET_NOT_IN_LATEST_RELEASE` (live: MYM as of 2026-09-15, ZO as of
    2026-09-01);
  - no rows in the window → `NO_DISCLOSURES · KNOWN_MARKET_NOT_IN_RECENT_RELEASES`, and
    the view lists the root under `mapped_without_report` (live: ALI, MHG, MXP, NKD, QG,
    SIL; their last reports were 2026-06-09, 2026-05-12, 2025-12-23, 2026-03-03,
    2024-08-27, and 2026-05-26).

## Point in time and release schedule

- `report_date` is the Tuesday the positions are as of. `publication_time` is the
  official release from the canonical `cftc.release_schedule` (normally Friday 15:30 ET,
  later for holidays; `publication_basis` says `CFTC_OFFICIAL_SCHEDULE` or `…_DELAYED`).
  `available_at` equals the release time.
- A report is visible only from its release time, both historically and now. There is
  no Tuesday lookahead: on the Thursday before a Friday release, the prior week's report
  is shown.
- Holiday delay is exercised in tests: positions of 2026-11-24 (Thanksgiving week) are
  not visible on Friday 2026-11-27 and become visible on Monday 2026-11-30 at 15:30 ET.
- No surface labels COT data real-time or live. It is a weekly publication.

## Service and UI

Everything is wired into the existing S12 service (`ui_api/screener_participants.py`);
no new service, endpoint, panel, or Preview tab was added.

- **Positioning view** (`/screener/participants/positioning`, Futures):
  - a coverage line built from `coverage.breakdown` (counts come from the runtime
    catalog, not from fixed prose);
  - TFF and Disaggregated groups, one block per mapped root: root, market, as-of,
    release, OI, contract, CFTC code, mapping basis, published OI change, quality notes,
    and the full category table (Long, Short, Spreading, weekly change L/S, Net
    (derived), Net chg (derived), % OI L/S (derived), Traders L/S);
  - the known markets with no recent report;
  - "Roots without CFTC positioning", grouped by reason, with root, contract, venue,
    and explanation. Ambiguous, mismatched, and unclassified groups are open by default.
  - The view is `PARTIAL` only for an unclassified root or an exchange mismatch. A
    decided root without a market is not partial data.
- **Institutional & Whale panel** (Futures section `futures_positioning`): CFTC market
  (name, code, report, as of, released) → positions & weekly change → context (open
  interest, derived net, % OI methods) → provenance (basis, confidence, CFTC exchange ↔
  provider venue, coverage state, former names, release basis, source). An unmapped root
  shows "CFTC positioning unavailable · <label>. <explanation>".
- **Quick Preview:** a compact line (report, as of, released) and the categories each
  report is read for (TFF: Asset manager, Leveraged funds; Disaggregated:
  Producer/merchant, Managed money), long / short / derived net. Unmapped roots show the
  same one-line explanation. Responses stay identity-guarded: after a mapped → unmapped
  → mapped selection, only the last root renders (regression-tested).

## Audit tool

`tools/screener/cftc_coverage_audit.py` reads the Futures catalog through the canonical
Screener query path (or a saved `--catalog` root list) and prints the counts for each
decision plus Unclassified. Options:

- `--detail`: one line per root;
- `--verify-cftc`: the latest public report of every mapped market, with flags;
- `--save-catalog`: writes root, venue, and lead symbol only;
- `--json`.

Exit status: 0 clean; 1 if any root is `UNCLASSIFIED`, an exchange mismatch exists, a
root is listed twice, CFTC rows conflict, or a registry invariant fails (duplicate code,
root both mapped and unmapped, unknown exchange, unsupported report); 2 if the catalog
did not load. A root the provider adds later therefore fails the audit until someone
records a decision for it, which is intentional governance.

```powershell
python tools/screener/cftc_coverage_audit.py --detail --verify-cftc
```

## Live acceptance (owner workstation, 2026-09-29)

Real Moomoo OpenD and real CFTC Public Reporting:

- Audit: 178 roots · 67 mapped · 77 single-stock · 33 no market · 1 ambiguous ·
  0 unclassified; exit 0.
- `--verify-cftc`: 61 of 67 mapped markets have a public report in the window: 59 in the
  latest release, plus MYM and ZO flagged `KNOWN_MARKET_NOT_IN_LATEST_RELEASE`. The other
  six are listed above.
- Latest release: positions as of **2026-09-22**, released **2026-09-25 19:30 UTC**
  (`CFTC_OFFICIAL_SCHEDULE`).
- Service (`ScreenerParticipantService`, live gates): view `PUBLICATION_CURRENT`.
  Representative mapped roots:

  | Family | Root | Report | Categories |
  |--------|------|--------|------------|
  | equity index | ES | TFF | Dealer / Asset manager / Leveraged funds… |
  | rates | ZN | TFF | Dealer / Asset manager / Leveraged funds… |
  | FX | 6E | TFF | Dealer / Asset manager / Leveraged funds… |
  | crypto | BTC, METH | TFF | Dealer / Asset manager / Leveraged funds… |
  | energy | CL | Disaggregated | Producer/merchant / Swap dealers / Managed money… |
  | metals | GC | Disaggregated | Producer/merchant / Swap dealers / Managed money… |
  | agriculture | ZC, KE (renamed market) | Disaggregated | Producer/merchant / Swap dealers / Managed money… |
  | livestock | LE | Disaggregated | Producer/merchant / Swap dealers / Managed money… |

  Unmapped roots checked: SNVDA (`PRODUCT_NOT_COVERED`), M6E and 2YY
  (`NO_CFTC_MARKET_FOUND`), VXM (`AMBIGUOUS_MAPPING`). QG
  (`KNOWN_MARKET_NOT_IN_RECENT_RELEASES`) is still mapped. No payload contains
  "realtime" or "live".

## Performance (local, 2026-09-29)

| Measurement | Result |
|-------------|--------|
| Audit: live catalog read / classify 178 roots | 1.29 s / 0.6 ms |
| `--verify-cftc` (two dataset queries) | 1.45 s |
| Positioning view, cold (first catalog build + 2 CFTC queries, in process) | 7.3–9.4 s |
| Positioning view, warm | 6 ms |
| Institutional & Whale panel, cold on a fresh service | 7.8 s (same catalog + CFTC load) |
| Panel / Preview, mapped or unmapped, warm | 0.1–0.7 ms |

The reference lookup is static (module dictionaries). There is no per-row remote call:
the CFTC is queried once per report family per 3-hour TTL for all mapped codes, as in
S12. In the running server, cold loads happen off the request thread, and a request
returns `PENDING` after the S12 6-second wait.

## Tests

| Suite | Tests | Result |
|-------|------:|--------|
| `tests/cftc/test_s15_cftc_coverage.py` (new): root accounting on the 178-root catalog fixture, 67-root reference, METH, VXM, single-stock, no-market, exchange mismatch, rename by code, whitespace, absent from latest release, deterministic and conflicting duplicates, new unknown root fails the audit, TFF vs Disaggregated categories and labels, values (positive, zero vs missing, negative change, spreading, derived net, OI ratio, zero and missing OI), PIT (Thursday before Friday release, holiday-delayed Monday) | 25 | pass |
| `tests/platform/test_screener_s15.py` (new): view coverage and explanations, full 178-root view, unclassified → PARTIAL, exchange mismatch, panel mapped / unmapped / known-market-no-report / conflicting rows, compact Preview, rapid A → B → C, lead-contract roll | 12 | pass |
| `ui/.../ParticipantsS15.test.tsx` (new): panel sections and columns, derived labels, release clock, TFF vs Disaggregated, three unmapped states, VXM, known-market state, flags, Preview categories, rapid root switching, coverage header from payload, grouped unmapped roots, full view | 13 | pass |
| Screener platform S1–S15 (incl. S12, S13, S14, S14 PIT) | 412 | pass |
| CFTC canonical (`test_cftc_cot`, `test_s12_screener_positioning`, S15) | 53 (+ XA-03 31, `live_cftc` 2 skipped offline) | pass |
| UI full (`npm test`) | 1,176 in 156 files | pass |
| UI typecheck, build, bundle budget | — | pass (initial 201.39 KiB gzip) |
| `imp.py lint`, `imp.py format` | — | pass |
| isolated-APPDATA `validate changed` | 2,586 in 13 suites, 8 skipped | pass (0 failures, 0 errors, 240 s) |

The S12 UI suite passes unchanged: an S12-shaped payload still renders, because every S15
field is optional in the schema.

## Known limitations

- The registry was verified against the 2026-09-29 catalog and CFTC data. When the
  provider adds a root, the audit reports it as `UNCLASSIFIED` until a decision is
  recorded.
- 93 of 178 roots have no provider venue, so the exchange check cannot run for them.
  Their mappings rest on the recorded CME Group product codes (`CURATED_OFFICIAL_ALIAS`).
- The Screener reads a 35-day CFTC window. A known market that has not reported in that
  window shows "not in recent releases", not its older last report.
- The release schedule is loaded for 2026. A report date outside it uses the S12
  fallback (Tuesday + 3 days, `PUBLICATION_TIME_INFERRED_TUESDAY_PLUS_3`).
- The visual check was through component tests and live payloads. No browser screenshot
  was taken in this session.
