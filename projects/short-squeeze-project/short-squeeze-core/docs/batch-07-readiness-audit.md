# Batch 07 operation-readiness audit (IBKR frozen-boundary cohort)

**Date:** 2026-08-17  
**Status:** Complete — 29/29 cases audited at shared frozen boundary

## Scope

Batch 07 operation-specific readiness consumes **only** Batch 05 provenance manifests
(request/artifact coverage, sha256, byte length). It never reads OHLCV or forward-outcome
bars. This audit confirms the expanded IBKR frozen-boundary cohort (including BIYA from
Phase 3F Batch 04) is wired for Phase 3A freeze consumption.

## Cohort

| Metric | Count |
|--------|------:|
| Frozen-boundary symbols | 29 |
| Operation-readiness cases | 29 |
| Phase 3A request readiness | 29/29 `PHASE3A_REQUEST_READY` |
| Global preflight verdict | `PREFLIGHT_REJECTED` (unchanged) |

## Key findings

1. **PRICE_RANGE** remains `BLOCKED_MISSING_SEMANTICS` — absolute price-level corporate-action
   semantics are not confirmed (`ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07`). This is expected
   and does not block cohort registration or outcome labeling.
2. **RELATIVE_VOLUME_MINIMUM** remains `BLOCKED_MISSING_SEMANTICS` — volume unit / corporate-action
   semantics unresolved at Batch 07 (`VOLUME_SEMANTICS_BLOCKED_BY_BATCH07`).
3. **MARKET_DATA_AVAILABLE** and **COMPLETED_BAR_AVAILABLE** are **ADMISSIBLE** on bar-backed rules.
4. **PERCENTAGE_CHANGE_MINIMUM** is **ADMISSIBLE_WITH_CONSTRAINTS** (ratio semantics only).
5. BIYA (yahoo-chart intake, IBKR-shaped) participates identically to IBKR-collected symbols
   at the provenance layer.

## Artifacts

```powershell
cd short-squeeze-project\short-squeeze-core
$env:PYTHONPATH="src;."
python tools/run_batch07_readiness.py
```

- JSON: `reports/acquisition/batch07-operation-readiness-report.json`
- Markdown: `reports/acquisition/batch07-operation-readiness-report.md`
- Synthetic golden (15-case fixture): `tests/fixtures/acquisition/batch07/`

## Governance

- Descriptive readiness only — no outcome scores, rankings, or auto-promotion.
- Detection policy calibration (ADR-0067) already documents that 28/30 historical case
  boundaries remain detection-unevaluable under baseline due to Batch 07 price blocking.
- Cohort expansion beyond in-repo US equity tickers requires **external discovery**
  preregistration (Phase 3F pattern), not further Batch 07 manifest edits.

## Explicit non-recommendations

- Do not treat readiness admissibility as Phase 3A PASS/FAIL.
- Do not lower Batch 07 semantics gates to inflate detection evaluability on artifact-discovery symbols.
