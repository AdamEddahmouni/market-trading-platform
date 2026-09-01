# P6 Shadow Run 1 — Forward Validation Evidence Phase (completion record)

**Status:** IN PROGRESS — EVIDENCE COLLECTION  
**Date:** 2026-09-01 (updated 2026-09-01 afternoon)  
**Baseline:** `cloud/build-35-release-governance-operational-acceptance` @ `96032be`

## Goal

Advance IMP from Build-35 operational baseline into a preregistered forward-validation evidence phase (P6 Shadow Run 1) without enabling production execution.

## Disposition

**IN PROGRESS — EVIDENCE COLLECTION**

ACTUAL_FORWARD observations collected on the default-store run (Moomoo/OpenD live). Stopping rule not met; P6 not CLOSED.

## Protocol

- **Protocol:** [P6_SHADOW_RUN_1_PROTOCOL.md](../engineering/P6_SHADOW_RUN_1_PROTOCOL.md)
- **Preregistered:** 2026-09-01T15:33:00Z (`artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json`)
- **Instrument:** BIYA
- **First session:** 2026-09-01
- **Run ID (live default store):** `SHRUN-00C5C98CD1C33EC4D22D0BFCAD4AF0AD51FBF5EBF566AA8C2308B98D2BD5A7FC`
- **Capture ID:** `CAP-BIYA-SR1-20260901`

## Forward evidence (current)

| Metric | Value |
|--------|------:|
| ACTUAL_FORWARD model outcomes (abstentions + predictions) | 4 |
| Decisions | 4 |
| Abstentions | 4 |
| Predictions | 0 |
| Recorder errors | 0 |
| Scheduled grid opportunities | 0 |
| Run state | OPEN (resumable) |

## Source availability

See `artifacts/shadow-run-1/SOURCE_AVAILABILITY_AUDIT.json`. `MOOMOO_BIYA_OBSERVATIONAL` verified live (OpenD + quote context PASS). ES excluded per ADR-DATA-001. Fixture/replay not counted as forward evidence.

## Acceptance matrix

`artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` — 15 pass, 0 fail, 0 blocked. P6-AC-011 pass with pinned `P6_VALIDATION_RECEIPT.json` (`validate.py full`: 3003 tests, 0 failures, 0 errors). **p6_disposition: IN_PROGRESS_EVIDENCE_COLLECTION** (stopping rule not met).

## Bug fixes (this increment)

1. **`event_type` vs `capability`** — live admission envelopes use `event_type`; recorder now accepts both.
2. **SQLite thread safety** — `ShadowExperimentStore` / `ShadowStore` use `check_same_thread=False` + `RLock` so Moomoo feed callbacks can write decisions.
3. **Execution gate check** — `IMP_SHADOW_RECORDING` no longer misclassified as an execution arm in acceptance.

## No-lookahead verification

- Predictor excludes late-arriving trades (`test_shadow_run1_predictor`)
- Append-only experiment store (`test_shadow_run1_experiment_store`)
- Cross-thread `record_decision_once` (`test_record_decision_once_from_worker_thread`)
- Labeling separated from decision generation (`test_shadow_run1_labeling_job`)
- Causality violations at report time: 0

## Operational findings

- Live 90s collection via `collect_shadow_observations.py` with external Moomoo SDK venv
- Shadow recorder wrote `ABSTAINED_MODEL` during live ingest (0 `RECORDER_EXCEPTION`)
- Preflight remains fail-closed without pinned validation + runtime health receipts

## Validation

| Command | Result |
|---------|--------|
| `unittest tests.platform.test_shadow_run1_*` (targeted) | pass (incl. thread-safety + event_type) |
| `validate.py full` | **passed** — pinned `artifacts/shadow-run-1/P6_VALIDATION_RECEIPT.json` (3003 tests, 0 failures, 0 errors) |

## Remaining blockers

1. Complete preregistered observation window (stopping rule: 5 sessions + 65 grid opportunities OR 8 sessions)
2. `close` → `label-due` → `report` after horizons mature
3. Pin validation receipt at operator preflight for P6-AC-011 pass

## Git state

Feature branch `feat/p6-shadow-run-1-forward-validation` from baseline `96032be`.

## Related

- [FORWARD_SHADOW_VALIDATION SOP](../engineering/sops/FORWARD_SHADOW_VALIDATION.md)
- [2026-08-23-platform-p6-shadow-run-1-design.md](../superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md)
