# L1 Volume Bubble notes

`L1VolumeBubble-main (1)/L1VolumeBubble-main` contains a minimal README and one
TradingView Pine v6 source file: `Custom volume bubble 1m1s l1.pine`. It is a
chart-indicator project, distinct from the Python applications. It imports
`TradingView/ta/11` and requests lower-timeframe volume delta (default 1 second)
to draw bubbles over the current chart timeframe.

## Calculation logic

- Signal is either volume delta `deltaClose − deltaOpen` or signed regular
  volume (`+V` if close ≥ open, otherwise `−V`).
- It computes `absoluteSignal = |signal|`, its SMA and sample standard deviation
  over a configurable 60-bar (minimum 20) lookback, then
  `z = (|signal| − mean(|signal|)) / stdev(|signal|)` (zero when stdev is zero).
- Adaptive mode triggers a bubble at `z ≥ 2.0` by default; fixed mode triggers
  at `|signal| ≥ 200`. The script calls 2σ roughly the top 5% in its tooltip.
- A lower-timeframe VWAP anchors a triggered bubble:
  `Σ(lower_close × lower_volume) / Σ(lower_volume)`; if unavailable it falls
  back to OHLC4. Delta dominance is `|signal| / barVolume`.
- Optional absorption means an unusual signal with candle body less than
  `absorption_ratio × average_body` (default ratio 0.6), a high-effort/small-
  result heuristic.

## Presentation and alerts

Bullish/bearish colors, dark/light themes, glow, font, opacity, and show/hide
controls are configurable. Bubble size is S/M/L based on threshold exceedance
(adaptive: +1σ/+2σ; fixed: 4×/6× threshold); adaptive opacity uses `100 − 20z`.
On confirmed bars, optional alerts emit an unusual-volume/delta message or an
absorption message. TradingView must create an alert using “Any alert() function
call.”

## Practical handling

- Import/open the `.pine` file in TradingView’s Pine editor; it does not need a
  Python environment, database, broker client, or server.
- Treat it as a visualization/indicator artifact, not an execution engine.
- Pine calculations operate on the chart feed and timeframe supplied by
  TradingView; lower-timeframe availability, volume-delta support, and historical
  granularity determine what it can show. It is not a full Level-1 quote feed.

No accompanying methodology, test evidence, API configuration, or validated
strategy documentation was supplied beyond the Pine implementation itself.
