# Main Screener S9 — Bonds / Fixed Income universe

S9 adds the fourth canonical Screener universe, `BONDS` ("Bonds"), inside the
existing architecture: one registry entry, the S6 canonical query and paging,
the shared table, a fixed-income Quick Preview, and one specialist panel,
Rates & Curve. The canonical universe model it belongs to is recorded in
[Screener universe architecture](SCREENER_UNIVERSE_ARCHITECTURE.md). Rows are
outstanding U.S. Treasury marketable securities from official Treasury data;
corporate and agency coverage is reported as unavailable, never invented.
Bonds are reference-only: S9 adds discovery, research, and context, not
execution.

## Architecture

| Layer | Module | Role |
|-------|--------|------|
| Treasury catalog adapter | `fixed_income/treasury_catalog.py` | Fiscal Data auctions + MSPD → typed `TreasurySecurity` |
| Treasury rates adapter | `fixed_income/treasury_rates.py` | daily par nominal/real curves, bill rates; derived spreads, shape, breakevens, tenor matching |
| FRED context adapter | `fixed_income/fred_context.py` | policy, inflation, credit, conditions via the existing `fred` client |
| FINRA adapter | `fixed_income/finra_fixed_income.py` | TRACE capability; credential-gated Treasury aggregates |
| Bond math | `fixed_income/analytics.py` | coupon schedule, price/yield, durations, DV01, bills |
| HTTP | `fixed_income/http.py` | allowlisted hosts, bounded bodies, stable error codes |
| Screener projection | `ui_api/screener_bonds.py` | caching, rows, query execution, Preview, Rates & Curve payloads |

The projection never reads HTTP response syntax; adapters return typed,
provider-neutral records, and React receives only normalized fields validated
by strict Zod schemas (`ui/src/api/screenerBonds.ts`). `MultiUniverseScreener`
routes `BONDS` to the bond service for read, row lookup, quote, and window.
The new `fixed_income` validation suite owns the package and its fixtures.

## Registry spec

`BONDS` in `ui_api/screener_universes.py`: label "Bonds"; admitted XA-01 asset
classes `SOVEREIGN_DEBT`, `BOND` and kinds `SOVEREIGN_SECURITY`, `BOND`;
identity fields `cusip`, `isin`; default sort maturity (the UI sends
ascending); views Overview, Treasuries, Rates & Curve, Custom; session model
`PUBLICATION`; quote capability `NO_STREAMING_QUOTE`; bars `NO_PRICE_HISTORY`;
panels `rates_curve`; data sources Fiscal Data auctions and MSPD, Treasury
daily rates, FRED, and FINRA aggregates; tradability `REFERENCE_ONLY`. The
`Universe` dataclass gained these optional fields with defaults, so existing
universes are unchanged. The UI derives behavior from the spec
(`tradability`, `quote_capability`, `panels`), not from universe-name checks.

## Identity and the execution boundary

- Each Treasury row registers an XA-01 sovereign identity through the
  existing `register_sovereign_security`, keyed by CUSIP only
  (`sovereign_identity_key`). The id is stable across catalog refreshes; if
  descriptive metadata ever conflicts with an earlier registration, the same
  CUSIP-derived id is re-derived rather than registered twice.
- `symbol` carries the CUSIP for the pinned column, labeled
  "Security · CUSIP" and shown with the description (for example
  "U.S. Treasury Note 4.625% Aug 2036"). No ticker is invented.
- A curve tenor ("10Y") is reference context attached to a row, never an
  identity. Treasury ETFs (TLT, IEF, …) stay in the ETF universe and Treasury
  futures (ZT, ZF, ZN, ZB, UB) stay in Futures; tests assert that the three
  identities are distinct.
- Corporate identity uses the existing `register_bond` (CUSIP, then ISIN,
  then issuer + maturity + coupon); tests cover it, although no corporate
  rows exist.
- `SOVEREIGN_SECURITY` and `BOND` remain `REFERENCE_ONLY`. No tradability,
  risk-admission, paper, or execution guard changed. A reference-only row
  never navigates to a Workspace: Enter and double-click open the Quick
  Preview.

## Provider investigation (2026-09-27)

| Source | Access | Use in S9 |
|--------|--------|-----------|
| Fiscal Data `auctions_query` | public JSON API | catalog terms and auction results; 890 auctions of securities maturing on or after today (3.0 MB, ~2.3 s) |
| Fiscal Data MSPD `mspd_table_3_market` | public JSON API | outstanding securities and amounts at the latest month end (2026-08-31: 888 lines, 463 CUSIPs) |
| Treasury daily rates XML (par yield curve, par real yield curve, bill rates) | public structured feed | curve context; bill closing bids by CUSIP |
| TreasuryDirect `TA_WS` / FedInvest | `robots.txt`: `User-agent: * Disallow: /`; FedInvest is a CSRF form | **not used**; Fiscal Data carries the same auction dataset |
| FRED / ALFRED | existing client; needs `FRED_API_KEY` + `IMP_FRED_LIVE=1` | context only; **NOT_CONFIGURED** on this host |
| FINRA Query API `fixedIncomeMarket` | metadata public; data returns 401 without the FINRA OAuth credential | aggregates adapter, credential-gated; **NOT_CONFIGURED** here |
| FINRA per-security TRACE prints | licensed TRACE data product, not in the Query API | **FINRA_TERMS_REQUIRED**; no corporate or agency rows |

home.treasury.gov delays anonymous tool user agents by about 17 s per request
and answers a descriptive user agent in about 0.4 s; the adapter sends
`IMP-FixedIncome/1.0`. Treasury sources are opt-in with `IMP_TREASURY_LIVE=1`,
the same pattern as the other `IMP_*_LIVE` public sources.

## Treasury catalog

- **Kinds** come from provider flags: `cash_management_bill_cmb` → CMB,
  `inflation_index_security` → TIPS, `floating_rate` → FRN, otherwise the
  auction `security_type` (Bill, Note, Bond). No kind is inferred from text.
- **Reconciliation:** auction rows are grouped by CUSIP (with a check-digit
  validated CUSIP). Maturity, kind, base type, and coupon must agree across
  reopenings or the CUSIP is rejected (`CONFLICTING_TERMS`). Exact duplicate
  auctions collapse. Malformed rows are rejected and counted by reason.
- **Terms:** original issue date is the earliest issue; the original term,
  coupon frequency, callable flag, series, and dated date come from the
  original auction. Bills carry no coupon and 0 payments per year. FRNs carry
  their fixed spread and quarterly payments.
- **Outstanding:** a security is outstanding when its original issue date is
  on or before today and its maturity date is after today. This is
  re-evaluated whenever the date changes; announced, not-yet-issued
  securities are counted but not listed. Securities issued after the MSPD
  record date are outstanding by the same rule and have no MSPD amount.
- **MSPD join:** amount outstanding in USD millions (shown in billions) with
  the record-date clock. A CUSIP in MSPD but absent from the auction dataset
  is kept with MSPD terms (frequency from its interest-payment dates).
  An MSPD failure leaves amounts unavailable; the catalog still loads.
- **Remaining maturity:** days = maturity − today; years = days / 365.25;
  buckets are half-open: <1Y, 1-3Y, 3-5Y, 5-7Y, 7-10Y, 10-20Y, 20Y+.
- **TIPS auction prices:** Treasury's `high_price` for TIPS is the
  inflation-adjusted price (unadjusted × index ratio); the unadjusted real
  price is kept separately and labeled.

## Treasury curves and derived context

- Par nominal curve (1M–30Y), par real curve (5Y–30Y), and bill rates are
  read for the current and previous month (six bounded requests, three at a
  time). Each feed fails independently, and a missing tenor is absent, never
  zero.
- `PUBLICATION_CURRENT` when the latest publication is at most 4 calendar
  days old (covers a weekend plus a holiday Monday), otherwise `STALE`.
- **Derived (one publication date, in bp):** 2s10s = 10Y − 2Y, 3m10y =
  10Y − 3M, 5s30s = 30Y − 5Y, 10s30s = 30Y − 10Y.
- **Curve shape:** UPWARD_SLOPING if 3m10y and 2s10s are both ≥ +10 bp,
  INVERTED if both ≤ −10 bp, otherwise FLAT_OR_MIXED. It is a description of
  the publication, never a forecast.
- **Breakevens:** nominal par − real par at the same tenor and date, labeled
  as a par-curve approximation; different dates → unavailable.
- **Reference matching:** the nearest published tenor by remaining maturity
  (ties go to the shorter tenor); nominal curve for bills, notes, and bonds;
  real curve for TIPS; none for FRNs (they reset to the 13-week bill). No
  reference is assigned when maturity lies more than 1 year outside the
  published tenor range (`OUTSIDE_CURVE_RANGE`). Nothing is interpolated.
  The reference is labeled a benchmark, never the security's yield.
- **Bill closing bids:** the bill-rate feed names the CUSIP of each
  on-the-run bill; its closing bid (bank discount and coupon-equivalent)
  attaches to exactly that CUSIP (6 bills on 2026-09-25).

## FRED and FINRA context

FRED supplies the Tier 1 registry series for policy (target upper, effective
fed funds, SOFR), inflation (10Y breakeven), credit (ICE BofA IG and HY OAS,
labeled as licensed indices), and conditions (NFCI). Each value keeps its
observation date and ALFRED `realtime_start`. Credit series are broad context
and are never assigned to a bond. AAA/Baa series are not in the Tier 1
registry and were not added. FINRA security-level trade prints are
`FINRA_TERMS_REQUIRED`; the Treasury-aggregates adapter normalizes the
metadata-documented `treasuryDailyAggregates` fields (aggregates, never
quotes) once credentials and `IMP_FINRA_LIVE=1` are present.

## Query, fields, views, filters

`BONDS` runs through `parse_query` / `order_rows` / `page_payload` unchanged.

| Execution | Fields |
|-----------|--------|
| `CATALOG` (sort + filter) | CUSIP/description, issuer, type, original term, issue, maturity, bucket, TIPS, FRN, callable, coupon, years, days, maturity year, outstanding, last auction date, auction yield, auction real yield, auction discount margin, bid-to-cover |
| `REFERENCE` (display only) | reference tenor, reference par yield, bill closing bid |

`REFERENCE` is a new execution mode: publication context that describes a
benchmark or a subset of rows, so it can never sort or filter the universe.
The auction yield column is the high yield for notes and bonds and the high
investment (coupon-equivalent) rate for bills (`basis` on the field says
which); TIPS real yields are a separate column so real and nominal never sort
together. Search covers CUSIP, description, issuer, type, maturity, term, and
series. Equity, ETF, and futures fields are rejected in a Bonds query
(`FILTER_UNIVERSE_MISMATCH`). There is no price, yield-to-maturity, spread,
rating, credit, or trade-activity field, and therefore no Credit or Activity
view.

Views: Overview (type, coupon, maturity, years, auction yield, last auction,
outstanding), Treasuries (terms, flags, auction results, reference), Rates &
Curve (maturity, bucket, reference tenor and yield, closing bid, auction
yield), and Custom. Missing values render as "—". The footer reports counts
per category ("Treasury 463 · Corporate unavailable · Agency unavailable"),
and an unavailable category never has a count.

Saved screens and URLs reuse the S5/S6 schema: universe, view, filters, sort,
and columns are persisted; curves, auction values, and quotes are not. A
fix made here: a direct link's view for a non-equity universe
(`?universe=BONDS&view=Treasuries`) is now honored once the universe spec
arrives (previously it always opened Overview). The `/screener` route now
defaults a missing `sort` to the universe's own default instead of `volume`.

## Fixed-income math

`fixed_income/analytics.py` (percent rates, prices per 100 par, years):

- Price from yield follows the Treasury formula (31 CFR 356 Appendix B) for
  regular periods, with the fractional first period discounted at simple
  interest. Validated against Treasury's own published results:
  626 of 639 nominal auction prices within 1e-6 (the rest were published to
  3 decimals) and 127 of 130 TIPS unadjusted prices within 1e-6; yield
  inversion within 3.3e-5.
- Accrued interest (actual/actual in period), next coupon, coupons remaining;
  end-of-month rule for month-end maturities.
- Modified duration and DV01 by a ±1 bp central difference of the dirty
  price; Macaulay = modified × (1 + y/f).
- Bills: price = 100 (1 − d·t/360); investment rate with the Treasury simple
  (≤ half year) and quadratic (> half year) forms and a 365/366 basis; this
  reproduces published bill prices exactly and rates within rounding.
  Macaulay duration of a zero equals its time to maturity.
- Fails closed with codes: `FRN_FLOATING_COUPON`, `MISSING_TERMS`, `MATURED`,
  `NON_POSITIVE_PRICE`, `IRREGULAR_FIRST_PERIOD`, `NOT_YET_DATED`,
  `UNSUPPORTED_FREQUENCY`, `YIELD_NOT_BRACKETED`.

Applied in the Preview only where inputs exist: accrued interest and coupon
schedule today (derived from terms), and durations and DV01 at the latest
auction yield on issue-date settlement, labeled "at auction … not a current
market measure" (real terms for TIPS). Current yield to maturity, current
duration, and benchmark spread are unavailable because no permitted
security-level price exists. There is no bond score.

## Quick Preview

For `BONDS`, `QuickPreview` renders `BondQuickPreview`. The header shows the
description, CUSIP, type, issuer, "Reference only", coupon, maturity, and
years; price is "—". Sections: Terms, Market (current price and latest trade
unavailable with reasons; on-the-run bill closing bids), Latest auction
(results by type, TIPS adjusted/unadjusted prices, index ratio, reference
CPI, bidder shares, bid-to-cover labeled as a fact rather than a signal),
Analytics, Rates context (matched reference, change versus the prior
publication, curve shape, spread unavailable), Why it matched, and Sources.
Each section shows its common source once; every value carries a class
badge when not observed and full provenance in its tooltip. No equity field,
Options tab, Squeeze tab, or bar chart appears.

## Rates & Curve panel

One dock panel (`rates_curve`, `GET /screener/rates-curve`) with its own
schema (`screener-rates-curve/1.0.0`). It loads without a selection and
places a selected security when one settles; a response for another selection
is never shown. It contains:

- a maturity → yield SVG chart (square-root maturity axis, yield axis fitted
  to the data) with nominal par, the prior publication (dashed), and real par,
  published points as markers, a selected-security marker at its reference
  point, a legend and direct labels, a hover tooltip, and a hidden data table;
  series colours were validated for CVD separation and contrast on the dark
  surface;
- curve spreads with the shape rule, the selected bond (matched reference,
  closing bid, latest auction yield, spread unavailable and why), real yields
  and breakevens, FRED policy and credit (or NOT_CONFIGURED), FINRA state,
  and compact source clocks.

Capability matrix for Bonds: Rates & Curve supported; Charts unavailable (no
security price history); Order Flow, CVD, and Level 2 unavailable (no
fixed-income trade stream, signed trades, or depth); Futures Context
unavailable (no verified rates-futures relationship); Options and Short
Squeeze not applicable. The launcher lists "Rates & Curve · unavailable" in
the other universes. There is no streaming bond quote, so the UI opens no
quote window and the server answers a window with `NO_STREAMING_BOND_QUOTES`.

## Source clocks and truth states

| Source | Clock | States |
|--------|-------|--------|
| Treasury terms & auctions | event/reference (retrieval time) | CURRENT, DEGRADED (last good), UNAVAILABLE, NOT_CONFIGURED |
| MSPD amounts | monthly publication (record date) | PUBLICATION_CURRENT, UNAVAILABLE |
| Par curves, bill rates | daily publication | PUBLICATION_CURRENT, STALE, UNAVAILABLE |
| FRED | series publication | PUBLICATION_CURRENT, PARTIAL, NOT_CONFIGURED, UNAVAILABLE |
| FINRA TRACE prints | transaction | FINRA_TERMS_REQUIRED |
| FINRA aggregates | daily publication | NOT_CONFIGURED, UNAVAILABLE, PUBLICATION_CURRENT |

The session is `PUBLICATION_BASED`; the US equity 09:30–16:00 clock is never
applied. Row-level reasons include `OUTSIDE_CURVE_RANGE`,
`FRN_INDEXED_TO_13_WEEK_BILL`, `CURVE_UNAVAILABLE`, and
`NO_STREAMING_BOND_QUOTES`. Matured securities leave the universe. Nothing
shows LIVE.

## Caching and rate limits

Catalog: one fetch per 6 h (5 min retry after a failure; the last good
catalog stays visible as DEGRADED), projected once per catalog and date.
Curves: 30 min. FRED and FINRA context: 6 h. No per-row or per-selection
provider request exists; the Preview and panel read the cached sources.
Tests assert one catalog load and one curve load across repeated reads and
every row's Preview.

## Real acceptance (2026-09-27/28, live sources, isolated `APPDATA`)

- Catalog: 463 outstanding — 241 Notes, 112 Bonds, 53 TIPS, 49 Bills,
  8 FRNs, 0 CMBs current; 9 issued after the 2026-08-31 MSPD (no amount);
  6 announced, not yet issued; 0 rejected rows. Paging 200/200/63 returned
  all 463 with no duplicates.
- Representative securities (observations, not hard-coded):

| Type | CUSIP | Terms | Latest auction |
|------|-------|-------|----------------|
| Bill | 912797VN4 | 17-week, issued 2026-06-30, matures 2026-10-27 | 2026-09-24 reopening, investment 3.915%, price 99.700556; closing bid 3.90% / 3.97% CE (2026-09-25) |
| Note | 91282CRF0 | 4.625%, issued 2026-08-17, matures 2036-08-15 | 2026-09-09, high yield 4.834%, price 98.361116 |
| Note | 91282CLM1 | 3.625%, issued 2024-09-30, matures 2031-09-30 | 2024-09-26, high yield 3.668% |
| Bond | 912810UW6 | 5.125%, issued 2026-08-17, matures 2056-08-15 | 2026-09-10, high yield 5.308% |
| Bond | 912810FT0 | 4.50%, issued 2006-02-15, matures 2036-02-15 | 2006-08-10, high yield 5.08% |
| TIPS | 91282CDX6 | 0.125%, issued 2022-01-31, matures 2032-01-15 | 2022-05-19, real 0.232%, unadjusted 98.982175, adjusted 102.6168 |
| TIPS | 912810US5 | 2.375%, issued 2026-02-27, matures 2056-02-15 | 2026-08-20, real 2.973% |
| FRN | 91282CLT6 | issued 2024-10-31, matures 2026-10-31 | 2024-12-24, discount margin 0.14% |
| FRN | 91282CRD5 | spread 0.05%, matures 2028-07-31 | 2026-09-23, discount margin 0.04% |

- Curves: nominal par 2026-09-25 (14 tenors; prior 2026-09-24; month-ago
  2026-08-28), real par 2026-09-25 (5 tenors); 2s10s +36 bp, 3m10y +93 bp,
  5s30s +51 bp, 10s30s +32 bp, UPWARD_SLOPING; 10Y breakeven 2.34%.
- FRED: `NOT_CONFIGURED` (`FRED_API_KEY_MISSING`). FINRA aggregates:
  `NOT_CONFIGURED` (`IMP_FINRA_LIVE_NOT_SET`); a direct unauthenticated probe
  returned 401. TRACE prints: `FINRA_TERMS_REQUIRED`.
- Not configured (`IMP_TREASURY_LIVE` unset): "— results", an explanatory
  message, `NOT_CONFIGURED` health, and no provider request.

## Visual acceptance

Inspected in the live UI at 1920×1080, 2560×1440, and 1100×800: the
populated table, search, direct view links, a Note, an on-the-run Bill, and a
TIPS in Preview, the Rates & Curve panel, and the not-configured state. The
document never exceeded the viewport; the table scrolls inside the grid.
Visual inspection caught and fixed: `Yrs` rounding a 1-day bill to "0" (now
two decimals); coverage listed alphabetically (now Treasury first); a bill's
coupon frequency shown as unavailable instead of "None (discount
instrument)" (a falsy-zero bug); bidder shares printed to 3 decimals; the
curve's y axis forced to 0% (now fitted); repeated per-item provenance (now
once per section); an unavailable category counted as "0"; and a direct view
link ignored for non-equity universes.

## Performance (live, same machine)

| Measure | Result |
|---------|--------|
| First Bonds page, cold (auctions + MSPD + 6 curve feeds) | 5.5–5.7 s |
| First page, warm | 0.049 s; 200 of 463 rows, ≈423 KB |
| Search (`912810`, `tips`, `2033-`) | 6–33 ms |
| Filters (type; years 7–10 + coupon ≥ 4, sorted by coupon) | 5 ms |
| Quick Preview (bond) | 2–7 ms, ≈9–10 KB |
| Rates & Curve | 2 ms, ≈6–7 KB |
| Initial UI bundle | 201.37 KiB gzip (S8 201.36); bond code is in the lazy Screener and Dock chunks |

## Tests

- `tests/fixed_income/test_fixed_income.py` (37): catalog typing, terms,
  bills, reopenings, duplicates, conflicts, malformed rows, matured and
  announced, MSPD-only, MSPD failure, auction failure, paging bound, CUSIP
  check digit, calendar boundaries; curves, bill CUSIP attachment, missing
  tenor, malformed XML, staleness, spreads, shape, breakevens, reference
  matching, per-feed failures, host allowlist; Treasury-published price and
  rate vectors, negative real yield, zero-coupon duration, schedules, failure
  codes; FRED NOT_CONFIGURED, knowledge dates, PARTIAL, redaction; FINRA terms,
  NOT_CONFIGURED, normalization, failure codes, no quote fields.
- `tests/platform/test_screener_s9.py` (38): registry and scope, identity
  (stability, ETF/future/tenor distinctness, corporate CUSIP/ISIN/terms),
  query (default order, search, filters, null-last sorting, pinned pages,
  invalid requests, default sort, date rollover), row truth states, source
  states (not configured, degraded, unavailable, curve failure, caching, no
  quotes, secret-leak audit), Preview by type, no equity concepts,
  capabilities, clocks, Why, Rates & Curve, FRED context, route policy, saved
  screens, and panel layout.
- `ui/src/components/screener/bonds/Bonds.test.tsx` (9): URL restore, columns,
  no quote window, reference columns never sort, search, filters, Preview,
  no Workspace handoff, single panel instance and selection follow,
  Equity → Bonds → Futures → Bonds → ETF switching and back, saved screens,
  not-configured state, formatting, and strict schemas.
- Updated: the S5 and S8 tests that pin the universe set now include
  `BONDS`; the S7 launcher test includes "Rates & Curve · unavailable".

## Validation

Gates on the final tree (`APPDATA` isolated, as in S3–S8, because
`powershell.exe` startup hangs on this host):

| Gate | Result |
|------|--------|
| S9 fixed income (`tests.fixed_income.test_fixed_income`) | 37 passed |
| S1–S9 Screener backend (`tests.platform.test_screener_s1` … `s9`) | 266 passed (S9 38) |
| XA-01 (`tests/xa01`) | 72 passed |
| FRED (`tests/fred`) | 30 passed |
| Screener UI (`npx vitest run src/components/screener`) | 83 passed, 6 files |
| Full UI (`npm test`) | 1,098 passed, 151 files |
| Typecheck / build + bundle budget | exit 0 / exit 0; initial 201.37 KiB gzip |
| Format / lint | exit 0 / exit 0 |
| Validation suite (`tests/validation`) | 209 passed |
| Docs links / `git diff --check` | 273 files OK / clean |
| `python tools/imp.py validate changed` | exit 0 — 5,341 tests, 35 skipped, 0 failures, 0 errors, 240.9 s |

The first `validate changed` run failed in the `validation` suite: the new
`fixed_income` package was not yet classified in the repository-closure
audit (`artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`,
now listed with the other provider domains), and the manifest test pinned 69
offline suites (now 70). Both were registrations the new suite requires, not
behavior changes; the rerun passed.

## Limitations

- Treasury securities only. Corporate, agency, municipal, and securitized
  instruments have no permitted programmatic source; TRACE security prints
  need a licensed FINRA feed.
- No current security-level price, yield to maturity, current duration,
  spread to benchmark, credit rating, or trade activity; auction-basis
  analytics describe the latest auction, which for old securities can be
  years old.
- Curve references are nearest published tenors, not interpolated
  security-matched benchmarks. FRNs have no maturity-matched reference.
- FRED and FINRA context need credentials this host does not have.
- No bond Workspace or execution; bonds remain reference-only.
- A cold first read takes about 5.5 s while the catalog and curves load.
- ISIN is not published in the Treasury datasets used, so Treasury rows carry
  CUSIP only.
