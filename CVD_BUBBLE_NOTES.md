# Trading CVD Bubble notes

## System

`tradingCVDBubble-main (1)/tradingCVDBubble-main` is a Dash/Plotly measurement
dashboard (port 8050) backed by local MongoDB. IBKR supplies trades, quotes and
Level-2 depth; FinViz Elite optionally supplies consolidated minute bars. The
pipeline is on-demand per searched ticker: tick/quote classification → 1-second
bars and L2 snapshots → MongoDB → materialized tier rollups → chart/heatmap.
Demo data is NVDA, 2026-07-22, in `demo_data/` and must be loaded into MongoDB.

## Core formulas and classifications

- **Lee–Ready-style aggressor rule** (`cvd/aggressor.py`): trade at/above ask =
  buyer initiated; at/below bid = seller initiated; inside quote uses tick rule;
  unchanged price inherits the prior non-zero direction. Delta is buy volume
  minus sell volume; CVD is cumulative delta.
- **BVC historical estimate** (`history/bvc.py`):
  `buy_volume = V × Φ(ΔP / σ)` and `sell_volume = V − buy_volume`, where `Φ` is
  the normal CDF. It fills bar-only periods and is marked estimated.
- **OHLC/wick decomposition** (`cvd/calculator.py`): decomposes candle volume
  into directional pressure when classified ticks are unavailable; quality flags
  preserve that distinction.
- **Order Flow Imbalance** (`cvd/ofi.py`), following Cont–Kukanov–Stoikov,
  accumulates best-bid/best-ask price/size event changes.
- **L2 metrics** (`level2_webapp/data_provider.py`): order-book imbalance,
  weighted liquidity (with decay), center of gravity, and persistent large-wall
  support/resistance selection.
- Closing-auction detection neutralizes an undirected Market-on-Close print
  (`buy=sell`, `delta=0`) so a single auction does not dominate CVD.

## Storage and components

- `ibkr/dynamic_collector.py` is the active combined collector; it probes ports
  7497, 4002, 7496, 4001. It retains recent tickers/depth subscriptions.
- `history/schema.py`, `store.py`, `rollup.py`, `serve.py`, and `session_grid.py`
  use 1sec → 1min → 30min → 1day tiers, watermark rollups, source/quality ranks,
  cache invalidation, and session-grid gaps. Quality-guarded upserts prevent
  estimates overwriting tick-derived data.
- `cvd/calculator.py` builds CVD/pressure frames; `visualizer.py` builds candles,
  CVD lines, bubbles, pies, source shading, and L2 heatmaps. `app.py` is Dash.
- `scripts/` covers demo load/export, coverage/latency, closing-auction checks,
  classification tests and price/CVD correlation research.

## Requirements and stated limitations

Requires Python 3.11–3.14 and MongoDB on `localhost:27017`; live mode also needs
IBKR Gateway/TWS, API permission and data subscriptions. FinViz credentials are
optional. IBKR historical/live stream coverage is documented as roughly 7–14% of
consolidated volume (IEX-biased in backfill), so FinViz bars rescale volume and
estimated regions are intentionally shaded. Depth is roughly 20 SMART levels,
not a full exchange book; depth and auction codes have ticker/venue limitations.
The project calls itself a measurement layer, not a short-squeeze strategy.

## Windows baseline (2026-08-14)

| Check | Result |
|---|---|
| `pip install -r requirements-demo.txt` | Pass |
| `python -m scripts.demo_dataset load` | Pass — 79,027 docs loaded (NVDA demo day 2026-07-22) |
| Dash `:8050` | Pass — HTTP 200 |
| MongoDB | Requires local MongoDB (`docker run -d --name cvd-mongo -p 27017:27017 mongo:7`) |

**Demo walkthrough:** search `NVDA`, jump to `2026-07-22 10:00` ET, set timeframe `1min`, L2 depth `20 levels`. Step 3 (jump to date) is required — default live view shows an empty chart.

## Windows baseline (2026-08-15)

| Check | Result |
|---|---|
| `scripts/offline_demo_bundle_check.py` | Pass — all bundled demo files match manifest (NVDA 2026-07-22) |
| `docker start cvd-mongo` | Pass — MongoDB 7 on `localhost:27017` |
| `python -m scripts.demo_dataset load` | Pass — 79,027 docs (66,548 candles + 12,479 L2 snapshots) |
| `pip install -r requirements-demo.txt` in `.venv` | Pass |

## Windows baseline (2026-08-16)

| Check | Result |
|---|---|
| `docker start cvd-mongo` | Pass — MongoDB 7 on `localhost:27017` (Docker Desktop required) |
| `python -m scripts.demo_dataset load` | Pass — 79,027 docs (66,548 candles + 12,479 L2 snapshots) |
| `python -m scripts.offline_demo_bundle_check` | Pass — all bundled gzip files match manifest |
| `python -m scripts.inspect_auction_conditions --ticker NVDA --date 2026-07-22` | Pass (runs) — FinViz demo bars have empty `special_conditions` at close; 0/610 bars match hard-wired auction codes `'6'`/`'M'` (live IBKR ticks required for code verification) |
| `python -m scripts.coverage_and_latency --tickers NVDA` | Expected fail on demo-only — no `raw_ticks` for IBKR-vs-FinViz coverage concat (`ValueError: No objects to concatenate`) |
| `python -m scripts.validate_moc` | Expected fail on demo-only — script queries timeframe `i1` (not present); demo uses `1min`/`1sec`/`30min`/`1day` |
| `python -m scripts.backtest_correlation` | Expected skip — all 9 grid tickers lack `raw_ticks` (live collector only) |
| `python -m scripts.backtest_correlation_wick` | Expected skip — demo has no `ibkr_hist` 1sec backfill rows |
| Extra deps for validation scripts | `matplotlib`, `ib_async` (not in `requirements-demo.txt`; needed for coverage/auction scripts) |
| `scripts/run_demo_validation.ps1` | Added — one-command MongoDB demo validation runner |

**Demo walkthrough unchanged:** search `NVDA`, jump to `2026-07-22 10:00` ET. Correlation and MOC validation scripts target live-collected tick/backfill data, not the bundled FinViz demo slice alone.
