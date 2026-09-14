# Item 7 Lane G — Path A corpus collection

Lawful **Path A production training** examples are not manufactured by this
repository today. Item 7 remains `PARTIAL` with blocker
`NO_GOVERNED_PATH_A_TRAINING_CORPUS` until governed historical rows exist and
pass attestation.

## Corpus layers (do not conflate)

| Layer | Artifact kind | Production claim |
| --- | --- | --- |
| Candidate corpus | `path_a_training_corpus_candidate_v1` | No |
| PIT-validated corpus | `path_a_training_corpus_pit_validated_v1` | No |
| Manifest candidate | `path_a_production_training_manifest_candidate_v1` | No |
| Governed training manifest | `path_a_production_training_manifest_v1` | Software input only; not empirical proof |
| PRODUCTION artifacts | contributor / calibration / model JSON | Requires governed corpus + RTH hop |

Collecting or exporting rows **does not** set `PRODUCTION_FORECAST_ARTIFACT_READY`.

## Floors (current code constants)

- Specialist: minimum **8** rows, minimum **2** per class (`MINIMUM_SPECIALIST_SAMPLES`, `MINIMUM_SPECIALIST_CLASS_COUNT`).
- Calibration: minimum **20** rows, minimum **5** per class (`MINIMUM_CALIBRATION_SAMPLES`, `MINIMUM_CLASS_COUNT`).

The collector reports floor status; it does not lower thresholds.

## Operator entrypoint

From `projects/integrated-market-platform/`:

```powershell
python tools/item7_corpus_collector.py `
  --training-cutoff-ns <ns> `
  --output-dir .local/corpus-export `
  --include-fixture-proof
```

`--include-fixture-proof` labels rows `FIXTURE_ONLY` for machinery verification
when no governed repository or JSONL joins exist. Do not promote fixture output
to production training.

## Implementation

- Library: `src/market_platform_foundation/intelligence/production/corpus_collector.py`
- CLI: `tools/item7_corpus_collector.py`
- Tests: `tests/intelligence/test_item7_corpus_collector.py`

Labels must trace to settled `OutcomeV1` direction (`LONG`/`SHORT`) or explicit
`FIXTURE_ONLY` proof mode. Manual or quote-synthetic label sources are rejected.
