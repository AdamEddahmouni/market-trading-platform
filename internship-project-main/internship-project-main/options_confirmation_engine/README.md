# Options Confirmation Engine

Standalone Python package that scores **options-chain confirmation** for a ticker: fetch (or replay) a chain, compute directional features, apply a liquidity gate, and emit a 0–100 score plus bias label. It is designed to be imported by the **news momentum agent** as a confirmation layer — not as a live broker execution path.

## What this package is

| Layer | Module(s) | Output |
|-------|-----------|--------|
| Ingest | `options_engine/data_ingestor.py`, providers | `Snapshot` + `data_quality_flags` |
| Features | `options_engine/features*.py` | Float feature dict with `*_available` flags |
| Liquidity gate | `options_engine/features_liquidity.py` | `liquidity_ok`, `liquidity_reject`, reject detail |
| Scoring | `options_engine/scoring.py` | `options_score`, `options_bias`, reasoning |
| Orchestration | `options_engine/runner.py` | Per-ticker dict; batch writes `state/signals.json` |

The scheduler (`scheduler.py`) can run this package on its own universe; the news agent typically calls it **on demand** for one ticker at a time.

## How the news agent imports it (PYTHONPATH)

The agent does **not** install this as a pip package. It adds the engine root directory to `sys.path`:

```python
# news_momentum_agent/settings.json
"options_confirmation": {
  "enabled": true,
  "engine_path": "/path/to/options_confirmation_engine",
  "chain_provider": "auto",   # unusual_whales → yfinance fallback
  "offline_mode": false       # true → replay provider + saved snapshots
}
```

```python
# news_momentum_agent/agent/options_client.py (simplified)
sys.path.insert(0, settings["options_confirmation"]["engine_path"])
from options_engine.runner import run_batch
from options_engine.utils import load_settings, merge_nested_dicts
```

Evaluation code uses the same pattern: `ENGINE_ROOT = PROJECT_ROOT.parent / "options_confirmation_engine"` then `sys.path.insert(0, str(ENGINE_ROOT))`.

**Requirements:** run from a venv that has engine dependencies (`requirements.txt`). The agent and engine can share a venv or use separate ones as long as `engine_path` resolves and imports succeed.

## Chain providers

Configured via `settings.json` → `chain.provider` (overridden by the agent's `chain_provider` / `offline_mode`).

| Provider | When used | Notes |
|----------|-----------|--------|
| **Unusual Whales** | `unusual_whales`, `uw`, or `auto` when `UNUSUAL_WHALES_API_TOKEN` is set | Primary live chain; optional `fetch_flow_recent` enrichment in `options_client` |
| **yfinance** | `yfinance`, or `auto` fallback | Free; may patch same-day expiry via Alpaca when co-located with the agent |
| **Finviz Elite** | `finviz` only (explicit) | CSV export; **not** used in agent `auto` mode (too unreliable) |
| **replay** | `replay`, or agent `offline_mode` | Reads `state/raw_snapshots/*.json`; no network |

Universe resolution (`finviz_screener.py`) and standalone paper trading (`paper_trader.py`) are engine-local; the news agent does not depend on them for live decisions.

## Scoring output shape

`runner.run_ticker` / `run_batch` items (and `options_client._normalize_item`) expose:

```json
{
  "ticker": "AAPL",
  "options_score": 62.5,
  "options_bias": "bullish",
  "spot_price": 198.12,
  "as_of": "2026-07-31T12:00:00+00:00",
  "provider": "unusual_whales",
  "features": { "...": 0.0 },
  "feature_values": { "...": 0.0 },
  "feature_subscores": { "...": 0.0 },
  "feature_weights_used": { "...": 25.0 },
  "data_quality": { "quality_score": 0.85, "flags": [] },
  "reasoning_summary": "AAPL: score=62.5, bias=bullish, ...",
  "liquidity_reject": false
}
```

- **`options_score`**: 0–100; 50 is neutral; weighted bullish sub-scores with missing features renormalized out.
- **`options_bias`**: `bullish` | `bearish` | `neutral` | `no_data` (low quality or too few directional signals).
- **`features`**: full feature layer output including 0DTE modules (GEX, max pain, flow trend, liquidity, TOD, regime).

Thresholds and weights live in `options_confirmation_engine/settings.json` under `scoring` and `odte_signals`.

## Liquidity gate

`features_liquidity.compute_liquidity_features` applies a **hard reject** before the agent sizes a trade:

- Requires at least one ATM-band contract passing **spread** (`max_spread_pct_of_mid`) and **open interest** (`min_oi`) floors.
- Sets `liquidity_reject=1.0` and `liquidity_reject_primary` (`no_listed_chain`, `spread_too_wide`, `oi_below_min`, etc.).
- Scoring adds a `liquidity_reject` data-quality flag and pulls the score toward neutral when quality is low.

The news agent's `odte_decision` module reads these fields and calls `format_liquidity_reject_detail` for logs — it does not loosen thresholds at runtime.

## Independence from live broker execution

- This package **never** sends orders to Alpaca or any broker.
- `paper_trader.py` is an optional **simulated** stock book driven by `options_bias` for engine-local demos; state under `state/portfolio.json`.
- Live paper/live trading in the news agent uses `news_momentum_agent/agent/paper_trader.py` and Alpaca separately; options output only **confirms or blocks** proposed direction (score, bias, liquidity).
- Batch runs write diagnostic state (`state/signals.json`, `health.json`, `trade_log.json`) for the optional Streamlit dashboard (`dashboard/app.py`).

## Quick start (standalone)

```bash
cd options_confirmation_engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scheduler.py --once --offline   # replay snapshots, no network
streamlit run dashboard/app.py         # read-only state viewer
```

## Related docs in repo

- Agent integration: `news_momentum_agent/agent/options_client.py`
- Offline replay / backtest: `news_momentum_agent/evaluation/spy_qqq_replay.py`, `historical_chain_adapter.py`
- Agent settings block: `news_momentum_agent/settings.json` → `options_confirmation`
