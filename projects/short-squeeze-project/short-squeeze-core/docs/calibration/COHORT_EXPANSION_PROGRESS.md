# Historical cohort expansion progress

Tracks progress toward `min_case_count_for_recommendation: 30` in
`phase_3d_calibration_policy_v1.json`. Calibration remains exploratory until the
threshold is met.

## Current labeled cohort (2026-08-17)

| Metric | Count |
|--------|------:|
| Unique historical symbols | 15 (13 pilot + KLRS, SG) |
| Case boundaries | 17 (BIYA×2 + fifteen artifact-discovery symbols) |
| Evaluable outcome labels after Stage 2 | 17 (all boundaries have Stage 2 forward-outcome bars) |
| Independent symbols for policy recommendation | 14 (BIYA boundaries are dependent per ADR 0054) |

## Completed milestones

1. **Phase 3D calibration** landed with detection-predicate ADR-0067 findings.
2. **ADR-0066 intake** accepts honest IBKR `UNKNOWN` volume/timestamp semantics.
3. **Phase 3E Stage 2** collected adjusted forward-outcome bars for 15 symbols
   (13 preregistered pilot symbols plus KLRS and SG from the expanded IBKR cohort).
4. **Fixture regeneration** now prefers `{SYMBOL}-forward-outcome.csv` over legacy
   `frozen-forward-24h` artifacts via `scripts/generate_ibkr_cohort_phase_3a_fixtures.py`.

## Remaining work toward n=30

- Register additional complete historical cases with evaluable outcomes (not
  artifact-discovery-only registrations).
- Complete Stage 1 evidence bundles and Phase 3A freeze for symbols lacking
  `build/acquisition/evidence-bundles` coverage.
- Re-run `tools/run_calibration_suite.py` after each cohort increment; update
  ADR-0067 only if detection findings change materially.
- Adam scoring calibration (`adam_evidence_gated_prime.v1`) remains deferred.

## Commands

```powershell
cd short-squeeze-project\short-squeeze-core
python scripts/acquisition/collect_forward_outcome_bars.py
python scripts/acquisition/run_stage2_pipeline.py
python scripts/generate_ibkr_cohort_phase_3a_fixtures.py
python scripts/generate_phase_3b_anchors.py
python scripts/generate_phase_3c_anchors.py
python tools/run_calibration_suite.py
```
