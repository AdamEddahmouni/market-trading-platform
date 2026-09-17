# IMP-DUAL-CORPUS-01 Lane D — Historical Development E2E Demo

**Branch:** `research/historical-development-demo`  
**Evidence class:** `HISTORICAL_DEVELOPMENT_ONLY` / `HISTORICAL_DEVELOPMENT`  
**Not:** calibrated, prospective, or Item 9 admission.

## Purpose

Bounded proof that Lane B historical infrastructure feeds existing platform paths:

1. Fixture provider → Lane B corpus build (manifest + quality + normalized fingerprint)
2. Canonical normalized bars → replay envelope → `run_feature_replay` (Phase 5 bar features)
3. Same events → `run_risk_simulation_evaluation` (Phase 7 strategy + simulator + accounting)
4. Reproducible `e2e_result.json` under `artifacts/historical-development/demo-runs/<run_id>/`

Instrument: **AAPL**. Session: **2026-09-15 RTH** via  
`tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json`.

## CLI

Governance lines (always printed):

- `AUTHORITY: HISTORICAL_DEVELOPMENT`
- `PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED`
- `CALIBRATION_STATE_CHANGED: NO`
- `FTEP_STATE_CHANGED: NO`

### One-shot demo (build + evaluate)

```text
python tools/imp.py historical-data demo \
  --fixture-path tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json \
  --instrument AAPL \
  --start 2026-09-15 \
  --end 2026-09-15
```

### Corpus only (Lane B)

```text
python tools/imp.py historical-data build \
  --provider fixture \
  --fixture-path tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json \
  --instrument AAPL \
  --start 2026-09-15 \
  --end 2026-09-15 \
  --resolution 1m \
  --session RTH
```

## Artifact layout

| Stage | Path |
| --- | --- |
| Lane B corpus | `artifacts/historical-rth-development/runs/<run_id>/` |
| Lane D e2e result | `artifacts/historical-development/demo-runs/<run_id>/e2e_result.json` |

Fingerprints in the e2e artifact: `dataset_fingerprint`, `normalized_fingerprint`, `quality_fingerprint`, `feature_root_hash`, `risk_simulation_root_hash`, `result_fingerprint`.

## Code map

| Component | Location |
| --- | --- |
| E2E orchestration | `src/market_platform_foundation/market_data/historical_development/e2e_demo.py` |
| Demo CLI | `tools/historical_data/demo_cli.py` |
| Lane B builder | `src/market_platform_foundation/market_data/historical_development/builder.py` |
| Feature path | `src/market_platform_foundation/replay/feature_lifecycle.py` |
| Risk simulation | `src/market_platform_foundation/risk_simulation/evaluation.py` |
| Tests | `tests/platform/test_historical_development_e2e_demo.py` |

## Explicit non-changes

- No writes to `item9-prospective-proof-receipts`
- Item 9 remains **NOT_CALIBRATED**
- No OpenD / live IBKR pulls in CI (fixture only)
- Lane C post-horizon label evidence not wired in this demo (nearest entrypoint: `intelligence/outcomes/label_evidence.py` + historical TRADE retrieval; requires TRADE ticks, not BAR_OHLCV)

## Known gaps

- Fixture sample has **two** RTH bars after dedupe; quality reports **missing intervals** for the full 390-minute grid (expected for a micro-fixture).
- `enrich_normalized_bar_for_replay` is a thin envelope adapter, not a new canonical ingestion pipeline.
- Walk-forward / Wave 1 research export and Item 7 corpus collectors are separate entrypoints (`research/wave1/`, `tools/item7_corpus_collector.py`).
- Moomoo OpenD historical pull remains `PROVIDER_UNVERIFIED` in CI (Lane B `moomoo-opend` provider).
