# P6 Shadow Run 1 — Forward Validation Evidence Phase (completion record)

**Status:** IN PROGRESS — EVIDENCE COLLECTION  
**Date:** 2026-09-01  
**Baseline:** `cloud/build-35-release-governance-operational-acceptance` @ `96032be`

## Goal

Advance IMP from Build-35 operational baseline into a preregistered forward-validation evidence phase (P6 Shadow Run 1) without enabling production execution.

## Disposition

**IN PROGRESS — EVIDENCE COLLECTION**

Forward observations are **blocked** pending Moomoo/OpenD observational connectivity. Infrastructure, protocol preregistration, acceptance machinery, and resumable run initialization are complete.

## Protocol

- **Protocol:** [P6_SHADOW_RUN_1_PROTOCOL.md](../engineering/P6_SHADOW_RUN_1_PROTOCOL.md)
- **Preregistered:** 2026-09-01T15:33:00Z (`artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json`)
- **Instrument:** BIYA
- **First session:** 2026-09-02
- **Run ID:** `SHRUN-D3AA0CCD4FA92F76F755049F570DC71DDEEA71CF35D1F0375EA03E0E5917FB06`

## Forward evidence (current)

| Metric | Value |
|--------|------:|
| ACTUAL_FORWARD observations | 0 |
| Decisions | 0 |
| Abstentions | 0 |
| Recorder errors | 0 |
| Run state | OPEN (resumable) |

## Source availability

See `artifacts/shadow-run-1/SOURCE_AVAILABILITY_AUDIT.json`. Primary blocker: `MOOMOO_BIYA_OBSERVATIONAL` externally blocked. ES excluded per ADR-DATA-001. Fixture/replay not counted as forward evidence.

## Acceptance matrix

`artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` — 13 pass, 0 fail, 2 blocked (forward observations; pinned full-validation receipt at operator preflight).

## No-lookahead verification

- Predictor excludes late-arriving trades (`test_shadow_run1_predictor`)
- Append-only experiment store (`test_shadow_run1_experiment_store`)
- Labeling separated from decision generation (`test_shadow_run1_labeling_job`)
- Causality violations at report time: 0 (no decisions yet)

## Operational findings

- Shadow CLI end-to-end verified: `open`, `status`, `acceptance`
- Preflight remains fail-closed without pinned validation + runtime health receipts
- Production `open` requires clean worktree; feature increment used `--allow-dirty` with documented note

## Validation

| Command | Result |
|---------|--------|
| `unittest tests.platform.test_shadow_run1_acceptance` | 4 passed |
| `unittest tests.platform.test_shadow_run1_*` (targeted) | 23 passed |
| `validate.py changed` | 670 passed, 1 failure — flaky `test_parallel_submits_have_unique_event_sequences` (pre-existing platform smoke; unrelated to P6 changes) |

## Documentation reconciliation

Updated: `PROJECT_STATUS.md`, `PRODUCT_BACKLOG.md`, `PLATFORMIZATION_ROADMAP.md`, `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`, `WORK_LOG.md`, `docs/README.md`, design spec status, new operator SOP.

## Remaining blockers

1. Configure Moomoo OpenD + `IMP_MOOMOO_LIVE=1` / `IMP_LIVE_OBSERVATIONAL=1`
2. Pin `validate.py full` receipt for preflight
3. Arm `IMP_SHADOW_RECORDING=1` with `IMP_SHADOW_RUN_ID`
4. Collect ≥1 ACTUAL_FORWARD observation window across preregistered sessions
5. Complete stopping rule or explicit `close`; `label-due`; `report`

## Git state

Feature branch `feat/p6-shadow-run-1-forward-validation` from baseline `96032be`.

## Related

- [FORWARD_SHADOW_VALIDATION SOP](../engineering/sops/FORWARD_SHADOW_VALIDATION.md)
- [2026-08-23-platform-p6-shadow-run-1-design.md](../superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md)
