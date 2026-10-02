# Order-flow temporal history (OCT1-01)

IMP's Order Flow and CVD panels share an observational temporal-series contract.
The existing S4 current summaries, recent tape, classification, authority gates,
and `SINCE_SUBSCRIPTION` / `LAST_N_CAPTURED` labels retain their meanings.
The historical CVD chart has a separately stated captured accumulation anchor;
it does not reset when the trader changes range, resolution, or viewport.

## Storage and evidence

`order_flow/history.py` retains one aggregate per observed second independently
of the 500-print tape. Both equity admission paths and Kraken's native trade
path feed this store. Each aggregate preserves signed delta, side volumes,
unknown volume, classification counts, source/receive clocks, provider identities,
and capture segment. Only exchange-native sides are native; provider-directed
and model-directed sides remain inferred. Unknown sides contribute no signed flow.

History is **runtime-local**, not durable session evidence. Restart, day rollover,
instrument eviction, earlier subscription absence, and interruptions remain partial.
An evicted instrument starts a new capture anchor on its next admitted print,
including when demand heartbeats repeat the old subscription activation time.
The optional live recorder and bounded envelope capture cannot guarantee current
intraday history, so this surface does not silently reuse replay journals or
experimental evidence stores. No historical provider entitlement or backfill is
assumed; no OHLCV reconstruction, interpolation, or synthetic zero-flow buckets.

Retention is bounded to one calendar day, 32 instruments, and at most 86,400
observed-second buckets per instrument. Equity days use America/New_York; crypto
uses the existing UTC-day/24-hour convention. Duplicate identities are retained
for a bounded 120-second event-time correction horizon, at most 50,000 identities.
Arrivals outside that horizon are excluded and counted explicitly; their absence
prevents a complete-coverage claim. Out-of-order observations within the horizon
update the earlier bucket, and subsequent CVD levels are projected in event order.
A configured smaller bucket limit preserves an absolute CVD baseline while
reporting truncation. Snapshot projection and ingestion use the store's own lock.

Subscription release/reacquisition, provider connection loss, queue overflow,
provider changes, and receive silence longer than 30 seconds produce explicit
coverage boundaries. Silence means **continuity unverified**, which can include
a legitimate period without prints; it is not asserted to prove provider loss.
Separate chart series prevent CVD lines from bridging capture segments.
Late arrivals use event-time segments. Observations inside an uncertain interval
are isolated by second so they cannot reconnect the line across that interval.

## Read contract

`GET /screener/order-flow-series` uses the existing universe/catalog admission,
current-provider, subscription, entitlement, source-state and read-route authority.
It takes `instrument`, `universe`, `range` (`1m`, `5m`, `15m`, `1h`, `session`),
`resolution` (`auto`, `1s`, `5s`, `15s`, `1m`, `5m`), and optional integer
millisecond `start`/`end`. Windows are half-open, positive, at most 24 hours,
and cannot end in the future. Invalid or repeated temporal parameters fail with
HTTP 400. Blocked states expose no historical points.

Coverage returns requested/actual bounds, capture anchor, complete/truncated
flags, gaps, excluded late arrivals, and `RUNTIME_LOCAL` persistence.
`complete` describes continuous subscribed capture for the requested window;
it does not establish consolidated venue coverage, complete aggressor
classification, or exchange-wide ground truth. Capture from after market open
never establishes complete morning coverage.

The endpoint bounds each response to 2,000 aggregate points, raising effective
resolution when necessary. Auto selects 1s through five minutes, 5s through
15 minutes, 15s through an hour, and 1m for broader ranges. Delta is the sum
inside each bucket; CVD is the absolute captured cumulative value at bucket
close. Aggregation never crosses an explicit segment boundary. The response
reports actual effective resolution rather than silently promising finer detail.

Equity Session begins at 04:00 ET in premarket, 09:30 ET in regular/closed
session context, and 16:00 ET in after-hours. Crypto labels this range **UTC day**.
This is a current-phase navigation scope, not a complete exchange-calendar or
overnight-session redesign.

## Navigation and clocks

Both panels provide range, resolution, mouse/pinch navigation, keyboard-accessible
zoom buttons, Fit, and Go Live. Initial load, instrument/range changes and explicit
Fit fit the chart; polling does not call `fitContent`. Historical inspection
preserves time bounds while new data arrives. Go Live restores the right edge.
Fit follows the full captured selection as new observations arrive; zoomed live
views preserve their chosen width. React memoization keeps viewport changes from
replacing chart data and cancelling pending chart navigation.

Current S4 state still polls at approximately one second. The broader temporal query
polls at five seconds while visible, including during historical inspection, so
current captured context stays current. Historical detail is requested after
300 ms of viewport settling. Broader context remains loaded around finer detail,
so zoom-out and backward pan remain usable.
Detail requests expand to whole overlapping coarse buckets before replacement,
preserving the observations on both sides of a narrower viewport.
Queries include universe, instrument, range, resolution and detail bounds;
AbortSignal and identity guards prevent old
symbol responses from populating a new symbol. During historical inspection,
requested/actual bounds and gap notices come from the historical detail response,
so healthy current capture cannot hide an older interruption.

Visible totals sum displayed buckets and include trade count, signed volume,
classification percentage and unknown volume. At coarse resolution, edge buckets
can straddle the visible boundary; these are bucket totals rather than tick-exact
sub-bucket measurements. Missing coverage and low classification remain visible.
An accessible text summary reports visible bounds and totals; the original
current CVD warning remains: a rising CVD is not a forecast.

## Acceptance

Automated S4 cases cover rollover, aggregation, stable anchors, ordering,
deduplication, gaps, source changes, truncation, day/session boundaries and feed
states. Focused chart tests cover pan/zoom/live/Fit behavior. Controlled browser
acceptance uses synthetic admitted prints and the actual temporal backend, React
components and Lightweight Charts; it is software evidence only. It does not
prove actual morning capture or activate any Paper/Live execution authority.
