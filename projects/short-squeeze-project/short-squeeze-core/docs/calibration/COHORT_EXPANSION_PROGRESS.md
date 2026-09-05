# Historical cohort expansion progress

Tracks progress toward `min_case_count_for_recommendation: 30` in
`phase_3d_calibration_policy_v1.json`. The threshold was met on 2026-08-17; policy
recommendation review is complete.

## Current labeled cohort (2026-08-17)

| Metric | Count |
|--------|------:|
| Unique historical symbols | 28 (15 IBKR + 5 Phase 3F-01 + 5 Phase 3F-02 + 3 Phase 3F-03) |
| Case boundaries | 30 (BIYA×2 + twenty-eight artifact-discovery symbols) |
| Evaluable outcome labels after Stage 2 | 30 (all boundaries have Stage 2 forward-outcome bars) |
| Independent symbols for policy recommendation | 27 (BIYA boundaries are dependent per ADR 0054) |

## Completed milestones

1. **Phase 3D calibration** landed with detection-predicate ADR-0067 findings.
2. **ADR-0066 intake** accepts honest IBKR `UNKNOWN` volume/timestamp semantics.
3. **Phase 3E Stage 2** collected adjusted forward-outcome bars for 15 symbols
   (13 preregistered pilot symbols plus KLRS and SG from the expanded IBKR cohort).
4. **Phase 3F Batch 01** preregistered and executed for CELZ, GDC, ADVB, GOAI, NXXT
   (archived news co-occurrence discovery; IBKR bars collected 2026-08-17).
5. **Phase 3F Batch 02** preregistered and executed for VMAR, ATAI, CADL, CGEM, IOVA
   (archived news co-occurrence + platform prime-log discovery; IBKR bars collected 2026-08-17).
6. **Phase 3F Batch 03** preregistered and executed for PMAX, STAK, APVO
   (archived prime-log + screening-universe discovery; IBKR bars collected 2026-08-17).
7. **Fixture regeneration** prefers `{SYMBOL}-forward-outcome.csv` over legacy
   `frozen-forward-24h` artifacts via `scripts/generate_ibkr_cohort_phase_3a_fixtures.py`.

## Policy recommendation review (2026-08-17)

- **Threshold met:** 30 case boundaries registered.
- **Review complete:** [PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md](PHASE_3D_POLICY_RECOMMENDATION_REVIEW.md)
- **Detection policy:** retain `phase_3b_research_detection_policy.v1` — [ADR-0067](../adr/0067-phase-3b-detection-predicate-calibration-findings.md) revised at n=30
- **Outcome policy:** retain `phase_3b_outcome_label_policy.v1` at ±25%/24h — [ADR-0068](../adr/0068-phase-3b-outcome-label-calibration-findings.md) created
- Re-run `tools/run_calibration_suite.py` after any future cohort increment; update ADRs only if findings change materially.
Adam scoring calibration (`adam_evidence_gated_prime.v1`) **complete** — retain 65%
minimum dimension weight ([ADR 0069](../adr/0069-adam-evidence-gated-prime-calibration-findings.md))
and baseline classification gates ([ADR 0070](../adr/0070-adam-classification-threshold-calibration-findings.md)).
See [ADAM_SCORING_CALIBRATION_REVIEW.md](ADAM_SCORING_CALIBRATION_REVIEW.md) and
[ADAM_CLASSIFICATION_THRESHOLD_CALIBRATION_REVIEW.md](ADAM_CLASSIFICATION_THRESHOLD_CALIBRATION_REVIEW.md).

## Phase 3F Batch 04 — BIYA IBKR alignment (2026-08-17)

| Metric | Count |
|--------|------:|
| IBKR frozen-boundary symbols | 29 (28 prior + BIYA) |
| Discovery sources exhausted | All in-repo US equity tickers except BIYA |
| Stage 2 leakage | 29/29 pass |
| Phase 3A freeze for BIYA | Complete — batch-05 manifest registration + 29/29 freeze |

See [phase-3f-cohort-expansion-batch-04.md](../phase-3f-cohort-expansion-batch-04.md).

In-repo US equity discovery for the IBKR frozen-boundary track is **exhausted**.
External discovery is preregistered in
[phase-3f-external-discovery-preregistration.md](../phase-3f-external-discovery-preregistration.md).

## Phase 3F Batch 05 — external Finviz export (2026-08-17)

| Item | Status |
|------|--------|
| Discovery lane | Fresh Finviz Elite export (`sh_float_u50,sh_price_u50`) |
| Preregistration | [phase-3f-cohort-expansion-batch-05-external.md](../phase-3f-cohort-expansion-batch-05-external.md) |
| Normalized artifact | `intake/batches/phase-3f-cohort-expansion-05-external/normalized/batch3f05_external_discovery_rows.json` |
| Symbol selection | **Captured** — AACB, AACG, AACI, AACP, AADX (export row order, excluding frozen cohort) |
| Identity audit | **PASS** — all 5 contracts `CONTRACT_RESOLVED` (`tools/run_batch05_identity_audit.py`) |
| IBKR bars | **Collected** — detection-context + forward-outcome under `intake/local-bars/ibkr-batch-05/raw/` |
| Manifest merge | **Complete** — `python tools/merge_batch05_manifests.py` |
| Batch 07 readiness (all cohort) | **34/34** cases — `python tools/run_batch07_readiness.py --cohort all` |
| Phase 3A freeze | **5/5** leakage passed — `--cohort batch3f05` |
| Stage 2 pipeline | **4/5** evaluable outcomes; AACP permanently `OUTCOME_UNEVALUABLE` |
| AACP retry (2026-08-18) | IBKR `ADJUSTED_FORWARD_OUTCOME_24H` → `SUCCESS_EMPTY` (documented) |
| Fixture regeneration | **Complete** — includes batch3f05 symbols (AACP outcome excluded) |
| Calibration suite | **Re-run** — no ADR changes required at n=35 |

## Batch 07 readiness audit (2026-08-17)

| Metric | Count |
|--------|------:|
| Operation-readiness cases (Batch 05 root) | 29 |
| Phase 3A request readiness | 29/29 ready |
| PRICE_RANGE at Batch 07 | `BLOCKED_MISSING_SEMANTICS` (expected) |

See [batch-07-readiness-audit.md](../batch-07-readiness-audit.md). Generate with
`python tools/run_batch07_readiness.py --cohort all`.

## Phase 3F Batch 05 pipeline completion (2026-08-17)

| Metric | Count |
|--------|------:|
| Registered case boundaries (cohort + IMP fixture) | 35 |
| Evaluable Stage 2 outcome labels | 34 (4 new external + prior 30) |
| Permanent outcome exclusions | 1 (AACP — see [AACP_OUTCOME_EXCLUSION_RECORD.md](AACP_OUTCOME_EXCLUSION_RECORD.md)) |
| Batch 07 operation-readiness cases | 34 |
| Leakage-passing batch3f05 freezes | 5 |
| Calibration ADR updates | None — policies retained |

Pipeline commands:

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/merge_batch05_manifests.py
python tools/run_batch07_readiness.py --cohort all
python -m squeeze_core.acquisition.phase3a_freeze.cli --cohort batch3f05 generate-phase3a-freeze
python scripts/acquisition/run_stage2_pipeline.py --cohort batch3f05 --force
python scripts/generate_ibkr_cohort_phase_3a_fixtures.py
python tools/run_calibration_suite.py
```
