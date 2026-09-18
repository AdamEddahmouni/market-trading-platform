# IMP-OFFHOURS-RESEARCH-03 — Lane E: Benchmark Harness Integration

**Depends on:** Lane B `historical_research_run_manifest_v1` ([#256](https://github.com/AdamEddahmouni/market-trading-platform/pull/256) / `research/historical-harness-v1`)

## IBP status

| Subject | State |
|---|---|
| Intelligence Benchmark Protocol (IBP) | **MINIMAL_GREENFIELD_V1** — no pre-existing IBP branch in tree; adapter layer added under `intelligence/benchmark_protocol/` |
| Full 30-case suite | **Catalog present** (`tests/fixtures/intelligence_benchmark/ibp_suite_catalog_v1.json`); **scores not executed** in this increment |
| Smoke10 plan | **Invocation contract** (`ibp-smoke10-invocation-v1`); wiring + contamination checks |
| Smoke10 baseline run | **One bounded execution** via `smoke10-run` (`intelligence_benchmark_smoke10_run_v1`); scores executed for 10 cases only |

## Integration

Lane B run manifests (`historical_research_run_manifest_v1`) map to IBP run records via `adapt_historical_research_run_manifest_v1`:

- Preserves `HISTORICAL_DEVELOPMENT` authority
- Requires explicit `simulator.result_kind` of `SIMULATOR_RESEARCH_RESULT` (refuses absent/unknown kinds and `ITEM9_CALIBRATION_RESULT`)
- Strips `labels_path` and evaluator-only keys from the system-under-test bundle
- Sets `scores_executed: false` until a governed evaluator run is authorized

## CLI

```bash
python tools/imp.py benchmark intelligence readiness --json
python tools/imp.py benchmark intelligence suite-info --json
python tools/imp.py benchmark intelligence adapt --manifest <path/to/run_manifest.json>
python tools/imp.py benchmark intelligence smoke10-plan --manifest <path/to/run_manifest.json>
python tools/imp.py benchmark intelligence smoke10-run --artifact-root <dir> [--manifest <path/to/run_manifest.json>] --json
```

Historical harness (Lane B) remains:

```bash
python tools/imp.py historical-data harness --fixture-path tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json --start 2026-09-15 --end 2026-09-15
```

## Contamination controls

- Evaluator gold lives only under `tests/fixtures/intelligence_benchmark/evaluator_only/gold/` (catalog `evaluator_gold_ref` prefix `evaluator_only/`).
- Adapter never copies gold into `system_under_test_input`.
- Full-suite execution is **not** wired in this increment.

## `BENCHMARK_SMOKE10_READY`

`YES` when: suite catalog validates (30 cases, 10 Smoke10 ids), Smoke10 contract builds, and historical manifest adapter passes on a fixture harness manifest. **Does not** require benchmark scores.

## Smoke10 baseline evidence (Lane D)

Pinned receipts (no rescoring): `evidence/intelligence-benchmark/imp-research-validation-04-lane-d-smoke10/` (`smoke10_baseline_evidence_receipt.json`, `frozen_config.json`, `smoke10_run_record.json`, `contamination_audit.json`).

## Admitted factual gold (Lane M1)

Contract-only increment: [IBP_ADMITTED_FACTUAL_GOLD_V1.md](IBP_ADMITTED_FACTUAL_GOLD_V1.md) (`imp.ibp-admitted-factual-gold/1.0.0`, protocol `IBP_FACTUAL_SMOKE_V1`). No cases, no Smoke10.

## Non-goals

No Item 9 calibration, no 30-case score chase, no gold mutation, no PROGRAM_STATUS SHA fabrication.
