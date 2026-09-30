# Main Screener S4 — specialist dock panels

S4 adds a Screener-local dock of specialist panels — Order Flow, CVD, Level 2,
Charts, and Futures Context — around the S3 table and Quick Preview. It answers
"what is happening underneath the price right now?" for the one selected
instrument. The table stays the primary surface: the dock exists only while a
panel is open. Everything shown comes from current providers or says it is
unavailable; no replay or fixture data is substituted. See
[Main Screener S3](SCREENER_S3.md) for the preview, bars, and levels it reuses.

## Dock architecture

The dock is [Dockview](https://dockview.dev) Community (`dockview-react` 8.3.1,
MIT, with `dockview` and `dockview-core`, both MIT). It is scoped to the
Screener's bottom region; the rest of IMP is unchanged. Dockview, its
stylesheet, and every panel are lazy-loaded on the first launcher click, so the
initial Screener bundle carries only the launcher and panel registry.

| Panel id | Title | Live capability | Data |
|---|---|---|---|
| `order_flow` | Order Flow | `US_EQUITY_TICKS` | `GET /screener/order-flow` |
| `cvd` | CVD | `US_EQUITY_TICKS` | `GET /screener/cvd` |
| `level2` | Level 2 | `US_EQUITY_DEPTH` | `GET /screener/depth` |
| `charts` | Charts | S3 current bars | `GET /screener/chart` |
| `futures` | Futures Context | S3 futures context | `GET /screener/futures-context` |

One compact **Open Panels** row sits above the footer; it is the only launcher.
A closed panel opens; an open panel is activated and focused, so no duplicate
instance is created. Panels can be dragged, tabbed together, split, docked
left/right/above/below within the dock, and resized by their sashes. Floating
and pop-out groups are disabled so panels stay inside the Screener. The dock's
height is set by a horizontal splitter (pointer, or ↑/↓ 16 px and Home/End),
clamped so the table keeps at least ~200 px.

Dockview's keyboard navigation and keyboard docking are enterprise modules and
are not used. Each panel header therefore carries compact buttons — move to
previous/next group, split into its own column, narrow/widen, close — as the
keyboard path for rearranging and resizing. Arrow keys inside panels (ladder,
tape, chart controls) stay local; the table moves its selection only when the
grid has focus.

## Layout persistence

The layout is a workstation preference, stored under `screener.s4.panels`
through `POST /screener/config` action `panel_layout`:

```text
{ version: 1, open_panels: [...ids], active_panel: id|null,
  dock_height: 140–1200, dockview_layout: <Dockview JSON>|null }
```

The backend validates it: known panel ids only; every grid view and panel entry
names an open panel; panel entries may hold only scalar presentation fields and
never `params`; at most 32 KiB. Market values cannot enter it. A missing,
corrupt, or other-version record reads as the default (no panels open). On
restore, a saved arrangement is applied only when it names exactly the open
panels; otherwise the open panels get the default arrangement. **Reset Panel
Layout** rearranges the open panels into the default columns and restores the
300 px height.

**Per universe.** Each universe keeps its own layout, stored under
`screener.s4.panels.by_universe` (`POST /screener/config` action `panel_layout`
with `universe`). Each entry is validated exactly as above. `GET /screener/config`
returns `panel_layouts` keyed by universe. A universe with no layout of its own
reads the legacy global `screener.s4.panels` record (then the default), so an
existing layout carries over to every universe until that universe saves one.
Switching universe flushes the pending write under the previous universe and
remounts the dock on the new universe's layout. The last-used screen (columns,
view, sort) is kept per universe the same way (`screener.s2.last.by_universe`,
returned as `last_by_universe`). Filters still clear on a universe switch.

**Containment.** Each panel has an error boundary. A new selection or
universe clears it, and Retry resets that panel's cached screener queries.
The dock as a whole has one too, offering Retry and **Reset layout** (drops
only this universe's saved arrangement). Lazily loaded panel code that fails
to load is imported again on Retry, never in a loop. A response that fails
schema validation (`SchemaMismatchError`) is shown as a UI/API version skew,
not a provider outage.

Saved screens are unchanged. A saved screen is a scanning configuration; the
panel layout is not stored in it, so loading a screen never rearranges the
workstation.

## Selected-instrument authority

Every panel follows the Screener's one selected row; no panel has its own
ticker picker. The dock waits for a selection to settle for 250 ms before
requesting anything, so arrowing past rows does not subscribe to each row.
Queries are keyed by instrument, requests carry an `AbortSignal`, responses for
another instrument are rejected by an identity guard, and a panel renders data
only when its instrument equals the current selection. A slower AAPL response
can therefore never appear under NVDA, and each panel shows its own loading or
degraded state.

## Subscriptions

`POST /screener/panels {client_id, instrument_id, panels}` turns the selected
instrument and the open live panels into subscriptions on the runtime's
`LiveSubscriptionManager`. Each open panel is one logical consumer
(`screener-panel:<client>:<panel>`), so the manager's reference counting does
the sharing:

- Order Flow + CVD → one `US_EQUITY_TICKS` provider subscription, two consumers.
  Closing Order Flow keeps it for CVD; closing CVD releases it.
- Level 2 → `US_EQUITY_DEPTH` only while it is open.
- Charts and Futures Context acquire nothing here; they reuse the S3 bar and
  futures services.
- Changing the selection releases the old instrument's panel consumers and
  acquires the new one's. Clearing the selection releases everything.

Order flow does not need an L1 subscription: Moomoo supplies its own ticker
direction, and the selected row already holds the S1 viewport quote. The client
heart-beats every 15 s while it holds anything; the backend releases a client
after 45 s of silence, and the page releases on unmount and `pagehide`.

A panel in a background Dockview tab keeps its subscription (one or two slots
for one instrument, so continuity is cheap) but stops polling until shown.
Closing a panel releases its unique capability.

**Provider limits.** OpenD reported a 100-subscription quota (each code and
subtype is one slot) and refuses an unsubscribe within one minute of the
subscribe ("Minimum subscription duration is 1 minute", observed). The push
feed now keeps a slot whose unsubscribe OpenD refused and retries every 5 s;
before S4 it forgot the slot, which leaked provider quota on every fast
selection change. Subscribe refusals are recorded per code and subtype, retried
every 15 s instead of every sync tick, and reported by the panels. The
specialist service lets at most six distinct instruments occupy panel slots,
counting instruments still inside the one-minute provider hold; a seventh is
`SUBSCRIPTION_BUSY` until a hold expires. With the S1 viewport (≤ 32) and S3
bars (≤ 12), S4 adds at most 12 slots.

## Order Flow

`screener-specialist/1.0.0`, panel `order_flow`: state, reason, provider,
entitlement, the captured window, the latest trade's event and receipt times, a
summary, and the newest 100 trades.

Trades come from the runtime's per-instrument tape, a deque bounded at 500
trades (the oldest roll off). The window is anchored at the later of the moment
the trade subscription became active and the latest provider (re)connect, so
trades retained from an earlier subscription or connection never join the
window. Trades are de-duplicated by provider sequence and ordered by event time
(pushes can arrive out of order). If the buffer rolled over inside the window,
the basis is `LAST_N_CAPTURED` ("Last 500 captured trades"); otherwise
`SINCE_SUBSCRIPTION`.

Summary: trade count, inferred-buy, inferred-sell, and unknown volume, net
signed volume, classified share of volume, trades per minute only when the
window spans at least one minute, and a large-print threshold of 10× the median
trade size when at least 20 trades exist. The tape shows event time (ET),
price, size, side, and the provider trade condition only when supplied.

**Aggressor semantics.** Each trade is `NATIVE`, `INFERRED`, or `UNKNOWN`.
Moomoo's `ticker_direction` is the provider's own classification, not an
exchange aggressor flag, so it is `INFERRED` with method
`PROVIDER_TICKER_DIRECTION` and shown as "Inf. Buy"/"Inf. Sell". `NATIVE` is
reserved for exchange-native sides (no current provider supplies them).
Neutral or missing directions are `UNKNOWN`. The panel states that direction is
inferred and is not a known buyer or seller.

## CVD

CVD reuses `compute_cvd_series` over the same window: each classified trade
contributes its signed size, an unknown trade contributes zero and counts
against coverage. The payload is marked `derivation: DERIVED`. The panel shows
the current value with its anchor ("CVD since subscription 09:21:56 ET", or
"CVD over last 500 captured trades" — never "session CVD", because the system
holds only trades captured since subscription), the net delta of the last 60 s
of event time, the classified share of volume (a warning below 70 %), the
methods, a baseline chart at one point per second, and a text summary for
screen readers. It adds no slope, forecast, or recommendation.

## Level 2

`panel: level2` is built from the runtime's canonical `IncrementalOrderBook`,
never from raw provider rows. Observed Moomoo semantics: `SubType.ORDER_BOOK`
pushes full MBP snapshots (10 levels per side on this account), which the
engine applies with `replace_from_snapshot` — the prior book is cleared and
rebuilt atomically; a malformed level invalidates and clears the book. No
incremental engine is needed for this provider.

The projection returns bids (descending) and asks (ascending) with size and
cumulative size (up to 20 per side), best bid/ask, spread, mid, spread in basis
points, completeness (`PROVIDER_MBP_TOP_N`, level counts, venue scope
`PROVIDER_UNSPECIFIED`), freshness, event and receipt times, and quality flags.
States:

| State | Rule |
|---|---|
| `INVALID` | engine validity is not `VALID`, the book is crossed or locked, or a level has a non-positive price or size; no levels are shown |
| `CONNECTING` / `SESSION_CLOSED` | no book received since this subscription and connection (`AWAITING_BOOK_SNAPSHOT`) |
| `SESSION_CLOSED` | the US session is closed; the last captured book is shown dimmed and labelled |
| `STALE` | no book receipt within the TTL; shown dimmed with its age |
| `PARTIAL` | one side is empty (`ONE_SIDED`) |
| `CURRENT` | valid, two-sided, fresh |

The TTL is the canonical depth freshness policy (`moomoo_l2`, 5 s, configurable
through `IMP_MOOMOO_L2_MAX_AGE_MS`) applied to the provider receipt time. A book
received before the current subscription or provider connection is never shown,
so an old book cannot survive a reconnect or a return to an instrument.

**Displayed-liquidity imbalance** for the top N levels (N = 5 and 10) is
`bid_size / (bid_size + ask_size)` over the resting sizes of the top N levels on
each side, with the signed form `(bid − ask) / (bid + ask)`; when a side has
fewer than N levels the count is shown. It describes resting orders, not
executed aggression, and is never called buying pressure. The ladder is a
semantic table with row headers, opens centred on the spread, and draws a size
bar proportional to the largest displayed level.

## Charts

`GET /screener/chart` is `ScreenerPreviewService.chart`: the same
`CurrentBarsService` and `AUTO_SR_V1` level cache as the Quick Preview, without
Why or news. Both panes therefore use one provider `K_1M` subscription per
instrument and can never disagree about bars or zones. The panel offers 1m, 5m,
15m and Extended/RTH — exactly the S3 contract — and draws candles, volume, the
nearest support and resistance bounds (via the shared `srClassify`), and the L1
price as a solid line only when the quote is live. Otherwise the text states the
last completed bar close and its time; a bar close is never shown as the current
price. Bar state, last bar, and level calculation time are shown. Stale or
unavailable bars produce no levels.

## Futures Context

`GET /screener/futures-context` returns `FUTURES_CONTEXT_MAP_V1` from the same
`FuturesContextService` as S3, including its expiry validation (an expired main
contract is `EXPIRED`, never current) and five-minute refusal cache. Each
contract shows its code, relationship type and reason, price and change only
when a current quote exists, provider and quote age, and last trade date; a
missing price says why ("Price unavailable — No futures quote entitlement"). The
causal note closes the panel. S4 adds no futures universe.

## States and clocks

Every panel has explicit no-selection, loading, and failure states, plus the
backend states `CURRENT`, `SESSION_CLOSED`, `STALE`, `PARTIAL`, `INVALID`,
`DISCONNECTED`, `NOT_ENTITLED`, `UNAVAILABLE`, `CONNECTING`, and
`SUBSCRIPTION_BUSY`. A closed market is `SESSION_CLOSED`, distinct from a
provider problem. `NOT_ENTITLED` requires an observed refusal: a fresh probe
that says so, or the provider refusing the subscribe. A stale or missing
capability probe is `entitlement: UNVERIFIED` and is stated in the panel; the
provider's own answer decides. A runtime fed by a fixture instead of a current
provider is `UNAVAILABLE` (`NO_CURRENT_FEED`).

Each panel keeps its own clock: Order Flow and CVD the latest trade's event and
receipt times, Level 2 the book's event and receipt times with its TTL, Charts
the bar receipt and last bar, and Futures each contract's quote time. There is
no shared "live" timestamp.

Each panel renders inside its own error boundary: a failing panel shows a retry
message while the table, the Quick Preview, and other panels continue.

## Workbook

`WORKBOOK_SURFACE_ABSENT`: the S3 branch has no Workbook route or surface, so
S4 has no Workbook launcher or panel.

## Validation evidence

Measured on Sunday 2026-09-27, market closed, real Finviz (4,288 rows) and
OpenD:

- Opening Order Flow, CVD, and Level 2 for NVDA produced exactly two OpenD
  subscriptions account-wide (`TICKER US.NVDA`, `ORDER_BOOK US.NVDA`); the trade
  key had two consumers. Closing Order Flow and Level 2 kept `TICKER` for CVD;
  OpenD released `ORDER_BOOK` on the push feed's retry.
- Arrowing through ten rows subscribed only the settled row (`TICKER` and
  `ORDER_BOOK` for SMCI); total OpenD usage was 30 of 100 including the S1
  viewport and S3 bars. After the panels closed, only viewport quotes remained.
- With the capability probe stale since 2026-09-15, panels report
  `SESSION_CLOSED`, entitlement unverified, and no captured trades or book.
- With all five panels polling each second, table DOM mutations were identical
  with the dock open or closed (three bursts per 9 s, the S1 three-second quote
  refresh); panel updates caused none.
- Warm panel open ≈ 26 ms (dev server). Dockview and panel modules are
  requested only on the first launcher click.
- Visual acceptance at 1920×1080, 2560×1440, and 1100×800: no panels, one
  panel, five panels, a tabbed group, widened and moved panels, reload and
  in-app return restoring the arrangement, and reset. Populated tape, CVD,
  ladder, and a priced future were inspected through a test-only in-page fetch
  interception; no production path carries those values.

## Tests and limits

Backend: `tests/platform/test_screener_s4.py` covers demand and reference
counting, ticker switching, client expiry, the busy bound, route policy,
aggressor states, tape summary and ordering, duplicates, large prints, window
anchoring and buffer rollover, session/stale/disconnected/entitlement/refusal
states, fixture-fed runtimes, CVD arithmetic and anchors, reconnect resets,
depth sorting, cumulative sizes, imbalance, TTL, partial, crossed and malformed
books, atomic snapshot replacement, reconnect hiding, push-feed unsubscribe
retry and subscribe back-off, layout validation and fallback, and chart/futures
reuse. UI: `panels/ScreenerPanels.test.tsx` plus the S1–S3 Screener tests.

Limits: order flow and depth need the live runtime with a current Moomoo feed.
Windows cover trades captured since subscription (at most 500); there is no
session-anchored CVD. Moomoo depth is 10-level MBP without venue identity and is
not the consolidated market. Trade direction is provider-inferred. Dock
rearrangement by drag and sash resizing are pointer-only in Dockview Community;
the header buttons are the keyboard path. Futures prices are unavailable on the
current account.
