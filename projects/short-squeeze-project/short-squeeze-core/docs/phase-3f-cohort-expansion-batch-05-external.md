# Phase 3F Cohort Expansion — Batch 05 External Discovery (Preregistered)

## Status

**Complete (2026-08-17).** Export captured, identity audit passed, IBKR bars collected,
manifests merged, Phase 3A freeze, Stage 2 outcomes, fixture regeneration, and
calibration re-run completed for five external-discovery symbols. Four symbols
have evaluable forward-outcome labels; **AACP** is permanently
`OUTCOME_UNEVALUABLE` — IBKR returned `SUCCESS_EMPTY` on initial collection and on
the 2026-08-18 adjusted-forward retry (see
[AACP_OUTCOME_EXCLUSION_RECORD.md](calibration/AACP_OUTCOME_EXCLUSION_RECORD.md)).

## Discovery lane

**Fresh Finviz Elite export** (lane 2 from
[phase-3f-external-discovery-preregistration.md](phase-3f-external-discovery-preregistration.md)).

| Parameter | Value |
|-----------|-------|
| API endpoint | `https://elite.finviz.com/export/screener` |
| Filter (`f`) | `sh_float_u50,sh_price_u50` (same as live screener `DEFAULT_FILTER`) |
| Columns (`c`) | Finviz Elite squeeze column bundle (`FINVIZ_COLUMNS` in `finviz_live.py`) |
| Provenance class | `EXTERNAL_PROVIDER_EXPORT` |
| Capture requirement | Store raw CSV byte hash + `observed_at` UTC instant before any bars collected |

Rejected for this batch:

- Live IBKR broad-mover scan (lane 1) — deferred; requires gateway entitlement budget
  separate from historical intake.
- External case list import (lane 3) — deferred; no third-party list preregistered.

## Cohort selection policy (at export capture)

Select **3–5 US equity tickers** from the fresh export that are **not** in the frozen
IBKR cohort (`FROZEN_COHORT`, 29 symbols as of Batch 04). Apply in export row order
(top of CSV after header):

1. Exclude any symbol in `excluded_symbols` (see normalized artifact).
2. Exclude `BLOCKED_CONFLICTING_IDENTITY` candidates (KLOS pattern).
3. Require resolvable primary exchange for IBKR contract lookup before preregistration
   table is finalized.
4. Stop after five symbols or when the export is exhausted.

Symbols and case IDs are **not fixed in this preregistration** — they are recorded in
`intake/batches/phase-3f-cohort-expansion-05-external/normalized/batch3f05_external_discovery_rows.json`
when the export is captured.

## Frozen boundary

The cohort boundary for all Batch 05 symbols will equal the documented Finviz export
`observed_at` instant (same convention as Batch 01–04: shared cohort boundary for outcome
comparability, not per-row news timestamps).

Case ID pattern: `BATCH3F05_{SYMBOL}_{YYYYMMDD}` derived from boundary UTC date.

## Window adjustment

Identical to Phase 3E Stage 2: if the boundary falls on a weekend, shift the forward
outcome window to the next US equity trading day (Monday open alignment).

## Execution gate (after export capture)

| Step | Artifact |
|------|----------|
| 1. Capture export | Raw CSV in private provenance + normalized discovery JSON |
| 2. Identity audit | Offline IBKR contract resolvability for each selected symbol |
| 3. IBKR bars | `intake/local-bars/ibkr-batch-05/raw/{SYMBOL}-detection-context.*` |
| 4. Batch 05 manifests | Register in private `ibkr-batch-05` provenance root |
| 5. Batch 07 readiness | `python tools/run_batch07_readiness.py` |
| 6. Phase 3A freeze | Leakage audit per new case boundary |
| 7. Stage 2 forward bars | Adjusted Monday window when boundary is weekend |
| 8. Calibration | Re-run `tools/run_calibration_suite.py`; update ADRs only if findings change |

Capture helper (live API or offline CSV):

```powershell
cd short-squeeze-project\short-squeeze-core
python tools/capture_batch05_finviz_export.py
# or after saving Elite export manually:
python tools/capture_batch05_finviz_export.py --csv-path path\to\finviz-export.csv
```

Refresh expired export tokens before live capture:

```powershell
python tools/provider_auth/finviz_token_refresh.py --providers-env .private/providers.env
```

Identity audit and bar collection:

```powershell
python tools/run_batch05_identity_audit.py
python tools/collect_batch05_external_bars.py
```

## Non-goals

- No in-repo archived news / prime-log re-scanning (exhausted)
- No Adam methodology threshold changes during acquisition
- No Batch 07 semantics gate lowering to inflate detection evaluability
- No conflation with live screener `CLOUD_BOOTSTRAP_SYMBOLS` or current candidates

## Acknowledged limitations

- Batch 07 `PRICE_RANGE` blocking will keep most artifact-discovery symbols
  detection-unevaluable under baseline policy (ADR-0067) regardless of cohort size.
- External discovery does not automatically improve detection evaluability without
  semantics resolution work (separate track).

## Revision history

| Date | Change |
|------|--------|
| 2026-08-17 | Initial external-discovery preregistration (lane 2 — Finviz export) |
