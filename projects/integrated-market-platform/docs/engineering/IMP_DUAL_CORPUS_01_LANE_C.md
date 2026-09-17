# IMP-DUAL-CORPUS-01 Lane C — Post-Horizon Historical Label Evidence

**Status:** **MERGED** on `origin/main` at `84d197d2` ([#244](https://github.com/AdamEddahmouni/market-trading-platform/pull/244); ancestry includes dual-corpus [#242](https://github.com/AdamEddahmouni/market-trading-platform/pull/242) `859251ae`)
**Increment:** Lane C — label artifacts + IBKR historical TRADE capability spike

## Scope delivered

| Area | Location |
| --- | --- |
| Label evidence contract (append-only, immutable source binding) | `src/market_platform_foundation/intelligence/outcomes/label_evidence.py` |
| Historical TRADE retrieval port | `src/market_platform_foundation/intelligence/outcomes/historical_trade_retrieval.py` |
| IBKR historical TRADE normalization | `src/market_platform_foundation/providers/ibkr_observational/historical_trades.py` |
| IBKR query service extension | `src/market_platform_foundation/providers/ibkr_observational/query_provider.py` |
| Outer TWS adapter hook | `tools/ibkr/tws_client.py` (`fetch_historical_trades` / `reqHistoricalTicks`, TRADES, RTH) |
| Outer REST shim (explicit unavailable) | `tools/ibkr/query_provider.py` |
| Leakage / contract tests | `tests/intelligence/test_post_horizon_label_evidence.py` |
| IBKR parser/runtime tests | `tests/providers/test_g11_historical_trades.py` |
| Fixtures | `tests/intelligence/fixtures/ibkr_historical_trades_sample.json` |

Lane A `dual_corpus` modules are **consumed only** (authority class + `assert_corpus_consumable_for_selection_or_training`). No edits under `paper/calibration/dual_corpus/**`.

## Path A semantics preserved

- Decision/signal time is the prospective source observation `signal_time_ns` (unchanged).
- Horizon: 5 minutes (`300_000_000_000` ns) via BUILD 15 `DIRECTION_UP_DOWN_5M_POLICY`.
- Terminal window: target time + 60s tolerance; availability cutoff at window end (no late grace).
- P0 and terminal prices require eligible **TRADE** observations; **BAR_OHLCV** and bar capabilities are refused.
- Retrieval gated: `request_time_ns >= terminal_window_end_ns` (fail closed otherwise).
- Missing terminal trade → `NO_ELIGIBLE_TRADE` (unlabelable); zero return → refusal on label body.

## Label artifact (minimum fields)

Produced by `build_post_horizon_label_evidence` / `attach_label_evidence`:

- Immutable binding: `source_observation_id`, `source_observation_hash` (canonical SHA over source body excluding linkage fields)
- `corpus_evidence_authority=POST_HORIZON_HISTORICAL_LABEL_EVIDENCE`
- Signal/feature cutoff, P0 block, horizon policy version, target/window times
- Retrieval provenance: request/actual times, provider, capability, params, raw payload ref/hash, trade counts
- Terminal selection: candidates + selected trade + trade event time
- Label outcome: direction / refusal, label availability time, labeler + source code SHAs, linkage id

Source prospective observations are never mutated; linkage is returned separately in `LabelAttachResult.linkage`.

## IBKR historical TRADE capability spike

| Topic | Finding |
| --- | --- |
| Adapter reuse | Extends existing G11 stack: `IbkrReadOnlyQueryProvider` → `IbkrObservationalQueryService` → `historical_trades` normalizer (parallel to `historical_bars`). |
| Endpoint | **TWS/Gateway:** `reqHistoricalTicks` with `whatToShow=TRADES`, `useRTH=True`, up to `numberOfTicks` (default 1000). **Client Portal REST:** no historical tick endpoint in allowlist — outer REST returns `REST_HISTORICAL_TRADES_UNAVAILABLE`. |
| Granularity | Tick-level TRADE prints (not aggregated bars). |
| Max records | Bounded by IB `numberOfTicks` per request (implementation default 1000); pagination not implemented in this spike. |
| RTH | `useRTH=True` on TWS historical ticks request. |
| Pacing | Inherits `ibkr.pacing.history` capability registration; no new live pacing run in CI. |
| Entitlements | Live TRADES streaming remains entitlement-gated separately; historical TRADES capability registered as `IBKR_HISTORICAL_TRADES` / `OBSERVATIONAL_HISTORICAL_TRADES`. |
| Timestamp semantics | Row `t` coerced to ns (seconds/ms heuristic shared with bar normalizer); `availability_semantics=historical_retrieval`. |
| Delayed data | Subject to account market-data tier at runtime (not exercised here). |

### Live verification status: **PROVIDER_UNVERIFIED**

**Blocker:** This increment did not run against a live IBKR session in the implementation environment (`IMP_IBKR_LIVE` / TWS loopback not exercised for historical ticks). Implementation is interface + parser + fixtures + unit tests only.

**Next verification step (operator):** With `IMP_IBKR_LIVE=1` and `IMP_IBKR_TRANSPORT=tws`, call `IbkrOuterReadOnlyQueryProvider.fetch_historical_trades` for a known past RTH window after terminal cutoff and archive raw payload + entitlement snapshot.

## Dual-corpus gaps (Lane C does not close)

- Lane B historical bar corpus population CLI and artifact directories
- Item 9 calibration protocol merge / fitting / gate changes
- Automated linker from Item 9 receipts → `path_a_label_evidence_ids` population
- Live pagination strategy for >1000 ticks per window
- JSON schema publication under manifests (optional follow-up)
- Runtime composition wrapper method (callers can use query service directly)

## Explicit non-changes

- Item 9 remains **NOT_CALIBRATED** — no fitting, no gate changes, no writes to frozen `item9-prospective-proof-receipts`
- Frozen Sep 15 / Sep 17 empirical artifacts untouched
- `UNTOUCHED_FORWARD_EVALUATION` consumption guard unchanged; BAR_OHLCV still forbidden for Path A labels
