# Futures Lane — Read-Only Integration

**Status:** `COMPLETE` — fixture-first ES depth lane with optional donor bridge.

This lane connects the governed IMP UI to ES CME futures depth evidence. The primary path uses admitted synthetic fixture `ADMITTED-L2-ES-001` per ADR-DATA-002. An optional read-only bridge to Eric_futuresX (`:8788`) serves live snapshots when the donor bridge is running.

## Prerequisites

- Python 3.11+ for IMP foundation
- Node.js for IMP `ui/` dev server (optional for API-only verification)
- FuturesX venv at `Eric_futuresX-main/futuresX-main/venv` (optional, for bridge)

## Quick start (three terminals)

### Terminal 1 — FuturesX donor bridge (optional)

```powershell
cd Eric_futuresX-main\futuresX-main
.\venv\Scripts\python.exe scripts\bridge_server.py --port 8788
```

Verify: `http://127.0.0.1:8788/health` returns `status: OK` and `symbol: ES`.

### Terminal 2 — IMP UI API

```powershell
cd integrated-market-platform
python tools/ui1/run_ui_api.py --serve --port 8766
```

Verify fixture path:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/workspace/ES/futures | Select-Object available, symbol, contract_month, snapshot_count
```

Verify explore:

```powershell
Invoke-RestMethod http://127.0.0.1:8766/explore/futures | Select-Object available, symbol
```

### Terminal 3 — React frontend

```powershell
cd integrated-market-platform\ui
npm run dev
```

Open `http://127.0.0.1:5173/workspace/ES/futures` to view the futures workspace.

Open `http://127.0.0.1:5173/explore` for the ES futures bridge status card (when donor bridge is running).

## Explain / Inspect

| Ref | Endpoint |
|---|---|
| `explain:futures:ES` | `GET /explain/explain:futures:ES` |
| `inspect:futures:ES` | `GET /inspect/inspect:futures:ES` |

Workspace Explain/Inspect buttons on `/workspace/ES/futures` use these refs. Inspect includes DERIVATION metadata for `futures_lane` signal methods.

## Donor launcher

From the workspace root:

```powershell
.\tools\run_donor_demos.ps1 -Start futures
```

Read-only bridge on `:8788`; does **not** start `live_trader.py`.

## Data paths

| Path | Provenance | Replay admission |
|---|---|---|
| Fixture `es_depth_slice.json` | Synthetic ES L2 (smoke-derived) | Admitted — ADMITTED-L2-ES-001 |
| Donor bridge `:8788` | Live/read-through from FuturesX | **Not** admitted into canonical replay |
| Bundled FuturesX CSV/DB | Git LFS (blocked in zip copy) | Deferred until lawful bytes + ADR update |

## Governance

- ADR-DATA-002 admits bounded synthetic ES fixture only.
- ADR-DATA-001 full ES session bundle remains **deferred**.
- `futures_depth` is the canonical institutional family id for ES L2 depth; `futures_positioning` remains the legacy whale envelope id (Phase 14 stable).
- `whale.futures_depth` and `whale.futures_positioning` capabilities both surface when entitled.
- Donor-bridge OFI uses in-process prev-snapshot carry; first fetch degrades with `NO_PREV_SNAPSHOT` (not zero OFI).
- No order execution in IMP; research-only by default.

## Phase 14 acceptance

```powershell
cd integrated-market-platform
python tools/phase14/run_phase14_pipeline.py --output-dir evidence/phase14/build-run
```

## Lane acceptance (end-to-end evidence)

With FuturesX bridge (`:8788`) and IMP UI API (`:8766`) running:

```powershell
cd integrated-market-platform
python tools/integration/futures_lane_acceptance.py --require-donor --require-imp --output evidence/integration/futures-lane-acceptance.json
```

Offline fail-closed checks always run; live projection and HTTP checks run when servers are up.
When the donor bridge is live, workspace `/workspace/ES/futures` should report `provenance: donor_bridge`.

Canonical lane-closure artifact: [`evidence/integration/futures-lane-acceptance.json`](../../evidence/integration/futures-lane-acceptance.json) (`status: PASS` when both servers are live).

## Related modules

| Component | Path |
|---|---|
| Lane patterns | `src/market_platform_foundation/donor_patterns/futures_lane.py` |
| Contract model (F1) | `src/market_platform_foundation/contracts/futures.py` |
| Roll / notional | `src/market_platform_foundation/futures/` |
| Redesign docs | `docs/research/FUTURES_*`, `docs/research/THREE_LANE_ROADMAP_RECONCILIATION.md` |
| Fixture provider | `src/market_platform_foundation/providers/adapters/fixture_futures.py` |
| Donor bridge client | `src/market_platform_foundation/donor_bridge/futures_client.py` |
| UI workspace | `ui/src/components/futures/` |
| Fixture | `tests/fixtures/providers/futures/es_depth_slice.json` |
| COT fixture (F4) | `tests/fixtures/providers/futures/es_cot_positioning_slice.json` |
| Settlement bars fixture (F5) | `tests/fixtures/providers/futures/es_settlement_bars_slice.json` |
| Macro calendar fixture (F7) | `tests/fixtures/providers/futures/es_macro_events_slice.json` |
| Margin history fixture (F8) | `tests/fixtures/providers/futures/es_margin_history_slice.json` |

## F4 — COT / OI positioning (fixture scope)

Module: `src/market_platform_foundation/futures/positioning.py`

| Capability | ID | Scope |
|---|---|---|
| COT crowding features | `futures_positioning_v1` | Managed-money net percentile / z-score |
| OI velocity hypotheses | `futures_positioning_v1` | Non-directional labels from chain OI history |

**Boundary:** COT positioning is distinct from depth-derived `legacy_whale_family: futures_positioning`. OI change ≠ directional forecast.

Workspace payload fields:

- `positioning_snapshot` — net, net_percentile, participant_category, observation/publication times
- `futures_positioning_available` — bool (COT PIT-valid)
- `oi_velocity_hypothesis` — label + disclaimer

Cross-lane signals: `FUTURES_POSITIONING_CROWDED_LONG`, `FUTURES_POSITIONING_CROWDED_SHORT`

Golden regression: `tests/fixtures/futures/es_positioning_expected.json`

## F5 — Trend + carry baselines (fixture scope)

Module: `src/market_platform_foundation/futures/baselines.py`

| Capability | ID | Scope |
|---|---|---|
| Vol-scaled trend features | `futures_baselines_v1` | trend_1m/3m/6m/12m from settlement bars + SHARED P2 EWMA vol |
| Carry percentile/change | `futures_baselines_v1` | Extends F3 carry with fixture `carry_history` |
| Curve momentum | `futures_baselines_v1` | Slope change + calendar spread momentum label |

**Boundary:** Baseline features ≠ directional forecast; positive carry ≠ positive return.

Workspace payload fields:

- `trend_baseline_snapshot` — vol-scaled trends, vol_estimate, lookback_bars_used
- `carry_baseline` — percentile, change, zscore (additive on `carry_observation`)
- `curve_momentum` — slope, slope_change, calendar_spread_momentum
- `futures_baselines_available` — bool
- `trend_regime` — `TREND_UP` / `TREND_DOWN` / `NEUTRAL` label only

Cross-lane signals: `FUTURES_TREND_UP`, `FUTURES_TREND_DOWN`

Golden regression: `tests/fixtures/futures/es_baselines_expected.json`

## F6 — Asset-family plugin models (fixture scope)

Module: `src/market_platform_foundation/futures/families/`

| Capability | ID | Scope |
|---|---|---|
| Family plugin interface | `futures_family_v1` | `FuturesFamilyModel` protocol + registry |
| EQUITY_INDEX plugin | `futures_family_v1` | ES curve/carry/positioning/macro/leverage interpretation |

**Boundary:** Family context is interpretive metadata — not a directional forecast or universal Futures Score.

Workspace payload fields:

- `family_context_snapshot` — curve_read, positioning_read, event_context_read, risk_context
- `futures_family_available` — bool

Golden regression: `tests/fixtures/futures/es_family_context_expected.json`

## F7 — Macro / fundamental events (fixture scope)

Module: `src/market_platform_foundation/futures/macro_events.py`

| Capability | ID | Scope |
|---|---|---|
| Macro calendar ingest | `macro.fixture.futures_macro` on `ADMITTED-MACRO-ES-001` | FOMC/CPI/NFP/PPI-style events |
| Event window + surprise | `futures_macro_events_v1` | 48h window, consensus vs actual surprise |

**Boundary:** Distinct from equity `public_catalyst` whale family and SHARED P2 jump primitives.

Workspace payload fields:

- `macro_event_snapshot` — upcoming event, event_window_active, surprise_zscore, macro_risk_regime
- `futures_macro_available` — bool

Cross-lane signals: `FUTURES_MACRO_EVENT_RISK`

Golden regression: `tests/fixtures/futures/es_macro_events_expected.json`

## F8 — Leverage / liquidation stress (fixture scope)

Module: `src/market_platform_foundation/futures/leverage_stress.py`

| Capability | ID | Scope |
|---|---|---|
| Margin history ingest | `margin.fixture.futures_margin` on `ADMITTED-MARGIN-ES-001` | PIT-filtered maintenance margin rows |
| Rule-based stress composite | `futures_leverage_stress_v1` | Margin percentile + crowding + liquidity fragility |

**Boundary:** Futures liquidation taxonomy — distinct from Short Squeeze equity mechanics.

Workspace payload fields:

- `leverage_stress_snapshot` — stress_score, stress_regime, long/short_liquidation_risk, effective_leverage
- `futures_leverage_stress_available` — bool

Cross-lane signals: `FUTURES_LONG_LIQUIDATION_RISK`, `FUTURES_SHORT_LIQUIDATION_RISK`

Golden regression: `tests/fixtures/futures/es_leverage_stress_expected.json`

## F11 — Advanced modeling baseline (experimental)

Modules: `src/market_platform_foundation/futures/advanced_features.py`, `advanced_baseline.py`, `research/`

| Method | ID | Scope |
|---|---|---|
| Feature vector | `futures_feature_vector_v1` | EQUITY_INDEX trend/carry/curve/COT/leverage/macro |
| Engineered baseline | `futures_family_engineered_v1` | M8 outright + curve-steepen probabilities vs M1 trend-only |
| Baseline gate | `F11-S1` | Walk-forward validation on `ADMITTED-F11-ES-001` |

**Boundary:** Research-only forecast metadata — no new directional EvidenceSignal enums. ENERGY/TREASURY remain fail-closed.

Workspace payload fields:

- `latest_futures_forecast` — model version, outright_up_probability, curve_steepen_probability, research_only
- `futures_advanced_forecast_available` — bool

Fixtures:

- `tests/fixtures/futures/es_f11_baseline_slice.json`
- `tests/fixtures/futures/es_f11_cot_upgrade_slice.json`
- `tests/fixtures/futures/es_f11_baseline_expected.json`

CLI: `python tools/futures/run_f11_baseline_gate_validation.py`

