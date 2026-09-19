# IMP-OFFHOURS-RESEARCH-03 — Historical Research Harness v1

**Authority:** `HISTORICAL_DEVELOPMENT` only  
**Item 9 / Item 7 / FTEP / Live effects:** `NONE`

## Pipeline

1. **Historical dataset** — Lane B `build_historical_rth_dataset` (fixture or provider); consume `dataset_manifest.json` + fingerprints (Lane C builder APIs; not edited here).
2. **Feature reconstruction** — `reconstruct_historical_research_features` with explicit `prediction_cutoff_ns`, lookback, schema version, and missing-data behavior; Path A bar features via `derive_bar_features` at cutoff.
3. **Chronological research split** — `assign_chronological_splits` → `HISTORICAL_TRAIN` / `HISTORICAL_DEVELOPMENT_VALIDATE` / `HISTORICAL_RESEARCH_TEST` (all remain `HISTORICAL_DEVELOPMENT`; no shuffle by default).
4. **Strategy / challenger** — default `historical_momentum_sign_v1` (development-only; not promotional).
5. **Simulator research** — prediction-conditioned `run_historical_development_simulator_research(predictions=…)` → `SIMULATOR_RESEARCH_RESULT` (explicitly not `ITEM9_CALIBRATION_RESULT`; no independent bar-replay trading).
6. **Metrics** — `compute_component_research_metrics` on development-validate split only; simulator input restricted to `HISTORICAL_DEVELOPMENT_VALIDATE` decision times (holdout excluded from selection-facing PnL/fills and `run_fingerprint` metrics).
7. **Manifest** — `historical_research_run_manifest_v1` written beside predictions/labels; `experiment_manifest.json` cross-ref to `ExperimentManifestV1` fields (no parallel ledger).

## CLI

```bash
python tools/imp.py historical-data harness \
  --fixture-path tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json \
  --start 2026-09-15 --end 2026-09-15
```

Governance lines printed first (`AUTHORITY: HISTORICAL_DEVELOPMENT`, `ITEM9_EFFECT: NONE`, …).

## Run manifest (required fields)

| Field | Description |
|-------|-------------|
| `run_id` | Deterministic SHA-256 from experiment + dataset + config + code SHA |
| `experiment_id` / `hypothesis_id` | Research experiment linkage |
| `research_code_sha` | Git SHA at run time |
| `source_dataset_id` / `dataset_fingerprint` | Lane B dataset identity |
| `evidence_class` / `corpus_evidence_authority` | `HISTORICAL_DEVELOPMENT` |
| `instruments` / `interval` | Coverage |
| `features.schema_version` | `historical-research-bar-features/1.0.0` |
| `target_label_definition` | `historical_research_forward_return_label_v1` (not POST_HORIZON) |
| `split_policy` / `split_assignments` | Chronological partition |
| `model_strategy` | Strategy id + version |
| `simulator` | Version, slippage, `result_kind` |
| `metrics` | Component research metrics |
| `outputs` | Artifact paths + feature root hash |
| `warnings` / `contamination_status` | Development safeguards |
| `lineage` | Parent / challenger run ids |
| `run_fingerprint` | Reproducibility digest |
| `created_timestamp_ns` | Wall clock (excluded from deterministic `run_id`) |

## Reproducibility

Deterministic reruns require the same: dataset fingerprint, `config_fingerprint`, `research_code_sha`, and split policy. Re-running the harness on an unchanged build yields identical `run_id` and `run_fingerprint`.

## Holdout consumption

`assert_split_consumable_for_training_or_selection` refuses `HISTORICAL_RESEARCH_TEST` for training or model selection (fail closed).

## Non-goals

No Item 9 calibration, no prospective label upgrade, no live execution, no production-ready language.
