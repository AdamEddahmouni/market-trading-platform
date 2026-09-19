# IMP simulator drawdown wiring — read-only review (Lane C)

**Hypothesis:** `LANE-E-HYP-SIMULATOR-DRAWDOWN-WIRING-V1`  
**Source finding:** `LANE-E-FND-019`  
**Reviewed implementation (uncommitted):** worktree `.worktrees/simulator-drawdown-wiring-v1`, branch `research/simulator-drawdown-wiring-v1`  
**Lane C policy:** no competing rewrite in this worktree; no v3 manifest backfill.

## Status (Lane C — Sep 18)

| Gate | Value |
|------|-------|
| `SPEC_READY` | **YES** (companion spec in drawdown worktree: `IMP_SIMULATOR_DRAWDOWN_WIRING_V1.md`) |
| `IMPLEMENTATION_READY` | **YES** (code + unit/integration tests present uncommitted on drawdown branch) |
| `EXECUTED` | **NO** (not merged; no NEW experiment hash run on OpenD corpus today) |

## Observed gap on `main` (v3)

`run_historical_development_simulator_research` sets:

- `max_drawdown` ← `risk_result["portfolio"]["max_drawdown"]`
- `max_drawdown_source` ← `RISK_PORTFOLIO_INHERITED`

`run_risk_simulation_from_signal_interpretations` does not populate `portfolio.max_drawdown`, so baseline pack v3 manifests show `drawdown: null` despite non-zero validate `net_pnl`. This is a **reporting gap**, not evidence of zero risk.

## Proposed wiring (reviewed read-only)

| Component | Assessment |
|-----------|------------|
| `simulator_drawdown.py` | Clear helpers: mark at/before time, gross unrealized, peak-to-trough, version constants `simulator-research/net-mtm-drawdown/1.0.0` |
| `aggregate_fill_economics` | Builds `net_mtm_curve` starting at `0.0`, appends point after each fill, reconciles terminal net with `NET_PNL_TOLERANCE` |
| `simulator.py` | Surfaces `max_drawdown`, `max_drawdown_source`, `drawdown_metrics_version`, `equity_curve_point_count` from execution economics instead of empty risk portfolio |
| `metrics.py` / baseline pack | Unchanged mapping `drawdown` ← `max_drawdown` (per drawdown worktree doc) |

## Equity curve definition (reviewed)

- **Basis:** cumulative **net** mark-to-market PnL in native currency (aligned with research `net_pnl` units), **not** total cash equity (`initial_cash_minor` excluded).
- **Source token:** `EQUITY_CURVE_NET_MTM`
- **Samples:** after each fill at bar close on or before `fill_time`; terminal sample uses same end-of-run mark as economics summary.
- **`ACCOUNTING_VERSION`:** remains `simulator-research-fill-economics/3.0.1` (drawdown is additive metadata, not an accounting version bump in the reviewed patch).

## Timestamp ordering

- `mark_price_minor_at_or_before` filters bars with `available_time <= at_time_ns` — causal, no lookahead.
- Fill loop uses `fill_time` from fill record; consistent with simulator fill bar `available_time`.
- Terminal mark uses last bar on full event path (same as existing `_mark_price_minor_from_events`).

## Realized / unrealized / costs on the curve

At each fill sample:

- `gross_market_realized_minor` = ledger post-fee realized + policy fees added back (market realized, consistent with terminal gross split).
- `gross_unrealized_minor` from position shares, basis, and mark at/before fill.
- `net_mtm_pnl_native` = `(gross_realized + gross_unrealized) − (slippage_total + policy_fees_native)`.

Slippage accumulates monotonically across fills — correct for cumulative net MTM.

## Drawdown formula

`max_peak_to_trough_drawdown`: running peak, maximum `peak − value`. Standard peak-to-trough on the net MTM curve. Empty curve → `0.0`.

## Position lifecycle

Curve points tied to fill events; open-position loss between fills only appears when mark at next fill (or terminal) moves — **documented limitation v1**: intra-hold bar path not walked. Open-loss test in `test_simulator_drawdown_wiring_v1.py` shows drawdown > 0 with mark move after entry.

## Inherited risk-state

`coverage` still from `RISK_PORTFOLIO_INHERITED` (unchanged in reviewed `simulator.py` diff). Only drawdown sourcing moves to fill economics.

## Tests reviewed

`tests/platform/test_simulator_drawdown_wiring_v1.py`:

- Peak-to-trough unit cases
- No fills → zero drawdown + version tokens
- Open MTM loss → drawdown matches unrealized loss magnitude
- Closed losing round trip → positive drawdown with negative net
- Integration: simulator returns non-null `max_drawdown` and `equity_curve_point_count > 1`

## Disposition (Lane C)

| Action | Owner |
|--------|-------|
| Merge drawdown wiring | drawdown worktree / separate PR — **not** Lane C |
| v4+ experiment with NEW hash to observe non-null drawdown on OpenD | deferred — **EXECUTED=NO** today |
| Backfill v3 JSON manifests | **FORBIDDEN** |

## Corrected implementation rule

Any formula change after review must be a **new** `drawdown_metrics_version` or experiment hash — no silent relabel of v3.
