# FuturesX notes

## Scope and structure

`Eric_futuresX-main/futuresX-main` is a futures Level-2 experimentation project.
It combines an Interactive Brokers (IBKR) client, a PyQt order-book window,
CSV/SQLite market-depth capture, historical backtests, a Topstep API experiment,
and bundled ES/SPY/Databento-style data. Its README directs users to TWS in paper
mode; it explicitly warns that take-profit and stop-loss orders in the live
trader do not currently execute properly.

## Components

- `src_client/workspace/main.py` starts the desktop UI; `gui.py` provides
  `OrderBookWindow`; `data_collecter.py` is a `QThread` collector.
- `ibkr_manager.py` contains the main `IBApp` (`EClient`/`EWrapper`) and depth,
  position, market/limit, and market/limit bracket-order wrappers.
- `ibkrdata.py` (`DataManager`) and `utils.py` manage IBKR contracts. The latter
  finds index-futures expiries (including the third-Friday helper).
- `historical data/` contains level-2 parsers, SQLite log/cleanup/split tools,
  and several backtest variants. `live_trader.py` contains the live loop.
- `topstep.py` exposes authentication, account/contract lookup, market order,
  historical-bar, and New-York-to-Zulu time conversion functions. `topstep_orb.py`
  implements an opening-range-breakout (ORB) test and simulated exits.
- `ib_course/` is a set of IB API learning examples: contracts, historical/live
  data, orders, brackets, account data and head timestamps.
- `charts/` and `index.html` are chart experiments; `archived/` is retained
  legacy work. `market_depth_rth_before_june9.db`, ES/SPY CSVs, backtest trade
  CSVs and timestamped mid-price files are supplied research artifacts.

## Trading/data ideas found

- Level-2 ladder/order-book visualization and periodic snapshots for replay.
- Bracket-order abstraction: entry plus take-profit and stop-loss children.
- ORB: establish an opening range, enter on breakout, then simulate a stop and
  target via `simulate_exit`.
- Historical backtests parse serialized bid/ask ladders and restrict tests with
  `is_active_hour`; risk/reward variants are present (`backtest_rr.py`).
- Contract selection is calendar-driven; data sources include IBKR and bundled
  ES 1-minute OHLCV / SPY data.

## Tools and dependencies

IBKR TWS API (`ibapi`), PyQt6, pandas/CSV/SQLite, Topstep endpoints, and browser
chart packages (`lightweight-charts`, `fancy-canvas`). Operational prerequisites
are TWS/API activation plus CME ES Level-2 data. The README’s primary launch
commands are `workspace/main.py`, historical `backtest_main.py`/`backtest_main2.py`,
and `live_trader.py`.

## Risks/limitations

- The code includes order-placement wrappers; broker connection and account mode
  must be controlled before running it.
- Bracket TP/SL **transmit chain** was corrected 2026-08-15 in `ibkr_manager.py`
  (parent `transmit=False`, stop-loss child `transmit=True`; no duplicate parent
  submit). **Paper TWS validation is still required** before trusting
  `live_trader.py` for risk-managed exits.
- `data_collecter.py` now writes depth only during RTH (9:30–16:00 ET).
- Backtest CSV/data coverage and ladder parsing rules should be verified before
  interpreting results; no performance claim is documented.

## Windows baseline (2026-08-14)

| Check | Result |
|---|---|
| `pip install pandas matplotlib pytz` | Pass |
| Bundled CSV/SQLite backtests (`backtest_main.py`, `backtest_main2_csv.py`) | Blocked — large data files are Git LFS pointers only (not pulled in this zip copy) |
| Offline smoke (`scripts/smoke_offline_backtest.py`) | Pass — synthetic `es_level2_data.csv` runs `backtest_main2_csv.py` end-to-end |
| `live_trader.py` / TWS | Not run (per plan — TP/SL defect) |

To obtain real bundled data, clone the FuturesX repo with Git LFS and run `git lfs pull`, then run backtests from the repo root so `market_depth_rth_before_june9.db` and `es_level2_data.csv` resolve correctly.

## Windows baseline (2026-08-15)

| Check | Result |
|---|---|
| `scripts/smoke_offline_backtest.py` | Pass — synthetic ES L2 CSV, backtest completes (0 trades on synthetic ladder) |
| `git lfs pull` | Not available — workspace copy is not a Git repository (zip extract) |
| Real ES/session data | Still blocked — requires cloning FuturesX with Git LFS |
| `live_trader.py` | Not run (requires manual TWS paper re-validation after bracket fix) |

## Windows baseline (2026-08-16)

| Check | Result |
|---|---|
| `tests/test_bracket_orders.py` | Pass — 2/2 unittest (transmit flags, parent linkage) |
| `scripts/smoke_offline_backtest.py` | Pass — synthetic ES L2 CSV backtest completes |
| Bracket fix in `ibkr_manager.py` | Applied — paper TWS validation still manual |
| `data_collecter.py` RTH gate | Applied — depth capture 9:30–16:00 ET only |
| Real ES/session data | Still blocked — workspace copy is not a Git/LFS clone |

## Windows baseline (2026-08-17) — futures lane kickoff

| Check | Result |
|---|---|
| `git lfs pull` | Not available — `Eric_futuresX-main/futuresX-main` is not a Git repository (zip extract) |
| `es_level2_data.csv` | Git LFS pointer only (`size 231641168`; oid present, bytes absent) |
| `scripts/smoke_offline_backtest.py` | Pass — synthetic ES L2 CSV, 0 trades on flat ladder |
| `tests/test_bracket_orders.py` | Pass — 2/2 after `pip install ibapi` in donor venv |
| `scripts/bridge_server.py` | Added — read-only HTTP bridge on `:8788` (health, depth, session) |
| Real ES/session backtests | Blocked — requires Git LFS clone of FuturesX repo |

### Paper TWS validation checklist (`live_trader.py`)

Manual validation required before trusting risk-managed exits in paper mode:

1. Start TWS in **paper** mode; confirm API socket enabled (port 7497 for paper TWS).
2. Verify CME ES Level-2 data entitlement is active on the paper account.
3. Run `live_trader.py` from `src_client/workspace/historical data/`.
4. Confirm depth subscription populates bids/asks in console output.
5. Wait for imbalance signal; confirm parent market order is placed.
6. Confirm take-profit (limit) and stop-loss (stop) child orders appear in TWS with correct `parentId` linkage.
7. Confirm stop-loss child has `transmit=True` (last child in bracket chain).
8. Cancel all orders and disconnect cleanly (`KeyboardInterrupt` path).
9. Record pass/fail and TWS version in this table.

| Step | Status |
|---|---|
| Paper TWS validation (2026-08-17) | **Not run** — requires manual operator with TWS paper + ES L2 |

## Git LFS data unblock (when repo is a real clone)

Zip extracts of this workspace cannot run `git lfs pull`. To obtain bundled ES/session bytes:

```powershell
git clone <futuresx-repo-url>
cd futuresX-main
git lfs pull
```

Then run backtests from the repo root so `es_level2_data.csv` and `market_depth_rth_before_june9.db` resolve to real files.

## IMP integration launcher

From the market-trading-platform workspace root:

```powershell
.\tools\run_donor_demos.ps1 -Start futures
```

Starts the read-only HTTP bridge on `:8788` for IMP `/explore/futures` and `/workspace/ES/futures` live snapshots. Does **not** start `live_trader.py`.
