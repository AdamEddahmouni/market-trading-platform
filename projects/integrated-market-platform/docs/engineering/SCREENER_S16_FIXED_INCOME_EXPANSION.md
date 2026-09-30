# Main Screener S16 — Fixed income coverage & market data expansion

Status: **implemented, ready for owner review** (2026-09-29). Not merged.
Branch `codex/screener-s16-fixed-income-expansion` from main `764b5755` (PR #437 merged).

S16 broadens the one BONDS universe beyond Treasuries. It adds **Corporate, Agency,
Municipal, and Securitized** categories from the SEC's Form N-PORT data sets. It also
adds Treasury market observations (TIPS index ratios, FRN indexes, buyback and Fed
purchase prices) with dated analytics derived from them, NY Fed reference rates and
SOMA holdings, credential-gated FINRA breadth, and opt-in OpenFIGI enrichment. There
is no new universe, no new query engine, and no parallel bond stack. Fund-held rows go
through the S6 canonical query (`apply_filters` / `order_rows` / `page_payload`). The
N-PORT catalog reuses the S14 managed-refresh lifecycle by subclassing it.

**What S16 does not do:** it shows no current price, current yield, or current spread
for any bond. None of the sources IMP may use supplies them:

- TreasuryDirect/FedInvest disallow automated access;
- TRACE security prints need a licensed feed;
- MSRB EMMA data is not licensed for redistribution;
- NRSRO ratings need a licence.

Each of these is shown as UNAVAILABLE or TERMS_REQUIRED with its reason. None is
scraped or approximated. Every value carries a class: OBSERVED, DERIVED, REFERENCE,
STALE, or UNAVAILABLE. Every dated value carries its own date.

## Source and licence matrix (live probes, 2026-09-29)

| Source | Categories | What IMP uses | Access / credential | Terms | Clock | State in IMP |
|--------|-----------|---------------|---------------------|-------|-------|--------------|
| SEC Form N-PORT data sets (`<yyyy>q<n>_nport.zip`) | Corporate, Agency, Municipal, Securitized (fund-held) | CUSIP, reported ISIN, issuer, LEI, title, maturity, coupon type, annualized rate, default / PIK / convertible flags, principal balance, fair value | public bulk ZIP; `SEC_USER_AGENT` for download only | SEC Fair Access | report date (effective), filing date (public, about 60 days later) | **CURRENT_AS_FILED** reference catalog; never prices |
| Treasury Fiscal Data `tips_cpi_data_detail` | TIPS | index ratio and reference CPI per CUSIP per day | public API | public | daily (published in advance) | OBSERVED |
| Treasury Fiscal Data `frn_daily_indexes` | FRN | daily index, spread, accrual rate, accrued per 100 | public API | public | daily | OBSERVED |
| Treasury Fiscal Data `buybacks_operations` + `buybacks_security_details` | Treasury notes, bonds, TIPS | weighted-average accepted price per CUSIP, par accepted, settlement | public API | public | operation date | OBSERVED, dated |
| NY Fed Markets API `tsy/all/results/details` | Treasury bills and coupons (Desk outright purchases) | weighted-average accepted quote per CUSIP: a **discount rate for bills**, a price for coupons | public API | NY Fed terms of use | operation date | OBSERVED, dated |
| NY Fed Markets API `rates/all/latest` | context | SOFR, EFFR (with target range), OBFR, TGCR, BGCR, volumes, 1st/99th percentiles | public API | NY Fed terms of use | daily | OBSERVED |
| NY Fed Markets API `soma/{tsy,agency}` | Treasury, agency debt, MBS, CMBS | par held, percent of issue outstanding (Treasuries) | public API | NY Fed terms of use | weekly (as of 2026-09-23) | OBSERVED holdings fact |
| OpenFIGI `/v3/mapping` | any | FIGI, market sector, security type | public API; 25 req/min keyless | OpenFIGI terms | reference | NOT_CONFIGURED unless `IMP_OPENFIGI_LIVE=1`; one lookup per opened preview, cached, rate-limited to 20/min |
| FINRA Query API `fixedIncomeMarket` breadth (corporate, agency) | Corporate, Agency | advances / declines / unchanged counts | OAuth `FINRA_CLIENT_ID/SECRET` + `IMP_FINRA_LIVE=1` | FINRA | trade date | NOT_CONFIGURED here (no credentials); counts, never prices |
| FINRA TRACE security-level prints | Corporate, Agency, Securitized | — | licensed product | licence | — | **FINRA_TERMS_REQUIRED** |
| TreasuryDirect / FedInvest prices | Treasury | — | robots `Disallow: /` | disallowed | — | not used (unchanged from S9) |
| MSRB EMMA | Municipal | — | programmatic data is a paid subscription | not licensed for redistribution | — | **TERMS_REQUIRED**; not scraped |
| NRSRO ratings (S&P, Moody's, Fitch; Rule 17g-7(b) histories) | all | — | click-through / licensed | NRSRO terms | — | **TERMS_REQUIRED**; not scraped |
| FRED | context | unchanged from S9 | `FRED_API_KEY` | FRED | — | NOT_CONFIGURED on this host |

`fixed_income/http.py` allowlists the hosts that answer HTTP calls. S16 adds
`markets.newyorkfed.org` and `api.openfigi.com` to that list. N-PORT downloads go
through the S14 SEC fetcher, never per request.

## Categories inside BONDS

| Category | Source | Rows (outstanding 2026-09-29) | Coverage state |
|----------|--------|-------------------------------|----------------|
| Treasury | Fiscal Data auctions + MSPD (S9) | 463 | CURRENT |
| Corporate | N-PORT `DBT`, issuer type `CORP` | 19,960 | FUND_HELD_REFERENCE |
| Agency | N-PORT `DBT`, issuer type `USGSE` / `USGA` | 4,064 | FUND_HELD_REFERENCE |
| Municipal | N-PORT `DBT`, issuer type `MUN` | 136,206 | FUND_HELD_REFERENCE |
| Securitized | N-PORT `ABS-MBS` (agency and non-agency), `ABS-CBDO`, `ABS-APCP`, `ABS-O` | 157,695 | FUND_HELD_REFERENCE |

- `category` is a CATALOG field, so it filters, sorts, and searches.
- The footer shows each category's own count, and `coverage_sources` gives each
  category's own source and clock: a fund-held category's clock is its N-PORT report
  date.
- ETFs are not bonds. ETF rows stay in `US_ETFS`, and a test asserts no instrument id
  is shared.

**Fund-held coverage, not every bond.** A row means at least one SEC-registered fund
reported holding that CUSIP at its report date. A bond held by no registered fund is
absent. A bond called after the report date can still appear until the next
generation. Rows whose reconciled maturity is on or before today are dropped at read
time.

## N-PORT reconciliation (`fixed_income/nport_catalog.py`)

The build runs offline from a verified ZIP into one SQLite generation. Per CUSIP,
after amended filings (`NPORT-P/A`) supersede the original for the same series and
report date:

1. **Identifier.** The CUSIP must pass its check digit, so placeholders like
   `999999999` fail. UMBS/GNMA TBA forwards are excluded (`01F` / `01N` / `21H`
   prefixes, or "TBA" in the title). **A letter-prefixed (CINS-shaped) identifier is
   admitted only when a reporting fund's ISIN embeds it.** Fund administrators'
   internal IDs (`ACI0…`, `BL…`, `BA000…`) carry a CUSIP-style check digit too. They
   would otherwise pose as CUSIPs and duplicate real bonds: `BR4230529` duplicated
   Banco do Brasil `059578AF1`. These are rejected as `UNCORROBORATED_IDENTIFIER`
   (2,225).
2. **Scope.** Only USD lines of asset category `DBT` or `ABS-*` count.
   - UST lines are skipped, because the Treasury catalog is authoritative.
   - Non-U.S. sovereign, loan, equity, and derivative categories are excluded and
     counted.
   - A CUSIP with no USD line is `NON_USD`.
3. **Consensus.** Category and maturity each need at least 75 % of lines to agree.
   Otherwise the CUSIP is rejected as `CATEGORY_CONFLICT` / `MATURITY_CONFLICT`.
4. **Coupon.** A fixed coupon is the modal exact value of the 2-decimal cluster that
   at least 75 % of fixed-coupon lines fall into.
   - A fraction-encoded rate (0.0457 for 4.57 %) is folded ×100 only when
     corroborated: by another filing's rate, or by a percentage in a reporting fund's
     own title ("FNMA 4.50% …").
   - A split cluster or an uncorroborated sub-0.1 % value withholds the coupon, and the
     row stays with a stated coupon state.
   - A floating/variable `ANNUALIZED_RATE` is the report-date rate. It is never stored
     as a coupon; it is shown as "Reported rate (report date)".
5. **Identity.** `instrument_id` is the XA01 bond id of the CUSIP, the same derivation
   as Treasury rows.
   - An ISIN is REPORTED when a fund's ISIN embeds the CUSIP.
   - Otherwise it is DERIVED (`US` + CUSIP + ISO 6166 check digit), only for a numeric
     CUSIP of a U.S. issuer.
   - Otherwise there is no ISIN.
6. **Holdings.** The values are `fund_count` (distinct series), `par_held` (sum of
   principal across lines) and `value_pct_par`. `value_pct_par` is the median of fund
   fair value ÷ principal at the latest report date. It is a **stale, fund-reported
   valuation**: class STALE, never a price. An implausible ratio (outside 0–300) is a
   unit error and is withheld.

Coupon states in the published generation (`gen-20260929T163829Z-561ece880b`):

| State | Count |
|-------|-------|
| CONSENSUS | 266,355 |
| NOT_FIXED | 47,400 |
| COUPON_TYPE_CONFLICT | 7,318 |
| ZERO_COUPON | 3,561 |
| COUPON_CONFLICT | 1,377 |
| AMBIGUOUS_RATE_ENCODING | 162 |
| NO_FIXED_RATE_REPORTED | 1 |

**Rejections.** Per CUSIP:

| Reason | Count |
|--------|-------|
| NON_USD | 10,633 |
| MATURITY_CONFLICT | 2,317 |
| UNCORROBORATED_IDENTIFIER | 2,225 |
| CATEGORY_CONFLICT | 1,874 |
| MISSING_MATURITY | 27 |

Per line:

| Reason | Count |
|--------|-------|
| EXCLUDED_ISSUER_TYPE | 88,061 |
| TREASURY_FROM_TREASURY_CATALOG | 54,393 |
| INVALID_CUSIP | 49,229 |
| TBA_FORWARD | 9,987 |

The generation contains 326,174 securities: Corporate 21,688, Agency 4,236, Municipal
141,433, Securitized 158,817. It was built from 14,416 submissions (86 superseded by
amendments) and 2,288,615 debt lines. Report dates run from 2025-04-30 to 2026-04-30,
and the latest filing date is 2026-06-29. The source is `2026q2_nport.zip`, sha256
`077cc836…c3b02296fc`.

N-PORT has no coupon frequency, day count, call schedule, amount outstanding, or
rating. **No price, yield, duration, or accrued-interest math is ever run on a
fund-held row.** Those items are UNAVAILABLE with the reason.

## Treasury market observations (`treasury_market.py`, `nyfed.py`, `observed.py`)

- **TIPS.** The index ratio and reference CPI for the latest index date on or before
  today are OBSERVED. The inflation-adjusted principal per 100 is DERIVED.
- **FRN.** The daily index, spread, accrual rate, accrued per 100, and accrual period
  are OBSERVED. An FRN never gets a fixed-rate yield (`FRN_FLOATING_COUPON`).
- **Operation prices.** The latest observation per CUSIP comes from two feeds over a
  60-day lookback: Treasury buybacks (price per 100) and NY Fed outright purchases.
  - **Fed bill purchases are accepted on a discount-rate basis.** The feed's
    `weightedAvgAccptPrice` for a bill is a rate (e.g. 3.932 = 3.932 %), confirmed
    against the raw feed on 2026-09-29.
  - IMP keeps it as the OBSERVED discount rate. It converts it to a DERIVED price only
    against the bill's maturity: `100 × (1 − d × days/360)`, from settlement.
  - A rate quote on a non-bill is `QUOTE_BASIS_MISMATCH`.
  - Reading the rate as a price had produced spreads of 1.38 M bp in the first live
    run. A regression test now pins this.
- **Dated analytics** at the operation price and settlement date:
  - notes and bonds: 31 CFR 356 App. B yield to maturity, then modified and Macaulay
    duration and DV01 at that yield;
  - bills: investment rate and bank-discount rate, with DV01 on the investment-rate
    basis (`analytics.bill_analytics`, which inverts the 31 CFR 356 investment-rate
    formula);
  - TIPS: buyback prices are per 100 of **unadjusted** principal, so the result is a
    **real** yield, compared with the real par curve. The live check below confirms
    this basis.
- **Spread.** The dated spread is the observed yield minus the par curve of the
  **same operation date**, linearly interpolated between the two bracketing published
  tenors. It is never extrapolated (`OUTSIDE_CURVE_RANGE`). With no curve that day,
  there is no spread (`NO_CURVE_ON_OPERATION_DATE`).
- **Presentation.** Every observed value shows the operation date. The Observed view,
  Quick Preview, and Rates & Curve label these values "dated, not current". The
  observed columns are REFERENCE fields: they are shown for visible rows only, and
  never filter or sort across the universe.
- **SOMA.** Par held and the percent of issue outstanding for the selected CUSIP are
  OBSERVED holdings facts as of the SOMA date.

## Point in time

| Value | Effective date | Public / known date | How IMP labels it |
|-------|---------------|---------------------|-------------------|
| N-PORT terms and holdings | report date (month end) | filing date, about 60 days later | as_of = report date; the preview shows the report window and latest filing date; source state CURRENT_AS_FILED |
| Fund fair value | report date | filing date | STALE with the report date, never a price |
| Buyback / Fed operation prices | operation date | same day (results) | OBSERVED at the operation date; settlement shown |
| Dated yield / spread / duration | operation settlement date | — | DERIVED at the operation date; the curve is the same day's publication |
| TIPS index ratio / FRN index | index date | published in advance / daily | OBSERVED at the index date |
| SOMA holdings | as-of date (weekly) | weekly release | OBSERVED at the as-of date |
| NY Fed reference rates | effective date | next business day | OBSERVED at the effective date |
| Treasury par curves | publication date | same evening | REFERENCE at the publication date |

A newer N-PORT quarter replaces the generation atomically. The previous generation
stays for `--rollback`. The API process picks up a new `CURRENT` without a restart.
This was verified live: the running server moved from 320,386 to 318,388 rows when
the corrected generation was published.

## Service and UI

- **`BondScreener`** (`ui_api/screener_bonds.py`) merges Treasury rows (dicts) and
  fund-held rows (`FundHeldRow` slotted views over frozen `NportRecord`s) into one
  list per inputs and day.
  - The canonical query filters, sorts, and pages that list.
  - Only the page's rows become dicts. Only visible Treasury rows get rates and
    observed values.
  - There is no client-side catalog and no remote call per row.
  - Quick Preview finds a fund row through the catalog's id index. The Treasury scan
    stops at the first fund row.
- **Filters** (CATALOG): category, isin, coupon_type, in_default, convertible, pik,
  fund_count, fund_par_held (USD millions), fund_value_pct, report_date.
  **REFERENCE (display only):** observed_price, observed_yield, benchmark_spread,
  observed_date.
- **Views:** Overview (with Category), Treasuries, Rates & Curve, **Credit & Munis**
  (issuer, category, type, coupon, coupon type, maturity, funds, fund par, fund
  value, reported), **Observed** (observed price, yield, spread, date, reference
  tenor and rate), Custom.
- **Quick Preview.**
  - Fund rows show Identity (reported issuer, title, CUSIP, ISIN with its source, LEI,
    FIGI), Terms (fund-reported, with the coupon state), Market, Fund holdings,
    Analytics, Ratings, and Rates context.
    - Market has no price; the latest trade shows the TRACE or EMMA licence reason;
      the fund value is STALE.
    - Fund holdings show the funds, par, report window, filing date, and SOMA.
    - Analytics are UNAVAILABLE with reasons; ratings are TERMS_REQUIRED; the rates
      context shows the nearest par tenor as REFERENCE, and the spread is
      UNAVAILABLE.
  - Treasury rows add the observed operation price, discount rate, and yield;
    TIPS inflation and FRN floating sections; dated analytics; SOMA; and the dated
    spread.
  - The headline shows the observed price, or else the stale fund value on its own
    line, or else "—".
- **Rates & Curve:**
  - the selected bond's category;
  - the auction yield (Treasury only);
  - the dated spread at the observed price, with its operation date, curve date,
    interpolation tenors and "dated, not current";
  - the NY Fed reference rates and SOMA counts;
  - FINRA corporate and agency breadth (counts, not prices);
  - the full source-clock matrix.

## Operator tool (`tools/fixed_income/nport_refresh.py`)

It mirrors `thirteen_f_refresh`:

- `--status`
- `--check`
- `--refresh [--dry-run] [--force]`
- `--rollback`
- `--generations`

Offline, `--import-zip` admits a hand-downloaded official ZIP, with the same
verification, and `--listing-file` reads a saved copy of the SEC data-set page. The
root (`--root` or `IMP_NPORT_DATA_ROOT`) must be outside the repository. Start the UI
API with `IMP_NPORT_DATA_ROOT=<root>`. Without it, the fund-held categories report
`NOT_CONFIGURED` and Treasury rows are unaffected.

## Live acceptance (owner workstation, 2026-09-29)

Run with `IMP_TREASURY_LIVE=1` against the published generation.
`SEC_USER_AGENT` was set only for the N-PORT download, in the process environment,
never in a file.

- **N-PORT build:** 195 s build, 3.7 s validate, 0.015 s swap. The index is 101 MB of
  SQLite.
- **BONDS unfiltered:** 318,388 rows.
  - Coverage: Treasury 463 CURRENT; Corporate 19,960, Agency 4,064, Municipal
    136,206, and Securitized 157,695 FUND_HELD_REFERENCE.
  - The N-PORT source is CURRENT_AS_FILED, as of 2026-04-30.
- **Market feeds:** 53 TIPS index ratios, 8 FRN indexes, 131 buyback observations,
  21 Fed purchase observations, and 117 priced CUSIPs (103 buyback, 14 Fed bill
  purchase). All feeds were healthy.
- **Dated spreads:** 117 in total, from −9.6 bp to +21.0 bp with a median of +4.4 bp.
  The +21 bp outliers are long off-the-run TIPS against the real par curve:
  `912810RL4` at a real yield of 3.066 % against a real par of 2.856 %.
- **TIPS basis check.** Six TIPS buybacks on 2026-09-15 priced between 49.25 and
  92.255 per 100, with index ratios of 1.28–1.54. At those prices, real yields of
  2.82–3.11 % sit 11–21 bp from the real par curve. An inflation-adjusted price would
  imply yields several hundred bp off, so the prices are per 100 of unadjusted
  principal.
- **Fed bill purchase check.** `912797SK4` was accepted at a 3.688 % discount rate on
  2026-08-20. That converts to a price of 99.293 and an investment rate of 3.766 %,
  a spread of −4.6 bp against the 2M–3M interpolated par of 3.811 %.
- **NY Fed rates (2026-09-28):** SOFR 3.90 %, EFFR 3.88 % (target 3.75–4.00 %), OBFR
  3.88 %, TGCR 3.89 %, BGCR 3.89 %.
- **SOMA (as of 2026-09-23):** 49 Bills, 326 NotesBonds, 8 FRNs, 50 TIPS, 6 agency
  debts, 8,387 MBS, and 560 CMBS.
- **Not configured on this host:** FRED (`FRED_API_KEY_MISSING`), FINRA aggregates
  and breadth (`IMP_FINRA_LIVE_NOT_SET`), and OpenFIGI (`IMP_OPENFIGI_LIVE_NOT_SET`).
  NRSRO and MSRB EMMA are TERMS_REQUIRED.
- **UI** (built-in browser, vite and UI API with live feeds):
  - checked at 1920×1080, 2560×1440, and 1100×800 (reloaded at that size);
  - no page-level horizontal overflow and no clipped headline or panel values;
  - one overflow found and fixed: the stale fund-value qualifier now sits on its own
    line;
  - at 1100 px, Quick Preview is the existing 400 px drawer and the Rates & Curve
    side column stacks under the chart;
  - the panel launcher is the existing horizontal scroller.

## Performance (local, one process, 2026-09-29)

| Operation | Cold median (3 runs, result cache cleared) | Cached |
|-----------|-------------------------------------------|--------|
| default (maturity ↑), 318,388 rows | 824 ms | 30 ms |
| sort coupon ↓ | 851 ms | 54 ms |
| filter category = Municipal (136,206) | 676 ms | 29 ms |
| Corporate and coupon > 6 (3,413) | 321 ms | 29 ms |
| fund_count ≥ 20, sorted (18,650) | 491 ms | 32 ms |
| search "apple" (96) | 112 ms | 29 ms |
| search ISIN prefix "US037833" (43) | 107 ms | 28 ms |
| deep page, offset 300,000 | 895 ms | 28 ms |

Other timings:

- Catalog load: 3.6 s. The first read, including live Treasury and market fetches,
  takes 7.7 s.
- Memory, measured as working set: +240 MB after the catalog loads, +381 MB after
  the first read, and 580 MB total for the process.
- Treasury preview: 0.6 ms. Rates & Curve: 0.4 ms. A warm fund-row preview: about
  0.3 ms (12 ms before the Treasury scan stopped at the first fund row).
- The first preview of a session takes about 1 s, because it performs the one-time
  NY Fed rates and SOMA fetches, which are then cached.

## Tests

| Suite | Result |
|-------|--------|
| `tests/fixed_income/test_s16_fixed_income_expansion.py` (new) | 42 passed |
| `tests/platform/test_screener_s9.py` (network now injected; 55 s → 0.1 s) + `tests/fixed_income/test_fixed_income.py` | passed |
| UI `Bonds.test.tsx` (5 new S16 cases) | 14 passed |
| `tools/imp.py validate changed` | 2,770 tests, 0 failures, 0 errors |
| `tools/imp.py validate full` (includes Screener S1–S15, S14 lifecycle, repository closure) | 7,553 tests, 52 skipped, 0 failures, 0 errors |
| UI `npm run typecheck`, `npm test -- --run`, `npm run build` | clean; 1,181 tests in 156 files passed; build passed |
| `check_docs_links.py`, `monorepo_guard.py validate --ci`, `generate_history_ledger.py validate --ci` | passed |

The full UI suite passes once no other heavy processes are running. While a dev
server and the 4-worker Python validation ran at the same time, some App-shell tests
exceeded their 1 s `findBy` wait. Those same files pass in isolation and in the
clean full run.

The S16 suite uses a synthetic N-PORT ZIP (fixture-only, never shown as data). It
covers:

- amendment supersede, fraction folding, TBA, UST, invalid CUSIP, non-USD, excluded
  issuer, equity and matured lines;
- the uncorroborated letter-prefixed identifier;
- identifier check digits (published ISINs);
- the build's determinism and integrity failure;
- the lifecycle: publish, empty root, corrupt download, and missing category;
- the TIPS / FRN / buyback / Fed-operation parsers, including the bill discount-rate
  basis;
- observed analytics round trips, the same-day curve, the real curve, no
  extrapolation, and the quote-basis mismatch;
- OpenFIGI and FINRA gating;
- fund rows in the canonical query: categories, filters, sort, search, paging,
  stale values that are never a price, REFERENCE columns that never filter,
  preview and curve reasons, unique identity, and bonds that are never ETFs.

## Known limitations

- **Coverage.** Fund-held coverage is not the full outstanding universe. Private
  placements, most bank loans, and bonds no registered fund holds are absent. Terms
  are as reported by funds and reconciled, not issuer documents.
- **Lag.** N-PORT is up to about 5 months old at the screen: a report date plus
  roughly 60 days to public filing, plus the quarterly data-set cadence. A called or
  defaulted bond can appear until the next generation.
- **CINS without an ISIN.** Genuine CINS securities that no fund reported with an
  ISIN are excluded along with the administrator IDs. This is conservative and
  counted as UNCORROBORATED_IDENTIFIER.
- **No current bond prices.** There is no current price, yield, spread, rating, or
  trade for any bond: licences required (TRACE, EMMA, NRSRO) or access disallowed
  (FedInvest). Treasury analytics exist only at dated operation prices, on at most
  a 60-day lookback. 117 CUSIPs had them on 2026-09-29.
- **Securitized terms.** No factor, WAL, or prepayment data for securitized rows:
  N-PORT does not report them. SOMA MBS terms are free text and are not typed.
- **Not configured here.** FINRA breadth and OpenFIGI are implemented and tested
  against fakes, but were NOT_CONFIGURED on this host (no credentials / opt-in).
  Their live behaviour is unverified.
- **Cold latency.** Cold unfiltered sorts over about 318k rows take 0.8–0.9 s.
  Cached pages take about 30 ms.
- **Visual check.** The visual check used the built-in browser, with geometry probes
  and partial screenshots: the pane captures an 800×450 crop. *See [final closure](SCREENER_FINAL_CLOSURE.md)
  for the five-universe pass, including Bonds News reading every Treasury.*
