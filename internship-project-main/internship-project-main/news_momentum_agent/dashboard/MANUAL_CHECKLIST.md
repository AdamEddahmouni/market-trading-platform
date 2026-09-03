# Dashboard manual checklist

Read-only monitor — does **not** approve trades or write agent state.

## Launch

```bash
cd news_momentum_agent
./venv/bin/python -m streamlit run dashboard/app.py
```

## Header

- [ ] Horizon box shows current mode (`range` / `deadline` / `same_day`) with plain-English exit rules
- [ ] Gate chips match `settings.json` (`path_a2_auto_execute` off, etc.)
- [ ] Agent RUNNING/STOPPED matches `state/agent.pid`
- [ ] EOD verdict bar appears when `eod_summary_*.json` exists

## Tabs

- [ ] **Overview** — hold-time buckets / rejection codes from latest EOD; Path A by-path counts; Path B consecutive counter
- [ ] **Portfolio** — TGB & NWL open (if still held); COIN not open; COIN close shows ~48s hold + `stop_loss`
- [ ] **Discovery** — `alert_reason` chips (`stocktwits` / `news_catalyst` / `volume_spike`); by-path metrics
- [ ] **Trade Log** — default hides LOG; toggle Include LOG; filter by `decision_reason_code`; Path A.2 badge on `news_catalyst`
- [ ] **Diagnostics** — Path B stats, quote pauses, flip audit, liquidity subreasons with values, near-miss bands with **N**, solicitation log count
- [ ] **Research** — miner headline (discovery vs OOS survivors); labeled historical-only
- [ ] **Options** — engine signals table + feature breakdown
- [ ] **Near-Expiry** — `odte_watchlist` with horizon caption (not “0DTE-only”)
- [ ] **Quadrant** — view-only pending list; **no** Approve/Execute buttons

## Negatives

- [ ] Sidebar does not write `settings.json`
- [ ] Missing state files show empty/missing panels (no crash)
- [ ] Stale banner appears if health age is large while agent stopped

## Automated

```bash
./venv/bin/python -m pytest dashboard/tests/test_loaders.py -q
```
