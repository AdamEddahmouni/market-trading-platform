# Main Screener S8 — Short Squeeze evidence

S8 evolves the US Equities `Short` table view into **Short Squeeze** and adds
selected-instrument evidence in the existing Screener dock and Quick Preview.
The table remains a universe-wide Finviz discovery view. The panel evaluates
one current US equity at a time; its state is a rule-based snapshot assessment,
not a squeeze probability, ranking, causal transition, or trading instruction.
Futures and ETFs do not expose this equity-specific panel.

## Architecture and authority

`screener_universes.py` publishes the view columns, capability, and legacy
`Short` alias. `screener_config.py` migrates saved screens. `server.py` exposes
read-only `GET /screener/squeeze?instrument=<canonical-id>&universe=US_EQUITIES&view=summary|detail&filters=<JSON>`.
`screener_squeeze.py` reads the existing Finviz Screener row, Moomoo L1 and S4
order-flow/CVD/Level 2 projections, S7 options cache (detail only), Finviz
news, and the public-data source adapters. `short_intelligence/squeeze_state.py`
evaluates named rules and returns state plus supporting, conflicting, context,
and missing evidence. S4's reference-counted `TRADES` subscription is shared
with the Short Squeeze dock; no new trade subscription exists.

The browser validates `screener-squeeze/1.0.0` with strict Zod objects and
rejects wrong instrument, universe, view, schema, unsupported clocks, score,
probability, or a current unreachable state. It aborts obsolete requests and
checks identity again before rendering. Detail is requested only while the
dock panel is visible, after the 250 ms dock selection settle. Summary is
requested only when the Squeeze Preview tab is active, after the Preview
selection settle. Closing both surfaces stops selected-symbol evaluations.

## Donor harvest

The evaluator adapts `squeeze_causal_baseline.v4` and the per-input
`phase_3a_transparent_candidate_policy.v1` rules already inspected during S8
backend implementation. Named evidence and source-specific missingness are
kept. The donor's 0–100 pressure/ignition composite has unvalidated weights;
its PRIME/SUBPRIME categories therefore are not a primary current signal.
Neither a weighted score nor a probability enters this endpoint.

| Donor artifact | Decision | S8 use |
|---|---|---|
| Scanner Short Pressure and Ignition sections | Adapted | Dense structural and ignition groups in the dock |
| Why Listed | Adapted | Exact active Screener predicates, separate from mechanism evidence |
| Causal contracts and evaluator cascade | Adapted | Evidence classes and rule-based snapshot state |
| Hysteresis and state transitions | Not currently used | No persisted previous state or temporal history |
| Weighted pressure/ignition score | Rejected | Unvalidated weights; no score output |
| PRIME/SUBPRIME | Rejected as primary | Research vocabulary only |
| Borrow provider | Unavailable | Fee and availability remain missing |
| Frozen cohort | Forbidden current fallback | No runtime dependency or fixture substitution |

## State and rule semantics

The operator labels are Baseline, Vulnerable, Armed, Ignition watch, Live
confirmation, Active squeeze evidence, Exhaustion evidence, Post-squeeze, and
Insufficient evidence. The supported current states are `BASELINE`,
`VULNERABLE`, `ARMED`, `IGNITION_WATCH`, `LIVE_CONFIRMATION`, and `UNEVALUABLE`.
`ACTIVE_SQUEEZE` requires dealer positioning that no current source supplies.
`EXHAUSTION` requires prior fuel and CVD history; `POST_SQUEEZE` cannot be
assigned from one snapshot. The lifecycle strip marks these three as
unavailable and never implies that the present assessment is a transition.
The existing Workspace squeeze surface keeps its own research contract; it
shares only operator-friendly state-label presentation.

Named rule thresholds are short float **> 20%** (IMP discovery), days to cover
**≥ 2**, published short-interest change **≥ 10%**, borrow fee **≥ 10%**,
change **≥ 10%**, and RVOL **≥ 5×**. The evaluator uses FINRA published days
to cover when present and attributes it; otherwise it uses the Finviz short
ratio. Borrow rules are unknown while lending is unconfigured. No single
spike establishes a higher state. Rules are provisional evidence gates, not
calibrated likelihoods.

## Evidence and clocks

Each metric carries its own value or `null`, source, quality, clock kind,
source time, and reason. Source outages and unconfigured providers are
unavailable evidence, not contradictions. The panel shows structural
pressure, ignition, live confirmation, supporting/conflicting/missing lists,
coverage counts, and Why Listed. The compact Preview shows a subset and opens
or focuses the dock. A discovery match does not mean the stock is squeezing.

| Observation | Source and clock | Distinction |
|---|---|---|
| Short float, Finviz short ratio, float, change, RVOL | Finviz Elite Screener snapshot | Delayed snapshot; short float is not borrow availability |
| Official short interest and change | FINRA settlement publication | Outstanding position, normally twice monthly |
| Daily short-sale volume | FINRA daily publication | Trading flow, not outstanding short interest |
| Threshold membership | Nasdaq, NYSE Group, Cboe Reg SHO daily lists | Membership only; a negative assertion needs every relevant list successfully read |
| Fails to deliver | SEC publication | Aggregate fail balance; no record is not zero or proof of naked shorting |
| Borrow fee and availability | Lending provider | Not configured; no live lender exists in this lane |
| Price and order flow/CVD | Moomoo L1 and S4 trade projection | Own current-session clocks; no new subscription |
| Options call/put activity | S7 Finviz options snapshot | Detail only; descriptive context, not dealer positioning |
| Headlines | Finviz news snapshot | Current-window context, not causal proof |

The Reg SHO, FINRA, and SEC adapters use their existing `IMP_*_LIVE` opt-in
flags, background fetch, bounded cache, and fail-closed states. No frozen
cohort or donor service is read on the current path. The donor service is not
a required runtime.

## Table and interaction

The US Equities view uses the backend registry's Symbol, Price, Change %,
RVOL, Volume, Float, Short Float, Short Ratio, Bid, Ask, and Spread columns.
Saved screens and URLs with `view=Short` normalize to `Short Squeeze`. The
Screener launcher has one Short Squeeze entry; an already open panel is
focused. Selected-only FINRA, borrow, FTD, Reg SHO, order-flow, CVD, and
options observations are not made universe-wide filters, sorts, or columns.
S6 server field capabilities remain the authority for that distinction.

## Current-provider acceptance (2026-09-27, closed session)

A bounded five-symbol run used a validated Finviz Elite token and the existing
Nasdaq, NYSE Group, and Cboe Reg SHO opt-in flags. The first Finviz request
failed as `FinvizHTTPError`; a direct export retry succeeded with 4,289
current US equity rows, and the next S8 run was healthy. No cached or frozen
universe replaced that failure. GME, NVDA, AAPL, AMC, and CVNA were all
`BASELINE` with `PARTIAL` source state. Their Finviz short float and short
ratio were snapshot values; Reg SHO settled to `PUBLICATION_CURRENT` from
2026-09-25 lists and reported no membership only after all three authorities
were read. The first GME list read was `PENDING`, never false.

FINRA official short interest and daily short-sale volume remained
`NOT_CONFIGURED` because FINRA credentials are absent. SEC FTD remained
`NOT_CONFIGURED` because `SEC_USER_AGENT` was not set; no zero FTD was
implied. Borrow and dealer positioning remained `NOT_CONFIGURED`. The Moomoo
trade/depth runtime was unavailable in this local closed-session process, so
Order Flow and CVD were unavailable. Preview summary left options
`NOT_REQUESTED`; opening AAPL detail read the S7 Finviz options snapshot and
returned a 1.4697 call/put volume ratio. A bounded separate scan of the
highest current short-float rows naturally found BRVE at 111.87% short float,
`ARMED`, with 2 supporting, 1 conflicting, and 12–13 unavailable observations;
CHRN and BAFN were also `ARMED`. No active squeeze state was constructed.

## Visual and performance acceptance

The live local API and Vite UI were inspected at 1920×1080, 2560×1440, and
1100×800. The table, Quick Preview Squeeze tab, dock, table-plus-dock, partial
and unavailable evidence, BRVE's natural Armed state, AAL's Baseline state,
and the retained but unavailable Futures panel were checked. At all three
widths, the document and page scroll bounds equaled the viewport bounds;
the dock measured 300 px tall, the preview 400 px wide, and the table remained
the principal surface. The 1100×800 screenshot showed the lifecycle, coverage,
and three evidence groups within the dock. The in-app browser's full-page
capture at oversized viewport overrides was distorted, so geometry and DOM
checks supplement the 1920/2560 screenshots.

Visual inspection caught and fixed two defects: date-only Reg SHO trade dates
were shifted back one day by ET conversion; and a direct Short Squeeze URL
could retain Overview columns after initial mount or Last Used restoration.
Both have UI regression tests. Date-only clocks now render as trade dates,
while timestamp clocks render in ET.

The bounded provider probe measured the first GME summary at 4,441 ms (news
and publication startup), settled summaries at 0–3 ms, first AAPL detail at
697 ms (options snapshot), and warm AAPL detail at 5 ms. S8 UI regression
tests measured **zero** selected-symbol squeeze requests while the tab and
panel were unused and **one** request after the final settled symbol in a
GME→NVDA→AAPL→AMC→CVNA navigation sequence. The production build's initial
bundle is 201.36 KiB gzip versus S7's 201.33 KiB; the lazy Screener page is
45.65 KiB gzip and the lazy Dock is 108.05 KiB gzip. The repository bundle
budget passes.

## Validation

Final gates on the committed S8 tree:

| Gate | Result |
|---|---|
| S1–S8 Screener backend (`tests.platform.test_screener_s1` … `s8`) | 228 passed (S8 50) |
| Short intelligence (`tests/short_intelligence`) | 37 passed |
| Donor squeeze bridge (`tests/donor_bridge/*squeeze*`) | 26 run, 2 skipped |
| Squeeze-lane integration | 2 run, 1 skipped |
| Focused UI (`src/components/screener`, `src/components/squeeze`, `screenerSqueeze.test.ts`) | 95 passed, 9 files |
| Full UI suite (`npm test`) | 1,089 passed, 150 files |
| Typecheck / build + bundle budget | exit 0 / exit 0; initial 201.36 KiB gzip |
| Format / lint / docs links / `git diff --check` | exit 0 / exit 0 / 271 files OK / clean |
| `python tools/imp.py validate changed` (isolated `APPDATA`) | exit 0 — 25 suites, 5,300 tests, 35 skipped, 0 failures, 0 errors, 330.5 s, perf `INSUFFICIENT_DATA` |

The frontend suite covers the strict contract and identity guard, source
clocks, unavailable values, state labels, view and legacy alias, saved-screen
restore, launcher and demand reuse, Preview lazy fetch, and rapid selection.

The first changed-domain run with the host's normal `APPDATA` had six errors
in `platform`, `intelligence`, and `providers`, reproduced by a serial rerun.
All six were `TimeoutExpired` in `tools/moomoo/check_live_environment.py`
`_opend_file_version`, where a PowerShell call reads the installed OpenD file
version and this host's PowerShell startup hangs past the test timeout. With
an empty isolated `APPDATA` the host-specific install is not discovered,
matching CI; the S3–S7 lanes used the same isolation. No S8 source was
involved. A run inside a command sandbox that denies detached
`CreateProcess` added one `software_fullstack_acceptance` error; that suite
passed 79/79 alone and in the final unsandboxed run.

## Known limitations

- `ACTIVE_SQUEEZE`, `EXHAUSTION`, and `POST_SQUEEZE` are unreachable: no
  current source supplies dealer positioning, and the evaluator has no
  persisted state or CVD history from which to assign a transition.
- Borrow fee and availability are `NOT_CONFIGURED`; borrow rules stay unknown.
- FINRA short interest, FINRA daily short-sale volume, and SEC FTD require
  credentials or `SEC_USER_AGENT`; without them they are `NOT_CONFIGURED`.
- Order flow and CVD require the Moomoo trade runtime and are unavailable
  outside a live session.
- Selected-symbol evidence is not a universe-wide filter, sort, or column.
- The panel is US-equity only; Futures and ETFs show it as unsupported.
- Rule thresholds are provisional evidence gates, not calibrated likelihoods.
