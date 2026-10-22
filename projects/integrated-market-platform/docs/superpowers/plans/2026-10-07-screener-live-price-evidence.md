# Screener live price evidence convergence

Status: software implemented and accepted locally; protected integration receipts belong to the owning PR. Evidence class: SOFTWARE_CONTROLLED.
Base: `55fbc2207d14e0852f3f45296fdc3c1ef6df3a58`.
Branch: `codex/screener-live-price-evidence`.

## Dependency map and proven failure seam (before behavior changes)

- OpenD transport normalizes source event and receive clocks into admitted L1 events.
- `market_data/observational_state.py` stores per-symbol `QuoteSnapshot` with canonical
  session last price, bid/ask, volume, provider, event/available/receive clocks.
- `ui_api/screener_projections.py::quote_view/quote_for` reads that shared runtime
  cache without provider calls. `window` owns bounded, expiring subscriptions.
- `ScreenerService.read` caches Finviz reference rows and orders them from snapshot
  values. It returns those rows without joining `quote_for`. ETF catalog/snapshot
  reads in `screener_multi.py` likewise omit the shared live observation.
- `ScreenerPage.tsx::fieldFor` overlays `/screener/window` quotes only in React.
- `screener_ai.py::_packet` reconstructs first 20 backend rows from
  `MultiUniverseScreener.read`; it never sees the React overlay.
- `screener_freshness.py` groups field source/clock/state, deliberately strips
  Finviz retrieval clocks from market observation authority, and evaluates OCT1-03.
- `candidate_reduction.py::build_candidate` excludes timeless price; the reducer
  rejects an empty grounded set before model work. Action requires selected lineage.

Thus the provider observation is present in the backend runtime, but absent from
backend Screener page rows. AI receives the timeless Finviz price, correctly yielding
`NO_OBSERVATION_TIME`, then `NO_GROUNDED_CANDIDATES`.

## Intended repair

Overlay already-owned equity/ETF quote fields on returned page rows after snapshot
filtering/order. Never mutate cached reference rows. Reapply on each read and after
reference refresh; retain stale quote authority for continuity with truthful aging.
Use existing field schema and canonical last price, not midpoint or prior close.
Preserve original provider event/receive clocks; no manufactured timestamps.
Keep freshness policy, 20-row intake, mandatory support, preview economy and all
execution gates unchanged. Expand bounded quote facts to include same-observation
bid/ask/spread, and retain receive provenance in new immutable evidence.

Live RTH acceptance: `NOT_OBSERVED_MARKET_CLOSED` (October 6, after US cash close).
No Paper or Live submissions authorized or required for this proof.

## Validation baseline

`python tools/imp.py validate fast`: 23 run, 23 passed, 0 skipped, 0 failures,
0 errors, 18.552s. Observe-only `SEVERE_REGRESSION` timing classification retained.

Acceptance, performance, final validation and integration receipts will be recorded
below after execution.

## A–S completion report

### A. Verdict

Controlled software implementation accepted. Final integration verdict belongs to the owning PR checks/merge metadata. Evidence class remains SOFTWARE_CONTROLLED.

### B. Repository

Base `55fbc2207d14e0852f3f45296fdc3c1ef6df3a58`; branch
`codex/screener-live-price-evidence`. Isolated managed worktree only; the
primary checkout and leftover nested clone were not edited. Implementation, PR, merge and final-main identities are recorded by the owning PR Git metadata and final integration report.

### C–D. Original defect and seam

The provider/runtime cache held healthy quotes. React's window overlay could
show them, but backend Screener rows supplied to AI still held a timeless
Finviz price. OCT1-03 correctly rejected that price. The repair joins the
existing runtime observation into backend equity/ETF page and selected-row
reads, after snapshot filtering/order, before evidence composition.

### E–G. Authority, Finviz and PIT

Canonical last traded price is the admitted OpenD L1 `last_price`, not a
midpoint or prior close. Numeric quote fields preserve provider and exact
source event clock; receive clock remains separate. Finviz price is fallback
reference when no L1 value exists; fundamentals, discovery and remaining
reference fields retain their own source. Refresh never mutates the L1 cache
or overwrites its returned authority. Stale observations stay visible with
stale state. Freshness policy, future cutoff checks and required strong support
are unchanged. Missing provider clocks are unknown; carried book values do
not inherit a later last-price event clock.

### H–I. Controlled evidence and AI

Backend fixture NVDA: before Finviz `$240`, observation null,
`NO_OBSERVATION_TIME`; after OpenD `$240.27`, observed
`2026-10-06T18:05:23Z`, received `2026-10-06T18:05:23.500000Z`, CURRENT.
The candidate receives the same numeric price/source/time and same-clock
bid/ask; canonical volume supplies additional admitted technical support.
Missing specialist/news/sentiment capabilities remain explicit. Read-only operator configuration audit found automatic engine selection (no saved model override), with Finnhub/NewsAPI configured. Canonical selected-provider reuse, model/reasoning/prompt configuration remain unchanged; no network audit calls. Preview and
empty-grounded runs make zero model calls. A controlled survivor triggers one
fixture model call; no paid/network inference is used. Intake remains first
20, selected maximum five, packet bounded and source-qualified.

### J. Action lineage and compatibility

The selected immutable candidate run supplies the Action Decision reference
price, observation and supporting references. Changed quotes change new hashes
without rewriting prior history. Controlled browser Action Decision showed
`120.12` / `2026-10-07T04:20:03.202006Z`, exactly the selected evidence.
Server gates returned REVALIDATION_REQUIRED with POSITION_SNAPSHOT_STALE and
PAPER_AUTHORITY_UNAVAILABLE. Those legitimate fixture limits were retained;
no entry/fill was forced. Paper/Live submit counts zero; fixture ledger stayed
at its baseline two events. Reevaluation, SMA, lifecycle, Paper routing and
outcome evaluation implementations are unchanged and covered by full validation.

### K–L. UI and controlled acceptance

The explicit loopback harness uses production API handlers and the production
bundle, isolated state, fixture source/model/auth and an explicitly controlled
REGULAR session. It refuses submit routes. Normal application startup has no
fixture fallback. Browser steps on the final bundle:

1. Reference only: three Finviz prices `240.00`, fundamentals `500` and short
   float `2.00%`; preview grounded zero, run selected zero with
   NO_GROUNDED_CANDIDATES; model counter stayed at two earlier fixture calls.
2. Controlled ticks: table AMD `120.12`, NVDA `240.27`, AAPL `140.15`, CURRENT;
   model counter increased from two to three; run selected one of three.
   AMD supporting QUOTE: provider MOOMOO_OPEND, observed
   `2026-10-07T04:20:03.202006Z`, received
   `2026-10-07T04:20:03.402006Z`, price `120.12`, bid `120.11`, ask `120.13`.
   Table tooltip and evidence card expose source/clocks; the card says
   SOFTWARE_CONTROLLED fixture and missing capabilities.
3. Evaluate Decision: exact reference price/time and references retained;
   explicit revalidation blockers, zero submissions, ledger unchanged.
4. Disconnect/age by 61 seconds: price retained, three REALTIME · STALE
   labels, run selected zero with NO_GROUNDED_CANDIDATES; model counter stayed
   three. Reconnect/tick restores current labels.

Cached preview counts can differ from a later run; each is evaluated at its
own cutoff. Preview does not score/acquire; POST run always reevaluates.

### M. Live RTH

`LIVE_RTH_ACCEPTANCE = NOT_OBSERVED_MARKET_CLOSED`.
This is not prospective provider proof, a trading result, or a live session
receipt. No historical observation was labelled prospective live.

### N. Performance

150 controlled iterations: overlay 20 rows median 0.0125ms / p95 0.0266ms;
100 rows 0.0579ms / 0.0633ms; freshness 20 rows 0.4773ms / 1.0688ms;
candidate gate 20 rows 1.5003ms / 2.5161ms. These are local fixture timings,
not production latency claims. Overlay issues zero provider requests, reads
only the shared per-symbol cache, preserves the frozen result-set ordering
and has one bounded 32-symbol expiring window owner (first 20 intake plus
selection/visible rows). No per-symbol HTTP request was added. UI retains its
existing table/window render path; fine-grained cell-only rendering is not
claimed. Production build: 8.56s, initial gzip 100.76KiB (200KiB budget).
AI panel remains lazy-loaded.

### O. Validation

Final FAST: 23 run/passed, 0 skips/failures/errors, 3.007s. Final FULL: 8,154 run, 8,101 passed, 53 skipped, 0 failures/errors, 645.696s. Both timing classifiers retained SEVERE_REGRESSION under the existing observe-only policy. Full skip ledger is retained in the JSON receipt: phase0 1, platform 4, donor_bridge 8, intelligence 27, integration 3, of01 3, xa04 7 (environment/platform, donor services, Mongo, and explicit fixture skips). Final CHANGED: 5,100 run, 5,065 passed, 35 skipped, 0 failures/errors, 291.978s, INSUFFICIENT_DATA timing classification. It included extra regenerated-artifact groups, subsequently restored; FULL validates the final repair as well. Focused backend ten passed including observed red/green
price and carried-book regressions. Focused UI final 54 passed across three
files. Typecheck/build and compile lint passed; docs links checked 292 files.
History guard passed; monorepo `validate --ci` passed. Local non-CI guard
requires donor source clones absent from this isolated checkout; no manifest
was changed. UI all-tests under concurrent CPU load failed five timing-sensitive
tests in two files; focused rerun passed, complete rerun with `--maxWorkers=1 --minWorkers=1 --no-file-parallelism` passed: 179 files, 1,374 tests, zero failures, 113.79s.
Earlier full attempts were INTERRUPTED and are not counted as passing; completed final
run used a separate Windows process group. No skipped tests are hidden.

### P. Read-only review

Found and fixed carried-book clock conflation with a regression proven red
before repair. Reviewed symbol mapping, immutable row caches, stable sorting,
missing/stale/future/delayed/disconnected gate behavior, lineage, source clock
hashes, model-call boundary, bounded subscription ownership and no provider or
execution authority expansion. No source-specific freshness waiver exists.

### Q. Genuine remaining limits

RTH proof is deferred. Provider availability/entitlements and true source
clocks remain external dependencies. Partial cached quote coverage and absent
additional strong support can legitimately yield no candidates. Carried bid/ask
without retained provider event time remains unknown until a new observation.
Cached preview estimates do not refresh on every tick. Intake warming shares
32-symbol capacity with selection/viewport; rows beyond capacity are not
subscribed by the AI read. Finviz filter/sort values remain snapshot authority
while returned market cells update, deliberately avoiding tick-driven reshuffle.

### R. Integration

Protected integration requires the up-to-date main `validate` check plus all IMP checks green on the exact implementation head; merge ancestry/tree/clean-worktree identities are recorded in the owning PR and final report. No bypass is authorized. No unrelated
tracker was created or marked closed, and no historical roadmap status changed.

### S. Next state

The timeless Finviz blocker is software-fixed when legitimate current cached
L1 evidence exists. Live runtime convergence remains pending RTH proof.

## Addendum: QUOTE push observation time (OCT1-13)

The pre-RTH readiness check on live OpenD still found `NO_OBSERVATION_TIME` on
rows with a live Moomoo price. The 2026-10-06 regular-session capture shows the
same split at 14:12 ET: NVDA, INTC, MRVL, NKE and SPCX blocked; AAL, PACB and
RXRX admissible. The cause is in the L1 cache, not the row join: OpenD's QUOTE
push carries `data_date`/`data_time` (when `last_price` traded) and no
`update_time`, so each push replaced the snapshot-clocked quote with one that
had no provider clock until the next 2 s snapshot poll.

A push now takes its observation time from `data_date` + `data_time` when the
price shown is the regular-session `last_price`. It is not used for a
pre-market, after-hours or overnight price (the push has no clock for those), for
a time ahead of receipt, or for a payload with its own `update_time`. The
freshness policy and thresholds are unchanged.
