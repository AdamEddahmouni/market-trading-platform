# TradingView validation — L1VolumeBubble

This donor artifact is a single Pine v6 indicator. There is no Python runtime to
test in-repo; validation happens in TradingView.

## Import steps

1. Open [TradingView](https://www.tradingview.com/) and sign in.
2. Open any liquid equity chart (for example NVDA or SPY) on a 1-minute timeframe.
3. Open **Pine Editor** (bottom panel) → **Open** → **Import from file**.
4. Select `Custom volume bubble 1m1s l1.pine` from this folder.
5. Click **Add to chart**.

## What to verify

- Volume-delta bubbles appear when z-score exceeds the default 2σ threshold.
- Bubble color reflects buy/sell delta direction.
- Optional absorption markers render without script errors.
- Alerts fire when configured (chart must stay open for alert delivery).

## Limitations

- Bubble granularity depends on your TradingView plan and the symbol's
  lower-timeframe volume-delta availability; this is not a full L1 quote feed.
- Treat the script as a visualization reference only for platform porting work.
