# G9 Current-State Matrix — IBKR Tick-by-Tick / CVD / Entitlement

**Cutoff:** 2026-09-08 (G9 increment)  
**Baseline FULL before G9:** 4221 / 48 / 0 / 0

## Archaeology summary

| Area | Pre-G9 | Post-G9 |
|------|--------|---------|
| `reqTickByTickData` / tick-by-tick transport | **Absent** | Implemented in `tools/ibkr/observational_transport.py` |
| IBKR trade → CVD path | **Absent** (L1 last tick ≠ trade tape) | `subscribe_trades` → `on_tick_by_tick_all_last` → `apply_classified_trade` → `build_cvd_payload` |
| `ClassifiedTrade` contract | Exists (G3) | Reused; IBKR facts via `TradePrintFacts` + `trades.classify_trade_print` |
| Aggressor NATIVE from IB TBT | Not verified | **Not claimed** — IB `TickAttribLast` has no verified aggressor side |
| Aggressor INFERRED | Lee-Ready path exists | Wired with canonical L1 quote context (same provider, freshness gate) |
| `US_EQUITY_TICKS` / lane `CAP_TRADES` | Moomoo only | IBKR `IBKR_TRADES` registered + runtime alias to `CAP_TRADES` |
| Capture/replay | L1 + depth only | TRADE callback kind added |
| Entitlement readiness | L1/L2 | L1/L2/TRADES diagnostics |
| Live canary | Not run | **Not run** — `LIVE_PROVIDER_UNVERIFIED` retained |
| src→tools boundary | Green | Preserved (no src import of tools.ibkr) |

## Key symbols

| Symbol | Path |
|--------|------|
| `TradePrintFacts` | `providers/ibkr_observational/contracts.py` |
| `classify_trade_print` | `providers/ibkr_observational/trades.py` |
| `subscribe_trades` / `on_tick_by_tick_all_last` | `providers/ibkr_observational/adapter.py` |
| `req_tick_by_tick_data` | `tools/ibkr/observational_transport.py` |
| `apply_classified_trade` | `market_data/observational_state.py` |
| `IBKR_CAPABILITY_TRADES` | `providers/ibkr_observational/capability.py` |

## BL backlog posture (G9)

| Backlog | Status | Evidence |
|---------|--------|----------|
| BL-0301 | **PARTIAL** | Contract resolution + TBT subscribe path; account/secdef/bars unchanged |
| BL-0303 | **PARTIAL** | Book freshness policy exists; live depth TTL admission not expanded in G9 |
| BL-0304 | **COMPLETE (offline/replay)** | IBKR classified tape → canonical store → G3 CVD; live evidence separate |
| BL-0305 | **PARTIAL / BLOCKED_BY_LIVE_EVIDENCE** | Offline lifecycle + entitlement diagnostics; no live canary run |

## Live provider

**LIVE_PROVIDER_UNVERIFIED** — IMP_IBKR_LIVE not enabled for bounded canary in this environment; no TWS session evidence collected.

## Provider callback verification

- Request: `reqTickByTickData(reqId, contract, tickType, numberOfTicks, ignoreSize)` — tickType `"AllLast"` for trade tape
- Callback: `tickByTickAllLast(reqId, tickType, time, price, size, tickAttribLast, exchange, specialConditions)`
- Cancel: `cancelTickByTickData(reqId)`
- Source time: provider `time` (seconds) → ns at transport boundary when supplied
- No stable provider event id — dedup uses local composite `replay_dedup_key` only

## G9 test inventory

| Module | Tests |
|--------|------:|
| `tests/providers/test_g9_ibkr_trade_tape.py` | 14 |
| `tests/order_flow/test_g9_ibkr_cvd.py` | 8 |
| `tests/market_data/test_g9_live_canary_gate.py` | 2 |
| `tests/ibkr/test_g9_tick_by_tick_transport.py` | 3 |
| `tests/providers/test_g9_performance.py` | 2 |
| **Total focused G9** | **29** |
