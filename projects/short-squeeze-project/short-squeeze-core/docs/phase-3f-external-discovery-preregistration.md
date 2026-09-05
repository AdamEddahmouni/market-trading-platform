# Phase 3F — External discovery preregistration (cohort expansion beyond in-repo)

**Date:** 2026-08-17  
**Status:** Batch 05 external lane preregistered — **not executed** (awaiting Finviz export capture)

## Context

Phase 3F Batches 01–04 brought the IBKR frozen-boundary track to **29 symbols** and the
historical research registry to **30 case boundaries** (n=30 policy threshold met).
All archived discovery sources in this repository are exhausted:

| Source | Status |
|--------|--------|
| Batch 01 scanner snapshot (13 rows) | Exhausted |
| Phase 2V comparison manifest | Exhausted |
| Phase 3F news / prime-log / screening-universe JSONL | Exhausted |
| BIYA yahoo-chart alignment (Batch 04) | Complete |

Further cohort growth requires **new discovery material outside the repo**, each batch
preregistered before acquisition (ADR-0063, Phase 3F pattern).

## Proposed external discovery lanes (pick one per batch)

1. **Live IBKR broad-mover scan** — new symbols from gateway scanner at a documented
   as-of instant (requires IBKR entitlement + pacing budget).
2. **Fresh Finviz Elite export** — new screener snapshot file with provenance timestamp
   (not the archived 13-row snapshot).
3. **External case list** — third-party research case import with explicit provenance
   classification and symbol identity resolution audit.

## Batch 05 gate (if executed)

| Requirement | Notes |
|-------------|--------|
| Preregistration doc | This file + batch-specific cohort table before any bars collected |
| Symbol count | 3–5 symbols per batch (Phase 3F convention) |
| Identity audit | Exclude `BLOCKED_CONFLICTING_IDENTITY` (KLOS pattern) |
| Batch 05 manifests | Register in `intake/local-bars/ibkr-batch-05` private provenance |
| Stage 2 forward bars | Adjusted Monday window when boundary is weekend |
| Batch 07 readiness | Run `tools/run_batch07_readiness.py` after manifest registration |
| Phase 3A freeze | Leakage audit per new case boundary |
| Calibration | Re-run `tools/run_calibration_suite.py`; update ADRs only if findings change materially |

## Non-goals

- No in-repo symbol re-scanning (already exhausted)
- No Adam methodology threshold changes during acquisition
- No Batch 07 semantics gate lowering to inflate detection evaluability
- No conflation with live screener `CLOUD_PROVIDER_MODE` current candidates

## Acknowledged limitations

- Batch 07 price-level blocking will keep most artifact-discovery symbols detection-unevaluable
  under baseline policy (ADR-0067) regardless of cohort size.
- External discovery does not automatically improve detection evaluability without
  semantics resolution work (separate track from cohort counting).

## Revision history

| Date | Change |
|------|--------|
| 2026-08-17 | Initial preregistration after in-repo discovery exhaustion |
| 2026-08-17 | Batch 05 external Finviz export lane preregistered — see [phase-3f-cohort-expansion-batch-05-external.md](phase-3f-cohort-expansion-batch-05-external.md) |
